# SPDX-License-Identifier: AGPL-3.0-only
"""Error report body: building, validation, size limits, sanitising, the privacy filter and the e-mail fallback."""
import json
import os
import tempfile
import unittest
import urllib.parse

import _paths  # noqa: F401
from error_report_fake_server import invalid
from hst_office import error_report_filter as flt
from hst_office import error_report_info as info
from hst_office import error_report_mail as mail
from hst_office import error_report_payload as p

PRODUCT = {"version": "1.0.0-beta.5", "build": "500", "engine": "26.8.1.1"}
OS = {"family": "linux", "version": "Ubuntu 24.04.1 LTS, kernel 6.8.0", "arch": "x86_64"}
SECRETS = flt.personal_strings({"HOME": "/home/nguyenvana", "USER": "nguyenvana",
                                "USERPROFILE": "C:\\Users\\Nguyen Van A"}, extra=["/home/nguyenvana/.config/hstoffice"])


def build(**kw):
    args = dict(report_id=p.new_report_id(), kind="user", created_at=p.utc_now(), product=PRODUCT, os=OS,
                locale="vi-VN", app="writer", description="Không lưu được tệp.")
    args.update(kw)
    return p.build_payload(**args)


class PayloadTests(unittest.TestCase):
    def test_minimal_user_report_matches_the_contract(self):
        payload = build()
        self.assertEqual(p.schema_errors(payload), [])
        self.assertEqual(invalid(payload), "")  # the fake server's independent reading
        self.assertEqual(set(payload), {"schemaVersion", "reportId", "kind", "createdAt", "product", "os", "locale",
                                        "app", "description"})
        self.assertRegex(payload["createdAt"], r"^\d{4}-\d\d-\d\dT\d\d:\d\d:\d\dZ$")

    def test_diagnostics_only_when_given_and_app_always_sent(self):
        self.assertNotIn("diagnostics", build(diagnostics={"systemInfo": " ", "log": ""}))
        self.assertEqual(build(app="nonsense")["app"], "unknown")
        crash = build(kind="crash", description="", diagnostics={"crash": "Emergency save ran: yes"})
        self.assertNotIn("description", crash)
        self.assertEqual(crash["diagnostics"], {"crash": "Emergency save ran: yes"})
        self.assertEqual(p.schema_errors(crash), [])
        self.assertEqual(invalid(crash), "")

    def test_encode_is_the_preview_object(self):
        payload = build(contact_email="an@congty.vn", diagnostics={"systemInfo": "Version: x"})
        self.assertEqual(json.loads(p.encode(payload)), json.loads(p.preview_text(payload)))
        self.assertIn("Không lưu được tệp.".encode("utf-8"), p.encode(payload))  # UTF-8, not \\u escapes

    def test_validation(self):
        self.assertEqual(p.problems(build(description="  ")), ["description_missing"])
        self.assertEqual(p.problems(build(description="x" * 5001)), ["description_long"])
        self.assertEqual(p.problems(build(description="x" * 5000)), [])
        for bad in ("an", "an@", "a b@c.vn", "an@congty", "<an@congty.vn>", "an'o@congty.vn", "a`n@congty.vn",
                    'a"n@congty.vn', "x" * 250 + "@congty.vn"):
            self.assertEqual(p.problems(build(contact_email=bad)), ["email_invalid"], bad)
            self.assertNotEqual(invalid(build(contact_email=bad)), "", bad)
        for good in ("an@congty.vn", "nguyen.van+a@mail.hasontech.vn"):
            self.assertEqual(p.problems(build(contact_email=good)), [], good)

    def test_diagnostics_are_cut_to_their_byte_limits_with_a_marker(self):
        big = "Lỗi đường truyền ứng dụng\n" * 20000  # multi-byte text far over every limit
        payload = build(diagnostics={"systemInfo": big, "log": big, "crash": big})
        for name, limit in p.LIMITS.items():
            value = payload["diagnostics"][name]
            self.assertLessEqual(len(value.encode("utf-8")), limit, name)
            self.assertGreater(len(value.encode("utf-8")), limit - 8, name)
        self.assertTrue(payload["diagnostics"]["log"].startswith(p.CUT_HEAD))  # the log keeps its recent end
        self.assertTrue(payload["diagnostics"]["systemInfo"].endswith(p.CUT_TAIL))
        self.assertLessEqual(len(p.encode(payload)), p.MAX_BODY)
        self.assertEqual(invalid(payload), "")

    def test_body_limit(self):
        payload = build(description="x" * 5000)
        payload["diagnostics"] = {"log": "y" * (p.MAX_BODY)}  # bypasses build_payload's cut
        self.assertIn("too_large", p.problems(payload))

    def test_sanitising_like_the_server(self):
        payload = build(description="a\r\nb\rc\x00d\x07e\tf\u202eg\u200bh", diagnostics={"log": "x\r\ny\x1b[0m"})
        self.assertEqual(payload["description"], "a\nb\ncde\tf\ufffdg\ufffdh")
        self.assertEqual(payload["diagnostics"]["log"], "x\ny[0m")

    def test_product_version_and_os_version_bounds(self):
        payload = build(product=dict(PRODUCT, version="1" * 100), os=dict(OS, version="v" * 300))
        self.assertEqual(len(payload["product"]["version"]), 80)
        self.assertEqual(len(payload["os"]["version"]), 120)
        self.assertEqual(p.schema_errors(payload), [])

    def test_os_info(self):
        self.assertEqual(p.os_info("Windows", "10", "10.0.19045", "AMD64"),
                         {"family": "windows", "version": "Windows 10 (10.0.19045)", "arch": "x86_64"})
        self.assertEqual(p.os_info("Darwin", machine="arm64", mac_version="14.5")["version"], "macOS 14.5")
        self.assertEqual(p.os_info("Linux", "6.8.0", machine="aarch64", pretty_name="Ubuntu 24.04 LTS"),
                         {"family": "linux", "version": "Ubuntu 24.04 LTS, kernel 6.8.0", "arch": "arm64"})


