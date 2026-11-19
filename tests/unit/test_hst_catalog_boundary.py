# SPDX-License-Identifier: AGPL-3.0-only
import importlib.util
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts/l10n"))
import hst_catalog

spec = importlib.util.spec_from_file_location("boundary", ROOT / "scripts/l10n/check-catalog-boundary.py")
boundary = importlib.util.module_from_spec(spec)
spec.loader.exec_module(boundary)


class CatalogBoundaryTest(unittest.TestCase):
    def test_retired_hunks_cannot_reenter_applied_patch(self):
        directory = ROOT / "patches/libreoffice"
        data = (directory / "hst-ribbon-tab-search-strings.patch").read_bytes()
        live, retired = boundary.active_patch(data)
        self.assertIn(b"STR_HST_TAB_SEARCH", live)
        self.assertNotIn(b"+++ b/translations/source", live)
        self.assertIn(b"+++ b/translations/source", retired)

    def test_new_upstream_catalog_hunk_is_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp)
            (path / "series").write_text("new.patch\n")
            (path / "new.patch").write_bytes(b"--- a/translations/source/vi/sfx2/messages.po\n"
                                              b"+++ b/translations/source/vi/sfx2/messages.po\n"
                                              b"@@ -1 +1 @@\n-old\n+new\n")
            with self.assertRaisesRegex(ValueError, "upstream PO hunk"):
                boundary.check_series(path)

    def test_pristine_check_rejects_incomplete_or_overlaid_tree(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / "sfx2").mkdir()
            (root / "sfx2/messages.po").write_text('msgid "old HST entry"\nmsgstr ""\n')
            with self.assertRaisesRegex(ValueError, "differ from the pinned release"):
                hst_catalog.verify_upstream(root)
