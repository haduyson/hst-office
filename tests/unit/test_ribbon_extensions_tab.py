# SPDX-License-Identifier: AGPL-3.0-only
"""The authored Extensions tab ("Phần mở rộng") of hst-ribbon-extensions-tab.patch, as the owner approved it.

Every group, caption, button label (two lines), command URL, icon and the split-button menu of each app are read
from the groups the patch adds to the three notebookbar.ui files. The HST icon themes must have every icon, light
and dark; Addons.xcu must not add the same tools again (they would show twice, once as a text row).
"""
import importlib.util
import os
import re
import unittest
import xml.etree.ElementTree as ET

from _paths import ROOT

PATCH = os.path.join(ROOT, "patches", "libreoffice", "hst-ribbon-extensions-tab.patch")
VI = "org.hst.office.vi:"
UI = {
    "writer": "sw/uiconfig/swriter/ui/notebookbar.ui",
    "calc": "sc/uiconfig/scalc/ui/notebookbar.ui",
    "impress": "sd/uiconfig/simpress/ui/notebookbar.ui",
}
ND30 = ("Văn bản\nhành chính", "Nd30Wizard", "nd30wizard")
SOLUTIONS = ("HASON TECH", [("Giải pháp\nHASON TECH", "ShowSolutions", "showsolutions")])
# app -> [(caption, [(label, command, icon)])]
LAYOUT = {
    "writer": [
        ("Văn bản tiếng Việt", [ND30, ("Chuyển mã\nsang Unicode", "ConvertEncoding", "convertencoding"),
                                ("Đổi số\nthành chữ", "NumberToWords", "numbertowords")]),
        SOLUTIONS,
    ],
    "calc": [
        ("Văn bản", [ND30]),
        ("Định dạng Việt Nam", [("Định dạng\nngày tháng", "FormatDate", "formatdate"),
                                ("Tiền\nVND", "FormatVnd", "formatvnd"),
                                ("Phần\ntrăm", "FormatPercent", "formatpercent")]),
        ("Dữ liệu", [("Nhập CSV\n(UTF-8)", "ImportCsv", "importcsv")]),
        ("Tiện ích tiếng Việt", [("Đọc số\nthành chữ", "NumberToWords", "numbertowords"),
                                 ("Bỏ\ndấu", "RemoveDiacritics", "removediacritics"),
                                 ("Tách\nhọ tên", "SplitName", "splitname"),
                                 ("Sắp xếp\ntheo tên", "SortByGivenName", "sortbygivenname"),
                                 ("Xóa dòng\ntrống", "DeleteBlankRows", "deleteblankrows")]),
        SOLUTIONS,
    ],
    "impress": [("Văn bản", [ND30]), SOLUTIONS],
}
SPLIT = {"calc": "FormatDate"}
DATE_MENU = [("FormatDate", "dd/mm/yyyy"), ("FormatDateLong", "ngày dd tháng mm năm yyyy"),
             ("FormatMonthYear", "tháng mm năm yyyy"), ("FormatDateDash", "dd-mm-yyyy")]


def sections():
    """{path: [lines of the file's diff]} of the patch."""
    result, current = {}, None
    with open(PATCH, encoding="utf-8") as handle:
        for line in handle.read().splitlines():
            match = re.match(r"^\+\+\+ b/(\S+)", line)
            if match:
                current = result.setdefault(match.group(1), [])
            elif current is not None:
                current.append(line)
    return result


def added_groups(lines):
    """The tab's group grids, cut from the new side of the file's first hunk and parsed as XML."""
    new, hunks = [], 0
    for line in lines:
        if line.startswith("@@"):
            hunks += 1
            if hunks > 1:
                break
        elif hunks == 1 and not line.startswith("-"):
            new.append(line[1:])
    grids, depth, current = [], 0, None
    for line in new:
        if current is None and 'class="GtkGrid" id="gdExtensionHst' in line:
            current, depth = [], 0
        if current is None:
            continue
        current.append(line)
        depth += line.count("<object ") - line.count("</object>")
        if depth == 0:
            grids.append(ET.fromstring("\n".join(current)))
            current = None
    return grids


def prop(node, name):
    found = node.find(f"property[@name='{name}']")
    return None if found is None else found.text


def tab(app):
    groups = []
    for grid in added_groups(sections()[UI[app]]):
        caption = next(o for o in grid.iter("object") if o.get("class") == "GtkLabel")
        buttons = [o for o in grid.iter("object") if o.get("class") in ("GtkToolButton", "GtkMenuToolButton")]
        groups.append((grid, caption, buttons))
    return groups


