# SPDX-License-Identifier: AGPL-3.0-only
"""The Sheets conditional formatting dropdown (hst-calc-conditional-format-menu.patch), read from the patch.

Owner request of 2026-11-13: the Home button "Định dạng có điều kiện ▾" and Format ▸ Conditional show the
familiar office suite's menu (highlight cells rules, top/bottom rules, data bars, color scales, icon sets,
new rule, clear rules, manage rules). Every item has a command label, Vietnamese text with one access key
per submenu and no trailing ellipsis, and the clear command is a real slot.
"""
import os
import re
import unittest
import xml.etree.ElementTree as ET

from _paths import ROOT

PATCH = os.path.join(ROOT, "patches", "libreoffice", "hst-calc-conditional-format-menu.patch")
MENU_XML = "sc/uiconfig/scalc/popupmenu/conditional.xml"
XCU = "officecfg/registry/data/org/openoffice/Office/UI/CalcCommands.xcu"
UI_PO = "translations/source/vi/officecfg/registry/data/org/openoffice/Office/UI.po"
SC_PO = "translations/source/vi/sc/messages.po"
MENU = "{http://openoffice.org/2001/menu}"
EASY = ".uno:ConditionalFormatEasy?FormatRule:short="
# Commands whose CalcCommands.xcu nodes are upstream; the patch only translates them.
UPSTREAM = {EASY + n for n in ("0", "1", "2", "6", "23")} | {
    ".uno:CondDateFormatDialog", ".uno:ConditionalFormatDialog", ".uno:ConditionalFormatManagerDialog"}


def sections():
    result, current = {}, None
    with open(PATCH, encoding="utf-8") as handle:
        for line in handle.read().splitlines():
            match = re.match(r"^\+\+\+ b/(\S+)", line)
            if match:
                current = result.setdefault(match.group(1), [])
            elif current is not None and not line.startswith("--- "):
                current.append(line)
    return result


def added(path):
    return "\n".join(line[1:] for line in sections()[path] if line.startswith("+"))


def after(path):
    return "\n".join(line[1:] for line in sections()[path] if line[:1] in (" ", "+"))


def vi_labels():
    """{(section, command, property): msgstr} of the CalcCommands entries the patch writes."""
    entry = re.compile(r'"\.\.CalcCommands\.UserInterface\.(\w+)\.(\.uno:[^"\\]+)\\n"\n"(\w+)\\n"\n'
                       r'"value\.text"\nmsgid "([^"]*)"\nmsgstr "([^"]*)"')
    return {(m.group(1), m.group(2), m.group(3)): m.group(5) for m in entry.finditer(after(UI_PO))}


def menu():
    text = after(MENU_XML)  # the hunk starts inside the license comment
    return ET.fromstring(text[text.index("<menu:menupopup "):])


def menu_label(labels, command, section="Commands"):
    return labels.get((section, command, "ContextLabel")) or labels.get((section, command, "Label"))


