# SPDX-License-Identifier: AGPL-3.0-only
"""An error report names the HST Office version only: no engine version (26.8) in what the user sees or sends.

The dialog summary, the preview (the JSON body), the systemInfo lines, the e-mail fallback and the attached local
log all leave the engine out; the server maps the HST version to its engine (docs/BUILD_MATRIX.md). A body without
product.engine is accepted (the field is optional in the API contract and in the fake server's reading).
"""
import os
import re
import tempfile
import unittest
from unittest import mock

import _paths  # noqa: F401
from error_report_fake_server import invalid
from hst_office import diag_log
from hst_office import error_report_filter as flt
from hst_office import error_report_info as info
from hst_office import error_report_mail as mail
from hst_office import error_report_payload as p

ENGINE = re.compile(r"(?<![\d.])26\.8(?!\d)|\bengine\b|\blõi\b", re.IGNORECASE)
OS = {"family": "windows", "version": "Windows 11 (10.0.26100)", "arch": "x86_64"}
SECRETS = flt.personal_strings({"USER": "an"})


def report(product):
    return p.build_payload(p.new_report_id(), "user", p.utc_now(), product, OS, "vi-VN", "writer",
                           description="Không in được.", diagnostics={"systemInfo": "Version: 1.0.2 (x86_64)"})


class ProductTests(unittest.TestCase):
    def test_product_is_the_hst_release_and_build_only(self):
        with mock.patch.object(info, "load_data", return_value={"release": "1.0.2", "build": 10000}):
            self.assertEqual(info.product(None), {"version": "1.0.2", "build": "10000"})

    def test_body_without_engine_is_valid_for_client_and_server(self):
        payload = report({"version": "1.0.2", "build": "10000"})
        self.assertEqual(p.schema_errors(payload), [])
        self.assertEqual(invalid(payload), "")
        self.assertEqual(set(payload["product"]), {"version", "build"})


class VisibleTextTests(unittest.TestCase):
    def test_preview_summary_and_mail_name_no_engine(self):
        payload = report({"version": "1.0.2", "build": "10000"})
        for text in (p.preview_text(payload), "\n".join(mail.summary_lines(payload)), mail.plain_text(payload),
                     mail.mailto_url(payload)):
            self.assertNotRegex(text, ENGINE)
        self.assertIn("Phiên bản: HST Office 1.0.2 (bản dựng 10000)", mail.plain_text(payload))

    def test_system_info_has_no_engine_line(self):
        fields = {"Version": "1.0.2 (x86_64)", "Engine": "26.8.1.1", "OS": "Windows 11", "VCL": "win"}
        text = info.system_info_text(fields)
        self.assertEqual(text, "Version: 1.0.2 (x86_64)\nOS: Windows 11\nVCL: win")

    def test_session_line_and_older_logs_carry_no_engine(self):
        with tempfile.TemporaryDirectory() as folder:
            diag_log.configure(folder, SECRETS)
            try:
                with open(os.path.join(folder, diag_log.LOG_NAME), "w", encoding="utf-8") as handle:
                    # Written by 1.0.1 before the update: the engine field must not reach a new report.
                    handle.write("2026-11-10T08:00:00Z INFO session: start 1.0.1 build 680 engine 26.8.1.1; "
                                 "Windows 11 x86_64; vi-VN; python 3.12.1\n")
                from hst_office import diag_crash
                with mock.patch.object(diag_crash, "_capture_stderr"), \
                        mock.patch.object(diag_crash, "previous_session", return_value=None):
                    diag_crash.start(None, ({"version": "1.0.2", "build": "10000"}, OS, "vi-VN", "writer"))
                text = info.recent_log(SECRETS)
            finally:
                diag_log.configure(None)
        self.assertIn("session: start 1.0.1 build 680; Windows 11 x86_64", text)
        self.assertIn("session: start 1.0.2 build 10000; Windows 11", text)
        self.assertNotRegex(text, ENGINE)


if __name__ == "__main__":
    unittest.main()