class FilterTests(unittest.TestCase):
    LOG = ("2026-11-06 10:00:01 ConvertEncoding\nTraceback (most recent call last):\n"
           '  File "/opt/hst-office1.0/share/extensions/hst-vietnamese-tools/python/hst_office/dispatch.py", line 79\n'
           '  File "C:\\Users\\Nguyen Van A\\AppData\\Roaming\\HST Office\\4\\user\\uno_packages\\x\\actions.py", line 3\n'
           "IOException: file:///home/nguyenvana/T%C3%A0i%20li%E1%BB%87u/b%C3%A1o.docx cannot open\n"
           "ValueError: 'Báo cáo quý 3.docx' at /home/nguyenvana/Tài liệu/Hồ sơ and C:\\Users\\Nguyen Van A\\Desktop\\"
           "Số liệu.xlsx was not found\n"
           "profile /home/nguyenvana/.config/hstoffice/4/user, user nguyenvana, mail an@congty.vn, "
           "\\\\server\\chia se\\Hợp đồng.odt, vnd.sun.star.tdoc:/1/Content, ~/Desktop/x, ratio 3/4 and/or tien.xlsx\n")
    PRIVATE = ("nguyenvana", "Nguyen Van A", "Báo", "báo", "Tài", "Hồ sơ", "Số liệu", "Hợp đồng", "quý", "an@congty",
               ".docx", ".xlsx", ".odt", "Desktop", "chia se", "server", "hstoffice", "AppData", "tdoc")

    def test_no_names_paths_or_users_survive(self):
        text = flt.scrub(self.LOG, SECRETS)
        for word in self.PRIVATE:
            self.assertNotIn(word, text)

    def test_shape_of_tracebacks_is_kept(self):
        text = flt.scrub(self.LOG, SECRETS)
        self.assertIn('File "<PATH>/dispatch.py", line 79', text)
        self.assertIn('File "<PATH>/actions.py", line 3', text)
        self.assertIn("IOException: <URL> cannot open", text)
        self.assertIn("ConvertEncoding", text)
        self.assertIn("ratio 3/4 and/or", text)

    def test_user_name_is_matched_as_a_word(self):
        secrets = flt.personal_strings({"USER": "minh"})
        self.assertEqual(flt.scrub("Minh: minhanh, minh.", secrets), "<USER>: minhanh, <USER>.")

    def test_recent_log_reads_the_filtered_tail_of_the_local_log(self):
        from hst_office import diag_log
        with tempfile.TemporaryDirectory() as folder:
            diag_log.configure(folder, SECRETS)
            try:
                self.assertEqual(info.recent_log(SECRETS), "")  # no log yet
                with open(os.path.join(folder, diag_log.LOG_NAME), "w", encoding="utf-8") as handle:
                    for number in range(1000):
                        handle.write("%d open /home/nguyenvana/Tài liệu/%d.docx\n" % (number, number))
                text = info.recent_log(SECRETS)
            finally:
                diag_log.configure(None)
            self.assertEqual(len(text.splitlines()), p.LOG_LINES)
            self.assertTrue(text.endswith("999 open <PATH>"))
            self.assertNotIn("nguyenvana", text)

    def test_system_info_and_vcl_backend(self):
        text = info.system_info_text({"Version": "1.0.0-beta.5 (x86_64)", "Engine": "26.8.1.1", "OS": "", "VCL": "gtk3"})
        self.assertEqual(text, "Version: 1.0.0-beta.5 (x86_64)\nEngine: 26.8.1.1\nVCL: gtk3")
        with tempfile.NamedTemporaryFile("w", delete=False) as maps:
            maps.write("7f00 r-xp /opt/hst-office1.0/program/libvclplug_gtk3lo.so\n")
        try:
            self.assertEqual(info.vcl_backend("Linux", maps.name), "gtk3")
        finally:
            os.unlink(maps.name)
        self.assertEqual(info.vcl_backend("Windows"), "win")
        self.assertEqual(info.app_of_module("com.sun.star.sheet.SpreadsheetDocument"), "calc")
        self.assertEqual(info.app_of_module("x"), "unknown")


class MailTests(unittest.TestCase):
    def test_mailto_carries_the_report_text(self):
        payload = build(contact_email="an@congty.vn")
        url = mail.mailto_url(payload)
        self.assertTrue(url.startswith("mailto:lienhe@hasontech.vn?subject="))
        query = urllib.parse.parse_qs(urllib.parse.urlsplit(url).query)
        self.assertEqual(query["subject"], ["Báo lỗi HST Office 1.0.0-beta.5"])
        self.assertIn("Không lưu được tệp.", query["body"][0])
        self.assertIn(payload["reportId"], query["body"][0])

    def test_long_report_is_shortened_with_a_note(self):
        payload = build(description="Mô tả dài " * 400, diagnostics={"log": "dòng nhật ký\n" * 500})
        url = mail.mailto_url(payload)
        self.assertLessEqual(len(url), mail.MAX_URL)
        body = urllib.parse.parse_qs(urllib.parse.urlsplit(url).query)["body"][0]
        self.assertTrue(body.endswith(mail.CUT_NOTE))
        self.assertTrue(body.startswith("Mô tả dài"))


if __name__ == "__main__":
    unittest.main()
