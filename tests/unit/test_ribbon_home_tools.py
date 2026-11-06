# SPDX-License-Identifier: AGPL-3.0-only
"""Home tab of hst-ribbon-home-fit.patch: the "Công cụ" group, Find & Replace in the paragraph group, the feature
search in the "Trang đầu" menu, Sheets' stacked Styles buttons and the style gallery's narrow minimum.

The groups are read from the new side of each notebookbar.ui diff; the Vietnamese caption from the .po hunks.
"""
import os
import re
import unittest
import xml.etree.ElementTree as ET

from _paths import ROOT

PATCH = os.path.join(ROOT, "patches", "libreoffice", "hst-ribbon-home-fit.patch")
UI = {
    "Writer": "sw/uiconfig/swriter/ui/notebookbar.ui",
    "Calc": "sc/uiconfig/scalc/ui/notebookbar.ui",
    "Impress": "sd/uiconfig/simpress/ui/notebookbar.ui",
}
PO = {"Writer": "sw", "Calc": "sc", "Impress": "sd"}
# rows of the "Công cụ" group under the tab menu: (commands of the row)
SECOND_ROW = {"Writer": ["org.hst.office.vi:Nd30Wizard"], "Calc": [".uno:SortAscending", ".uno:DataFilterAutoFilter"],
              "Impress": [".uno:Presentation"]}
INDENT_ROW = {"Writer": "bxHomeIndentation", "Calc": "bxHomeSpacingIndentation", "Impress": "bxHomeIndentation"}


def sections():
    result, current = {}, None
    with open(PATCH, encoding="utf-8") as handle:
        for line in handle.read().splitlines():
            match = re.match(r"^\+\+\+ b/(\S+)", line)
            if match:
                current = result.setdefault(match.group(1), [])
            elif current is not None:
                current.append(line)
    return result


def element(lines, marker):
    """The XML element whose start tag holds `marker`, cut from the new side of the hunks."""
    new = [l[1:] for l in lines if not l.startswith(("-", "@@"))]
    start = next(i for i, l in enumerate(new) if marker in l)
    tag = re.match(r"\s*<(\w+)", new[start]).group(1)
    depth = 0
    for end in range(start, len(new)):
        depth += new[end].count(f"<{tag} ") + new[end].count(f"<{tag}>") - new[end].count(f"</{tag}>")
        if depth == 0:
            return ET.fromstring("\n".join(new[start:end + 1]))
    raise AssertionError(marker)


def actions(node):
    return [p.text for p in node.iter("property") if p.get("name") == "action-name"]


class HomeToolsTest(unittest.TestCase):
    def test_tools_group_rows_and_caption(self):
        for app, path in UI.items():
            with self.subTest(app=app):
                grid = element(sections()[path], 'id="gdHomeHstTools"')
                rows = {}
                for child in grid.findall("child"):
                    obj = child.find("object")
                    row = int(child.find("packing/property[@name='top-attach']").text)
                    rows[row] = obj
                self.assertEqual(rows[0].get("id"), "Home-HomeButton:Menu Home")
                self.assertEqual(actions(rows[1]), SECOND_ROW[app])
                self.assertEqual(actions(rows[2]), [".uno:CommandPopup"])
                search = rows[2].find(".//object[@id='Home-HstFeatureSearch']")
                self.assertEqual(search.find("property[@name='label']").text, "Tìm tính năng")
                caption = rows[3].find("property[@name='label']")
                self.assertEqual((caption.text, caption.get("context")), ("Tools", f"Tabbed{app}|labelHomeHstTools"))
                self.assertNotIn(".uno:SearchDialog", actions(grid))
                po = "\n".join(sections()[f"translations/source/vi/{PO[app]}/messages.po"])
                self.assertIn(f'+msgctxt "Tabbed{app}|labelHomeHstTools"\n+msgid "Tools"\n+msgstr "Công cụ"', po)

    def test_find_and_replace_follows_the_indent_buttons(self):
        for app, path in UI.items():
            box = element(sections()[path], f'id="{INDENT_ROW[app]}"')
            commands = actions(box)
            self.assertEqual(commands[-1] if app != "Calc" else commands[commands.index(".uno:DecrementIndent") + 1],
                             ".uno:SearchDialog", (app, commands))

    def test_feature_search_in_the_tab_menu(self):
        for app, path in UI.items():
            lines = sections()[path]
            added = [i for i, l in enumerate(lines) if 'id="MenuHome-HstFeatureSearch"' in l]
            self.assertEqual(len(added), 1, app)
            before = next(l for l in reversed(lines[:added[0]]) if 'id="Menu' in l)
            self.assertIn('id="MenuHome-', before, app)  # an item of the "Trang đầu" menu precedes it
            self.assertIn(".uno:CommandPopup", "\n".join(lines[added[0]:added[0] + 4]))

    def test_sheets_styles_are_two_small_buttons_stacked(self):
        grid = element(sections()[UI["Calc"]], 'id="gdHomeStyles"')
        boxes = {o.get("id"): o for o in grid.iter("object") if o.get("class") == "sfxlo-NotebookbarToolBox"}
        for tid in ("bxHomeConditionalFormatMenu", "bxLayoutAutoFormat"):
            props = {p.get("name"): p.text for p in boxes[tid].findall("property")}
            self.assertEqual((props["toolbar-style"], props["icon_size"]), ("both-horiz", "1"), tid)
        rows = sorted(int(c.find("packing/property[@name='top-attach']").text) for c in grid.findall("child")
                      if c.find("object").get("id") in boxes)
        self.assertEqual(rows, [0, 1])

    def test_style_gallery_needs_one_preview_and_a_narrow_button_column(self):
        ui = "\n".join(l[1:] for l in sections()["svx/uiconfig/ui/stylespreview.ui"] if not l.startswith(("-", "@@")))
        self.assertIn('<property name="min-content-width">106</property>', ui)
        column = ui[ui.index('id="stylesbuttons"'):]
        self.assertIn('<property name="orientation">vertical</property>', column[:400])
        for bid in ("prevstyles", "nextstyles", "morestyles"):
            self.assertIn(f'id="{bid}"', column)
        self.assertEqual(column.count('<property name="height-request">20</property>'), 3)


if __name__ == "__main__":
    unittest.main()
