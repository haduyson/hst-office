# SPDX-License-Identifier: AGPL-3.0-only
"""Error reports name apps by their HST product names; the engine's module names stay a server key only.

What the user reads or sends as text (dialog summary, systemInfo "App:", crash text, e-mail, the payload's "appName")
says HST Writer, HST Sheets, HST Slides, HST Draw, HST Math, HST Base, HST PDF or Trang bắt đầu, never writer/calc/
impress/Calc/Impress. The payload "app" keeps the key system.hasontech.vn accepts (it answers 400 to other values).
"""
import re
import unittest

import _paths  # noqa: F401
from error_report_fake_server import invalid
from hst_office import error_report_apps as apps
from hst_office import error_report_crash as crash
from hst_office import error_report_info as info
from hst_office import error_report_mail as mail
from hst_office import error_report_payload as p

OLD_NAMES = re.compile(r"\b(writer|calc|impress|draw|math|base|start|startcenter|Calc|Impress|LibreOffice)\b")
PRODUCT = {"version": "1.0.2", "build": "10000"}
OS = {"family": "linux", "version": "Ubuntu 24.04", "arch": "x86_64"}


def report(app):
    return p.build_payload(p.new_report_id(), "user", p.utc_now(), PRODUCT, OS, "vi-VN", app, description="Lỗi")


class FakeController:
    def __init__(self, services):
        self.services = services

    def supportsService(self, name):  # noqa: N802 - UNO method name
        return name in self.services


class FakeFrame:
    def __init__(self, services):
        self.controller = FakeController(services)

    def getController(self):  # noqa: N802 - UNO method name
        return self.controller


class AppNameTests(unittest.TestCase):
    def test_every_server_key_has_a_product_name(self):
        expected = {"writer": "HST Writer", "calc": "HST Sheets", "impress": "HST Slides", "draw": "HST Draw",
                    "math": "HST Math", "base": "HST Base", "start": "Trang bắt đầu", "unknown": "Không rõ"}
        self.assertEqual({key: apps.app_name(key) for key in apps.SERVER_KEYS}, expected)
        self.assertEqual(apps.SERVER_KEYS, p.APPS)
        self.assertEqual(apps.app_name("pdf"), "HST PDF")
        self.assertEqual(apps.app_name("nonsense"), "Không rõ")

    def test_payload_keeps_the_server_key_and_adds_the_product_name(self):
        for key in apps.SERVER_KEYS:
            payload = report(key)
            self.assertEqual((payload["app"], payload["appName"]), (key, apps.app_name(key)))
            self.assertEqual(invalid(payload), "", key)
            self.assertEqual(p.schema_errors(payload), [], key)
        pdf = report("pdf")
        self.assertEqual((pdf["app"], pdf["appName"]), ("unknown", "HST PDF"))
        self.assertEqual(invalid(pdf), "")

    def test_text_users_read_names_hst_apps_only(self):
        for key in ("writer", "calc", "impress", "draw", "math", "base", "start", "pdf"):
            payload = report(key)
            system_info = info.system_info(None, None, payload)
            self.assertIn("App: " + apps.app_name(key), system_info)
            for text in (system_info, "\n".join(mail.summary_lines(payload)), mail.plain_text(payload),
                         payload["appName"]):
                self.assertNotRegex(text, OLD_NAMES, key)
        self.assertIn("Ứng dụng: HST Sheets", mail.summary_lines(report("calc")))

    def test_crash_text_names_the_apps_and_keeps_the_key(self):
        state = {"crashed": True, "session": False, "modules": ["com.sun.star.sheet.SpreadsheetDocument",
                                                                 "com.sun.star.text.WebDocument"]}
        text, app = crash.crash_facts(state)
        self.assertIn("Documents open at exit: 2 (HST Sheets, HST Writer)", text)
        self.assertEqual(app, "unknown")
        _text, app = crash.crash_facts(dict(state, modules=["com.sun.star.text.GlobalDocument"]))
        self.assertEqual(app, "writer")

    def test_hst_pdf_frame_is_its_own_app(self):
        self.assertEqual(info.app_of(None, FakeFrame({info.PDF_VIEWER})), "pdf")
        self.assertEqual(info.app_of(None, FakeFrame(set())), "unknown")  # no module manager outside the office


if __name__ == "__main__":
    unittest.main()
