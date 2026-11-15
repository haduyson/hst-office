# SPDX-License-Identifier: AGPL-3.0-only
"""The anonymous install ID in an error report: sent in its own "installId" field only when "Gửi mã máy ẩn danh" is on
and an ID exists, never created for a report, never in free text; shown by "Xem nội dung sẽ gửi", in the e-mail
fallback, and accepted by a server that follows the contract (local fake server, never the real endpoint)."""
import json
import unittest
from unittest import mock

import _paths  # noqa: F401
from install_id_support import ID, FakeConfig, cfg  # UNO stubs first
from error_report_fake_server import FakeServer, invalid
from hst_office import error_report_dialog as dialog
from hst_office import error_report_filter as flt
from hst_office import error_report_mail as mail
from hst_office import error_report_payload as p
from hst_office import error_report_send as s
from hst_office import update_install_id as iid
from hst_office.error_report_texts import TEXT

PRODUCT = {"version": "1.0.2", "build": "10000"}
OS = {"family": "linux", "version": "Ubuntu 24.04.1 LTS, kernel 6.8.0", "arch": "x86_64"}
OTHER_ID = "9c2d4e6f-1a3b-4c5d-8e7f-0a1b2c3d4e5f"


def build(**kw):
    args = dict(report_id=p.new_report_id(), kind="user", created_at=p.utc_now(), product=PRODUCT, os=OS,
                locale="vi-VN", app="writer", description="Không lưu được tệp.")
    args.update(kw)
    return p.build_payload(**args)


class ForReport(unittest.TestCase):
    def test_on_with_id(self):
        self.assertEqual(iid.for_report(dict(cfg.DEFAULTS, InstallId=ID)), ID)

    def test_off_sends_nothing_even_with_a_stored_id(self):
        self.assertIsNone(iid.for_report(dict(cfg.DEFAULTS, SendInstallId=False, InstallId=ID)))

    def test_no_or_invalid_id_sends_nothing(self):
        for stored in ("", None, ID.upper(), "{%s}" % ID, "not-an-id"):
            self.assertIsNone(iid.for_report(dict(cfg.DEFAULTS, InstallId=stored)), stored)

    def test_a_report_never_creates_or_stores_an_id(self):
        for values in ({}, {"SendInstallId": False}, {"InstallId": ID}):
            config = FakeConfig(**values).patch(self)
            with mock.patch.object(iid, "new_install_id", side_effect=AssertionError("created")):
                iid.for_error_report(None)
            self.assertEqual(config.saves, [], values)

    def test_failure_to_read_settings_gives_no_id(self):
        with mock.patch.object(cfg, "settings", side_effect=RuntimeError("no configuration")), \
                mock.patch.object(iid.diag_log, "exception"):
            self.assertIsNone(iid.for_error_report(None))


class Payload(unittest.TestCase):
    def test_on_adds_the_top_level_field_and_stays_valid(self):
        payload = build(install_id=ID)
        self.assertEqual(payload["installId"], ID)
        self.assertEqual(p.schema_errors(payload), [])
        self.assertEqual(invalid(payload), "")  # the server ignores what it does not know
        self.assertEqual(json.loads(p.encode(payload))["installId"], ID)

    def test_off_or_no_id_leaves_the_field_out(self):
        for value in (None, "", "not-an-id", ID.upper()):
            self.assertNotIn("installId", build(install_id=value), value)
        self.assertNotIn("installId", build())

    def test_schema_check_rejects_a_bad_value(self):
        payload = dict(build(), installId="x")
        self.assertIn("installId", p.schema_errors(payload))

    def test_free_text_still_hides_uuids(self):
        log = flt.scrub("update check failed for ?i=%s\nother %s" % (ID, OTHER_ID), secrets=[])
        self.assertNotIn(ID, log)
        self.assertNotIn(OTHER_ID, log)
        body = p.encode(build(install_id=ID, diagnostics={"log": log}))
        self.assertEqual(body.count(ID.encode()), 1)  # only in "installId"
        self.assertIn(b"<ID>", body)


class Mail(unittest.TestCase):
    def test_fallback_text_carries_the_field_when_sent(self):
        text = mail.plain_text(build(install_id=ID))
        self.assertIn("Mã máy ẩn danh: " + ID, text)
        self.assertIn(ID, mail.mailto_url(build(install_id=ID)))

    def test_fallback_text_has_no_id_when_off(self):
        self.assertNotIn("Mã máy ẩn danh", mail.plain_text(build()))

    def test_long_reports_keep_the_id(self):
        url = mail.mailto_url(build(install_id=ID, diagnostics={"log": "x" * 20000}))
        self.assertIn(ID, url)
        self.assertLessEqual(len(url), mail.MAX_URL)


class _FakeDialog:
    """dialogs.Dialog double: records the read-only text of each edit field, returns the user's entries."""
    shown = []

    def __init__(self, ctx, title, width, height):
        self.title, self.texts = title, {}

    def label(self, *args, **kw):
        return mock.Mock()

    def edit(self, name, *args, text="", **kw):
        self.texts[name] = text

    def button(self, *args, **kw):
        pass

    def execute(self, parent=None):
        _FakeDialog.shown.append(self)

    def get(self, name):
        return {"description": "Không lưu được tệp.", "email": "", "diagnostics": False}[name]


class DialogPreview(unittest.TestCase):
    def preview(self, kind="user", **values):
        FakeConfig(**values).patch(self)
        _FakeDialog.shown = []
        environment = (PRODUCT, OS, "vi-VN", "writer")
        with mock.patch.object(dialog.info, "environment", return_value=environment), \
                mock.patch.object(dialog, "release_info", return_value={"release": "1.0.2"}), \
                mock.patch.object(dialog, "proxy", return_value={}), \
                mock.patch.object(dialog, "Dialog", _FakeDialog):
            report = dialog.ReportDialog(None, None, kind=kind)
            report.dialog = _FakeDialog(None, "", 0, 0)
            report.show_preview()
        self.assertEqual(len(_FakeDialog.shown), 1)
        return json.loads(_FakeDialog.shown[0].texts["content"]), report

    def test_preview_shows_the_field_when_on(self):
        for kind in ("user", "crash"):
            shown, report = self.preview(kind, InstallId=ID)
            self.assertEqual(shown["installId"], ID, kind)
            self.assertEqual(shown, json.loads(p.preview_text(report.payload())))

    def test_preview_has_no_field_when_off_or_without_id(self):
        self.assertNotIn("installId", self.preview(SendInstallId=False, InstallId=ID)[0])
        self.assertNotIn("installId", self.preview()[0])

    def test_always_sent_text_mentions_the_install_id(self):
        self.assertIn("mã máy ẩn danh (nếu bật)", TEXT["summary"])


class Server(unittest.TestCase):
    def test_contract_server_accepts_the_body_and_receives_the_field(self):
        server = FakeServer()
        self.addCleanup(server.close)
        outcome = s.send(p.encode(build(install_id=ID)), "1.0.2", proxy={}, test_mode=True,
                         environ={s.TEST_URL_ENV: server.url}, timeout=10)
        self.assertEqual(outcome.kind, "sent")
        self.assertEqual(server.reports[0]["installId"], ID)


if __name__ == "__main__":
    unittest.main()
