# SPDX-License-Identifier: AGPL-3.0-only
"""Reject source locks that can select a mixed or unverified upstream release."""
import importlib.util
import json
from pathlib import Path
import shutil
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location("source_lock", ROOT / "scripts/check-source-lock.py")
CHECK = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(CHECK)


class SourceLock(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        for name in (*CHECK.SOURCE_PINS, "upstream/libreoffice-lock.json"):
            target = self.root / name
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(ROOT / name, target)
        self.path = self.root / "upstream/libreoffice-lock.json"
        self.lock = json.loads(self.path.read_text())

    def test_current_source_selection_is_consistent(self):
        self.assertEqual(CHECK.check_lock(self.root), self.lock["version"])

    def test_stale_platform_pin_is_rejected(self):
        path = self.root / "scripts/windows/trial-build.sh"
        path.write_text(path.read_text().replace(self.lock["version"], "26.8.1.1"))
        with self.assertRaisesRegex(ValueError, "differs from lock"):
            CHECK.check_lock(self.root)

    def test_wrong_archive_release_url_is_rejected(self):
        self.lock["tarballs"][0]["url"] = self.lock["tarballs"][0]["url"].replace("/src/", "/old/")
        self.path.write_text(json.dumps(self.lock))
        with self.assertRaisesRegex(ValueError, "source URL"):
            CHECK.check_lock(self.root)

    def test_duplicate_archive_cannot_hide_missing_archive(self):
        self.lock["tarballs"][-1] = self.lock["tarballs"][0]
        self.path.write_text(json.dumps(self.lock))
        with self.assertRaisesRegex(ValueError, "expected exactly"):
            CHECK.check_lock(self.root)


if __name__ == "__main__":
    unittest.main()