class ExtensionsTabTest(unittest.TestCase):
    def test_groups_buttons_labels_and_commands_of_each_app(self):
        for app, layout in LAYOUT.items():
            with self.subTest(app=app):
                groups = tab(app)
                self.assertEqual([prop(caption, "label") for _, caption, _ in groups], [c for c, _ in layout])
                for (grid, caption, buttons), (_, expected) in zip(groups, layout):
                    self.assertEqual([(prop(b, "label"), prop(b, "action-name"), prop(b, "icon-name")) for b in buttons],
                                     [(label, VI + command, f"cmd/32/{icon}.png") for label, command, icon in expected])
                    box = next(o for o in grid.iter("object") if o.get("class") == "sfxlo-NotebookbarToolBox")
                    self.assertEqual((prop(box, "toolbar-style"), prop(box, "icon_size")), ("both", "5"))  # 32 px, text below
                    self.assertIsNotNone(next((o for o in grid.iter("object") if o.get("class") == "GtkSeparator"), None))
                    self.assertIsNone(caption.find("property[@name='label']").get("translatable"))

    def test_labels_have_two_lines_no_ellipsis_and_a_tooltip(self):
        for app in LAYOUT:
            for _, _, buttons in tab(app):
                for button in buttons:
                    label = prop(button, "label")
                    self.assertEqual(label.count("\n"), 1, label)
                    self.assertFalse(label.endswith(("...", "…")), label)
                    self.assertTrue(prop(button, "tooltip-text"), label)
                    self.assertNotIn("\n", prop(button, "tooltip-text"))

    def test_ids_are_unique_and_new_in_each_file(self):
        for app, path in UI.items():
            ids = [o.get("id") for grid in added_groups(sections()[path]) for o in grid.iter("object")]
            self.assertEqual(len(ids), len(set(ids)), app)
            self.assertTrue(all(i.startswith(("gdExtensionHst", "bxExtensionHst", "btnExtensionHst",
                                              "lbExtensionHst", "sepExtensionHst")) for i in ids), ids)

    def test_date_split_button_and_its_menu(self):
        for app in LAYOUT:
            split = [prop(b, "action-name") for _, _, bs in tab(app) for b in bs if b.get("class") == "GtkMenuToolButton"]
            self.assertEqual(split, [VI + SPLIT[app]] if app in SPLIT else [], app)
        menu = "\n".join(l[1:] for l in sections()["sc/uiconfig/scalc/popupmenu/hstformatdate.xml"] if l.startswith("+"))
        root = ET.fromstring(menu[menu.index("<menu:menupopup"):])
        ns = "{http://openoffice.org/2001/menu}"
        self.assertEqual([(i.get(ns + "id"), i.get(ns + "label")) for i in root],
                         [(VI + command, label) for command, label in DATE_MENU])
        controller = "\n".join(sections()["officecfg/registry/data/org/openoffice/Office/UI/Controller.xcu"])
        self.assertRegex(controller, r"(?s)<value>org\.hst\.office\.vi:FormatDate</value>.*"
                                     r"SpreadsheetDocument</value>.*GenericPopupToolbarController</value>.*"
                                     r"<value>private:resource/popupmenu/hstformatdate</value>")
        self.assertIn("+\tsc/uiconfig/scalc/popupmenu/hstformatdate \\", sections()["sc/UIConfig_scalc.mk"])

    def test_third_party_add_ons_keep_their_merge_point_after_the_groups(self):
        for app, path in UI.items():
            text = "\n".join(sections()[path])
            # Writer has the merge point in its upstream "Extension" box, Sheets and Slides in pmhbExtensionAddons.
            self.assertRegex(text, r'\n[ +][^\n]*<object class="(NotebookBarAddonsToolMergePoint" id="AddonCommand|'
                                   r'sfxlo-PriorityMergedHBox" id="Extension)">', app)
            self.assertRegex(text, rf'\+\s*<property name="position">{len(LAYOUT[app])}</property>', app)

    def test_every_icon_is_in_both_hst_themes(self):
        spec = importlib.util.spec_from_file_location("hst_theme", os.path.join(ROOT, "scripts/brand/build-hst-icon-theme.py"))
        builder = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(builder)
        icons = {f"cmd/32/{icon}.png" for layout in LAYOUT.values() for _, buttons in layout for _, _, icon in buttons}
        for theme in builder.PALETTES:
            files = builder.resources(theme)
            links = dict(l.split() for l in files["links.txt"].decode().splitlines() if not l.startswith("#"))
            for icon in icons:
                self.assertIn(links.get(icon, icon), files, (theme, icon))

    def test_addons_no_longer_add_a_text_row_to_the_tab(self):
        root = ET.parse(os.path.join(ROOT, "extensions/hst-vietnamese-tools/Addons.xcu")).getroot()
        oor = "{http://openoffice.org/2001/registry}"
        self.assertEqual([n for n in root.iter("node") if n.get(oor + "name") == "OfficeNotebookBar"], [])


if __name__ == "__main__":
    unittest.main()
