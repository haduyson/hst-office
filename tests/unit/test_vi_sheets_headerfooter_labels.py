# SPDX-License-Identifier: LicenseRef-HST-Proprietary
# Copyright (C) 2026 HASON TECH
"""The Sheets header/footer edit page shows "Preset", "Format", "Field" and its Bold/Italic/Underline tooltips in
Vietnamese.

Upstream headerfootercontent.ui leaves these six strings untranslatable, so no override row can reach them: the patch
hst-sheets-headerfooter-labels-translatable.patch marks them translatable with their own contexts and adds the
Vietnamese entries to translations/source/vi/sc/messages.po.
"""
import os
import re
import unittest

from _paths import ROOT

PATCHES = os.path.join(ROOT, "patches", "libreoffice")
NAME = "hst-sheets-headerfooter-labels-translatable.patch"
# context -> (English source, Vietnamese)
EXPECTED = {
    "headerfootercontent|labelFT_PRESET": ("Preset", "Định sẵn"),
    "headerfootercontent|labelFT_FORMAT": ("Format", "Định dạng"),
    "headerfootercontent|labelFT_FIELD": ("Field", "Trường"),
    "headerfootercontent|buttonBTN_BOLD|tooltip_text": ("Bold", "Đậm"),
    "headerfootercontent|buttonBTN_ITALIC|tooltip_text": ("Italic", "Nghiêng"),
    "headerfootercontent|buttonBTN_UNDERLINE|tooltip_text": ("Underline", "Gạch dưới"),
}


def file_sections(text):
    """{path: added lines} of a unified diff."""
    sections, current = {}, None
    for line in text.splitlines():
        if line.startswith("+++ b/"):
            current = sections.setdefault(line[6:], [])
        elif current is not None and line.startswith("+") and not line.startswith("+++"):
            current.append(line[1:])
    return sections


class ViSheetsHeaderFooterLabelsTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with open(os.path.join(PATCHES, NAME), encoding="utf-8") as handle:
            cls.sections = file_sections(handle.read())

    def test_patch_is_in_the_series(self):
        with open(os.path.join(PATCHES, "series"), encoding="utf-8") as handle:
            self.assertIn(NAME, handle.read().split())

    def test_ui_strings_become_translatable(self):
        added = "\n".join(self.sections["sc/uiconfig/scalc/ui/headerfootercontent.ui"])
        for context, (english, _) in EXPECTED.items():
            with self.subTest(context=context):
                self.assertRegex(added, rf'translatable="yes" context="{re.escape(context)}">{english}</property>')

    def test_vietnamese_entries_are_added(self):
        added = "\n".join(self.sections["translations/source/vi/sc/messages.po"])
        for context, (english, vietnamese) in EXPECTED.items():
            with self.subTest(context=context):
                self.assertIn(f'msgctxt "{context}"\nmsgid "{english}"\nmsgstr "{vietnamese}"', added)


if __name__ == "__main__":
    unittest.main()
