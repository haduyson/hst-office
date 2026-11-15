# SPDX-License-Identifier: AGPL-3.0-only
"""hst-ui-mode-neutral-descriptions.patch: the user interface picker never names a third-party office suite.

The Tabbed and Tabbed Compact descriptions (cui/inc/uimode.hrc, shown in Tools > User Interface) compared the modes
with another vendor's product. The patch rewrites the English source; l10n/vi-overrides.jsonl renames the Vietnamese
keys to the new source (msgid_new) and gives neutral Vietnamese text."""
from pathlib import Path
import json
import unittest

ROOT = Path(__file__).resolve().parents[2]
PATCH = ROOT / "patches/libreoffice/hst-ui-mode-neutral-descriptions.patch"
SERIES = ROOT / "patches/libreoffice/series"
OVERRIDES = ROOT / "l10n/vi-overrides.jsonl"
VENDOR_WORDS = ("Microsoft", "MS Office", "Word", "Excel", "PowerPoint")


def hunk_lines(prefix):
    body = PATCH.read_text(encoding="utf-8").split("\n--- a/", 1)[1]
    return [line[1:] for line in body.splitlines()
            if line.startswith(prefix) and not line.startswith(("+++", "---"))]


def uimode_rows():
    rows = [json.loads(line) for line in OVERRIDES.read_text(encoding="utf-8").splitlines() if line.strip()]
    return [row for row in rows if row["file"] == "cui/messages.po" and row["msgctxt"] == "RID_CUI_UIMODES"]


class NeutralUiModeDescriptions(unittest.TestCase):
    def test_patch_in_series(self):
        self.assertIn(PATCH.name, SERIES.read_text(encoding="utf-8").split())

    def test_source_replaces_both_vendor_descriptions(self):
        removed, added = hunk_lines("-"), hunk_lines("+")
        self.assertEqual(len(removed), 2)
        self.assertEqual(len(added), 2)
        self.assertTrue(all("Microsoft" in line for line in removed))
        for line in added:
            self.assertIn("RID_CUI_UIMODES", line)
            self.assertIn("ribbon-style", line)
            for word in VENDOR_WORDS:
                self.assertNotIn(word, line)

    def test_vietnamese_rows_follow_new_source(self):
        new_ids = {line.split('"RID_CUI_UIMODES", "', 1)[1].split('")', 1)[0] for line in hunk_lines("+")}
        rows = {row["msgid_new"]: row for row in uimode_rows() if row.get("msgid_new")}
        self.assertEqual(set(rows), new_ids)
        for row in rows.values():
            self.assertIn("Microsoft", row["msgid"])
            self.assertIn("ribbon quen thuộc", row["msgstr"])
            for word in VENDOR_WORDS:
                self.assertNotIn(word, row["msgstr"])


if __name__ == "__main__":
    unittest.main()
