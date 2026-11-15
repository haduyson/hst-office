# SPDX-License-Identifier: AGPL-3.0-only
"""check-branding --release: the installed ReadMe names the HST version, never the engine version (26.8)."""
import os
import shutil
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(ROOT, "scripts"))

from brand.audit import check_version_fields  # noqa: E402


def write(base, rel, text):
    path = os.path.join(base, rel)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as handle:
        handle.write(text)


class ReadmeVersionTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmp, True)

    def test_readme_with_the_hst_version_passes(self):
        write(self.tmp, "opt/hst-office1.0/readmes/README_vi", "Tài liệu Đọc Đi HST Office 1.0\n\nPython 3.12.8\n")
        self.assertEqual(check_version_fields(self.tmp, "1.0.2"), [])

    def test_engine_version_in_a_readme_is_reported_with_its_line(self):
        write(self.tmp, "opt/hst-office1.0/readmes/README_en-US", "HST Office 26.8 ReadMe\n\nhst office26.8-x\n")
        write(self.tmp, "HST Office.app/Contents/Resources/readmes/README_vi", "ok\nHST Office 26.8.1.1\n")
        problems = check_version_fields(self.tmp, "1.0.2")
        self.assertIn("opt/hst-office1.0/readmes/README_en-US:1: engine version: HST Office 26.8 ReadMe", problems)
        self.assertIn("opt/hst-office1.0/readmes/README_en-US:3: engine version: hst office26.8-x", problems)
        self.assertIn("HST Office.app/Contents/Resources/readmes/README_vi:2: engine version: HST Office 26.8.1.1",
                      problems)

    def test_other_files_named_readme_are_not_version_fields(self):
        write(self.tmp, "opt/hst-office1.0/share/README_engine", "built on 26.8\n")
        self.assertEqual(check_version_fields(self.tmp, "1.0.2"), [])


if __name__ == "__main__":
    unittest.main()