class ConditionalFormatMenuTest(unittest.TestCase):
    def test_top_level_order(self):
        ids = [(node.tag[len(MENU):], node.get(MENU + "id")) for node in menu() if node.tag != MENU + "menuseparator"]
        self.assertEqual(ids, [
            ("menu", ".uno:HstConditionalFormatHighlightMenu"), ("menu", ".uno:HstConditionalFormatTopBottomMenu"),
            ("menu", ".uno:HstConditionalFormatDataBarMenu"), ("menu", ".uno:HstConditionalFormatColorScaleMenu"),
            ("menu", ".uno:HstConditionalFormatIconSetMenu"), ("menuitem", ".uno:ConditionalFormatDialog"),
            ("menu", ".uno:HstConditionalFormatClearMenu"), ("menuitem", ".uno:ConditionalFormatManagerDialog")])

    def test_highlight_and_top_bottom_items(self):
        submenus = {node.get(MENU + "id"): [item.get(MENU + "id") for item in node.iter(MENU + "menuitem")]
                    for node in menu() if node.tag == MENU + "menu"}
        self.assertEqual(submenus[".uno:HstConditionalFormatHighlightMenu"],
                         [EASY + "2", EASY + "1", EASY + "6", EASY + "0", EASY + "23", ".uno:CondDateFormatDialog",
                          EASY + "8"])
        self.assertEqual(submenus[".uno:HstConditionalFormatTopBottomMenu"],
                         [EASY + n for n in ("11", "13", "12", "14", "15", "16")])
        self.assertEqual(submenus[".uno:HstConditionalFormatClearMenu"],
                         [".uno:HstConditionalFormatClear?Scope:short=0", ".uno:HstConditionalFormatClear?Scope:short=1"])
        for name in ("DataBar", "ColorScale", "IconSet"):
            with self.subTest(submenu=name):
                items = submenus[f".uno:HstConditionalFormat{name}Menu"]
                self.assertEqual(items[-1].split("?")[1], "IconSet:short=-1")  # "More Rules" opens the dialog

    def test_every_command_has_a_label_and_vietnamese_text(self):
        xcu, labels = added(XCU), vi_labels()
        for node in menu().iter():
            command = node.get(MENU + "id")
            if not command:
                continue
            section = "Popups" if node.tag == MENU + "menu" else "Commands"
            with self.subTest(command=command):
                if command not in UPSTREAM:
                    self.assertIn(f'<node oor:name="{command}" oor:op="replace">', xcu)
                text = menu_label(labels, command, section)
                self.assertTrue(text, "no Vietnamese menu text")
                self.assertFalse(text.endswith(("...", "…")), text)

    def test_vietnamese_terms(self):
        labels = vi_labels()
        expected = {
            ".uno:HstConditionalFormatHighlightMenu": "Quy tắc tô ~sáng ô", EASY + "2": "~Lớn hơn",
            EASY + "1": "~Nhỏ hơn", EASY + "6": "~Trong khoảng", EASY + "0": "~Bằng", EASY + "23": "~Văn bản chứa",
            ".uno:CondDateFormatDialog": "Ngày ~xảy ra", EASY + "8": "~Giá trị trùng lặp",
            ".uno:HstConditionalFormatTopBottomMenu": "Quy tắc ~trên/dưới", EASY + "11": "10 ~mục lớn nhất",
            EASY + "13": "10% ~lớn nhất", EASY + "12": "10 mục ~nhỏ nhất", EASY + "14": "10% n~hỏ nhất",
            EASY + "15": "~Trên trung bình", EASY + "16": "~Dưới trung bình",
            ".uno:HstConditionalFormatDataBarMenu": "Thanh ~dữ liệu", ".uno:HstConditionalFormatColorScaleMenu": "Thang ~màu",
            ".uno:HstConditionalFormatIconSetMenu": "~Bộ biểu tượng", ".uno:ConditionalFormatDialog": "~Quy tắc mới",
            ".uno:HstConditionalFormatClearMenu": "~Xóa quy tắc",
            ".uno:HstConditionalFormatClear?Scope:short=0": "Khỏi ~vùng chọn",
            ".uno:HstConditionalFormatClear?Scope:short=1": "Khỏi cả ~trang tính",
            ".uno:ConditionalFormatManagerDialog": "Quản ~lý quy tắc"}
        for command, text in expected.items():
            section = "Popups" if command.endswith("Menu") else "Commands"
            with self.subTest(command=command):
                self.assertEqual(menu_label(labels, command, section), text)

    def test_access_keys_are_unique_ascii_per_submenu(self):
        labels = vi_labels()

        def check(container, path):
            keys = {}
            for node in container:
                command = node.get(MENU + "id")
                if not command:
                    continue
                section = "Popups" if node.tag == MENU + "menu" else "Commands"
                text = menu_label(labels, command, section)
                if "~" in text:
                    key = text[text.index("~") + 1]
                    self.assertTrue(key.isascii() and key.isalnum(), f"{path}: {text}")
                    self.assertNotIn(key.upper(), keys, f"{path}: {text} and {keys.get(key.upper())}")
                    keys[key.upper()] = text
                popup = node.find(MENU + "menupopup")
                if popup is not None:
                    check(popup, path + " > " + text)
        check(menu(), "conditional")

    def test_clear_rules_is_a_slot_with_undo(self):
        self.assertIn("#define SID_HST_CONDFORMAT_CLEAR", added("sc/inc/sc.hrc"))
        self.assertIn("SfxVoidItem HstConditionalFormatClear SID_HST_CONDFORMAT_CLEAR\n(SfxInt16Item Scope FN_PARAM_1)",
                      added("sc/sdi/scalc.sdi"))
        self.assertIn("SID_HST_CONDFORMAT_CLEAR", added("sc/sdi/cellsh.sdi"))
        code = added("sc/source/ui/view/cellsh3.cxx")
        self.assertIn("case SID_HST_CONDFORMAT_CLEAR:", code)
        self.assertIn("GetDocFunc().SetConditionalFormatList(", code)  # ScUndoConditionalFormatList
        self.assertIn("STR_ERR_CONDFORMAT_PROTECTED", code)

    def test_duplicate_rule_defaults_to_light_red_and_switches_to_unique(self):
        dialog = added("sc/source/ui/condformat/condformateasydlg.cxx")
        self.assertIn("{ STR_HST_CONDFORMAT_STYLE_LIGHT_RED, Color(0xFFC7CE), Color(0x9C0006) }", dialog)
        self.assertIn("mxStyles->set_active(0);", dialog)
        self.assertIn("ScConditionMode::NotDuplicate", dialog)
        self.assertIn('id="unique"', added("sc/uiconfig/scalc/ui/conditionaleasydialog.ui"))
        po = after(SC_PO)
        for msgid, msgstr in (("Light Red Fill with Dark Red Text", "Nền đỏ nhạt, chữ đỏ đậm"),
                              ("Duplicate", "Trùng lặp"), ("Unique", "Duy nhất"),
                              ("Highlight cells with %1", "Tô sáng các ô có %1")):
            self.assertIn(f'msgid "{msgid}"\nmsgstr "{msgstr}"', po)

    def test_no_foreign_product_names_or_banned_terms(self):
        text = "\n".join(added(path) for path in sections())
        for banned in ("Vĩ lệnh", "Excel", "Microsoft", "LibreOffice", "Huỷ", "Xoá", "tập tin"):
            with self.subTest(term=banned):
                self.assertNotIn(banned, text)


if __name__ == "__main__":
    unittest.main()
