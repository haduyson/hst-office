# SPDX-License-Identifier: LicenseRef-HST-Proprietary
# Copyright (C) 2026 HASON TECH
"""The Vietnamese UI never calls a table or a metaobject a file.

The upstream Vietnamese translation titles the Insert Table dialog of Slides/Draw (cui newtabledialog.ui) and the
Insert Table placeholder button of Slides layouts "Chèn tập tin" (Insert File), which HST's glossary pass turns into
"Chèn tệp tin", and calls the broken-down metaobjects of the Break dialog "siêu tập tin" (metafiles).
l10n/vi-overrides.jsonl (applied after the upstream .po files and the l10n/vi overlay, so it wins) must correct them.
"""
import json
import os
import re
import unittest

from _paths import ROOT

OVERRIDES = os.path.join(ROOT, "l10n", "vi-overrides.jsonl")
FILE_WORD = re.compile(r"t[ệậ]p tin", re.IGNORECASE)
EXPECTED = {
    ("cui/messages.po", "newtabledialog|NewTableDialog", "Insert Table"): "Chèn bảng",
    ("sd/messages.po", "STR_INSERT_TABLE", "Insert Table"): "Chèn bảng",
    ("sd/messages.po", "breakdialog|label2", "Broken down metaobjects:"): "Các siêu đối tượng được chia nhỏ:",
}


def override_rows():
    with open(OVERRIDES, encoding="utf-8") as handle:
        return [json.loads(line) for line in handle if line.strip()]


class ViTableNotFileTest(unittest.TestCase):
    def test_mistranslated_strings_are_overridden(self):
        found = {(r["file"], r["msgctxt"], r["msgid"]): r["msgstr"] for r in override_rows()}
        for key, msgstr in EXPECTED.items():
            with self.subTest(key=key):
                self.assertEqual(found.get(key), msgstr)

    def test_no_table_override_says_file(self):
        for row in override_rows():
            if re.search(r"\btable\b", row["msgid"], re.IGNORECASE) and not re.search(r"file", row["msgid"], re.I):
                with self.subTest(msgctxt=row["msgctxt"]):
                    self.assertIsNone(FILE_WORD.search(row["msgstr"]), row["msgstr"])


if __name__ == "__main__":
    unittest.main()
