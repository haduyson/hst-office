# SPDX-License-Identifier: AGPL-3.0-only
"""HST menu contract from Addons.xcu: where each command is offered and which language its label has."""
import json
import os
import unittest
import xml.etree.ElementTree as ET

import _paths

EXT = os.path.join(_paths.ROOT, "extensions", "hst-vietnamese-tools")
OOR, XML = "{http://openoffice.org/2001/registry}", "{http://www.w3.org/XML/1998/namespace}"
ALL = {"com.sun.star.text.TextDocument", "com.sun.star.sheet.SpreadsheetDocument", "com.sun.star.presentation.PresentationDocument"}
UPDATE = "org.hst.office.update:Check"


def items(section):
    """{(url): [(title values by lang, contexts)]} for every addon node under the given AddonUI section."""
    root = ET.parse(os.path.join(EXT, "Addons.xcu")).getroot()
    result = {}
    for node in root.iter("node"):
        props = {p.get(OOR + "name"): p for p in node.findall("prop")}
        if "URL" not in props or "Context" not in props:
            continue
        if section not in _ancestors(root, node):
            continue
        titles = {(v.get(XML + "lang") or ""): (v.text or "") for v in props["Title"].findall("value")}
        contexts = set(props["Context"].find("value").text.split(","))
        result.setdefault(props["URL"].find("value").text, []).append((titles, contexts))
    return result


def _ancestors(root, target):
    path = []

    def walk(node, trail):
        if node is target:
            path.extend(trail)
            return True
        return any(walk(child, trail + [node.get(OOR + "name")]) for child in node.findall("node"))
    walk(root, [])
    return path


class MenuContractTest(unittest.TestCase):
    def test_nd30_is_offered_everywhere_in_vietnamese(self):
        menu = items("OfficeMenuBar")["org.hst.office.vi:Nd30Wizard"][0]
        self.assertTrue((ALL | {"com.sun.star.frame.StartModule"}) <= menu[1])
        self.assertEqual({v for v in menu[0].values()}, {"Văn bản hành chính"})
        self.assertEqual(set(menu[0]), {"", "en-US", "vi"})

    def test_every_hst_label_is_vietnamese_except_the_update_check(self):
        for section in ("OfficeMenuBar",):
            for url, entries in items(section).items():
                for titles, _ in entries:
                    if url == UPDATE:
                        self.assertEqual(titles["en-US"], "Check for Updates…")
                        self.assertEqual(titles["vi"], "Kiểm tra cập nhật")
                    else:
                        self.assertEqual(titles["en-US"], titles["vi"], url)

    def test_vietnamese_labels_have_no_trailing_ellipsis(self):
        # Owner rule 2026-11-06: no "..."/"…" unless the text is cut, in the HST menu and on the ribbon alike
        # (scripts/l10n/vi_ellipsis.py). Only the English "Check for Updates…" of the English UI keeps it.
        root = ET.parse(os.path.join(EXT, "Addons.xcu")).getroot()
        for value in root.iter("value"):
            text, lang = value.text or "", value.get(XML + "lang") or ""
            if lang == "en-US" and text.replace("…", "").isascii() or not text.strip():
                continue
            self.assertFalse(text.rstrip().endswith(("...", "…")), text)
        menu = items("OfficeMenuBar")
        for name in ("ConvertEncoding", "ImportCsv", "ShowSolutions"):
            self.assertFalse(menu["org.hst.office.vi:" + name][0][0]["vi"].endswith(("...", "…")), name)

    def test_csv_import_is_offered_in_every_module(self):
        self.assertTrue(ALL <= items("OfficeMenuBar")["org.hst.office.vi:ImportCsv"][0][1])

    def test_moved_commands_stay_in_the_hst_menu_and_none_in_an_addon_ribbon_row(self):
        # Macro VBA (Developer tab), the UI language (Review tab), USB Token (File ▸ Info) and the update
        # check (Help) sit where Office has them; the HST menu still offers all of them. The Extensions tab
        # is authored in notebookbar.ui (hst-ribbon-extensions-tab.patch), so Addons.xcu adds no ribbon row.
        vi = "org.hst.office.vi:"
        self.assertEqual(items("OfficeNotebookBar"), {})
        menu = items("OfficeMenuBar")
        for url in (vi + "SetupUsbToken", vi + "EditVba", UPDATE, vi + "UILanguageVi", vi + "UILanguageEn",
                    vi + "UILanguageSystem"):
            self.assertIn(url, menu)
        self.assertIn(UPDATE, items("OfficeHelp"))

    def test_english_menu_strings_are_vietnamese(self):
        en, vi = (json.load(open(os.path.join(EXT, "locales", c + ".json"), encoding="utf-8")) for c in ("en", "vi"))
        self.assertEqual(en["menu"], vi["menu"])
        self.assertEqual(en["nd30"], vi["nd30"])
        self.assertEqual(en["undo"]["nd30"], vi["undo"]["nd30"])


if __name__ == "__main__":
    unittest.main()
