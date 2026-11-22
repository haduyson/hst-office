# SPDX-License-Identifier: LicenseRef-HST-Proprietary
# Copyright (C) 2026 HASON TECH
"""Large ribbon buttons show 24 px images (owner rule: every large button but Paste).

The rule itself (scripts/patches/check-ribbon-large-icons.py) is tested on small documents; the patches are
checked for the images they name. With HST_LO_TREE set to a tree with the whole series applied, the four
notebookbar.ui files are scanned too (as check-ribbon-large-icons.py --tree does). The HST styles draw every
named glyph at 24 px (tests/brand/test-hst-icon-theme.py); the classic style layers them over Colibre."""
import importlib.util
import os
import unittest
import xml.etree.ElementTree as ET

from _paths import ROOT
from patch_sections import added, removed

spec = importlib.util.spec_from_file_location("large_icons", os.path.join(ROOT, "scripts/patches/check-ribbon-large-icons.py"))
large_icons = importlib.util.module_from_spec(spec)
spec.loader.exec_module(large_icons)

WRITER = "sw/uiconfig/swriter/ui/notebookbar.ui"


def ribbon(*buttons):
    """A .ui document of toolboxes: (toolbox properties, button class, button properties)."""
    def props(items):
        return "".join(f'<property name="{k}">{v}</property>' for k, v in items.items())
    boxes = "".join(f'<child><object class="sfxlo-NotebookbarToolBox" id="bx{n}">{props(box)}<child>'
                    f'<object class="{klass}" id="btn{n}">{props(own)}</object></child></object></child>'
                    for n, (box, klass, own) in enumerate(buttons))
    return ET.fromstring(f'<interface><object class="GtkGrid" id="grid">{boxes}</object></interface>')


class RuleTest(unittest.TestCase):
    def test_large_buttons_name_24px_images(self):
        root = ribbon(({"toolbar-style": "both", "icon_size": "3"}, "GtkToolButton",
                       {"action-name": ".uno:A", "icon-name": "cmd/lc_a.png"}),
                      ({"toolbar-style": "both", "icon_size": "3"}, "GtkToolButton",
                       {"action-name": ".uno:B", "icon-name": "cmd/32/b.png"}),
                      ({"toolbar-style": "both", "icon_size": "3"}, "GtkToolButton",
                       {"action-name": ".uno:C", "icon-name": "cmd/sc_c.png"}),
                      ({"toolbar-style": "both", "icon_size": "5"}, "GtkToolButton", {"action-name": ".uno:D"}),
                      ({"toolbar-style": "icons"}, "GtkToolButton", {"action-name": ".uno:E", "icon-name": "cmd/sc_e.png"}))
        self.assertEqual([button for button, _, _ in large_icons.violations(root)], ["btn1", "btn2", "btn3"])

    def test_large_menu_buttons_show_24px_images(self):
        root = ET.fromstring(
            '<interface><object class="GtkImage" id="imgBig"><property name="icon-name">cmd/32/x.png</property></object>'
            '<object class="GtkImage" id="imgOk"><property name="icon-name">cmd/lc_x.png</property></object>'
            '<object class="GtkImage" id="imgSmall"><property name="icon-name">cmd/sc_x.png</property></object>'
            '<object class="svtlo-ManagedMenuButton" id="btnBig"><property name="image">imgBig</property>'
            '<property name="image-position">top</property></object>'
            '<object class="svtlo-ManagedMenuButton" id="btnOk"><property name="image">imgOk</property>'
            '<property name="image-position">top</property></object>'
            '<object class="svtlo-ManagedMenuButton" id="btnSmall"><property name="image">imgSmall</property>'
            '<property name="image-position">left</property></object></interface>')
        self.assertEqual([button for button, _, _ in large_icons.violations(root)], ["btnBig"])

    def test_paste_keeps_its_32px_image(self):
        root = ribbon(({"toolbar-style": "both", "icon_size": "5"}, "GtkMenuToolButton", {"action-name": ".uno:Paste"}))
        self.assertEqual(large_icons.violations(root), [])


class PatchTest(unittest.TestCase):
    def test_vietnamese_tools_of_writers_home_name_their_24px_images(self):
        new, old = added("hst-ribbon-mockup-writer.patch", WRITER), removed("hst-ribbon-mockup-writer.patch", WRITER)
        for name, before in {"nd30wizard": "cmd/32/nd30wizard.png", "convertencoding": "cmd/sc_convertencoding.png",
                             "numbertowords": "cmd/sc_numbertowords.png"}.items():
            self.assertIn(f'<property name="icon-name">cmd/lc_{name}.png</property>', new)
            self.assertIn(f'<property name="icon-name">{before}</property>', old)

    def test_the_other_large_buttons_of_the_four_ribbons_name_24px_images(self):
        patch = "hst-ribbon-large-icons-24.patch"
        for path in large_icons.RIBBONS.values():
            new, old = added(patch, path), removed(patch, path)
            self.assertNotIn("cmd/32/", new, path)
            self.assertNotIn('icon_size">5<', new, path)
            self.assertIn('icon_size">5<', old, path)  # every ribbon's Extensions tab was drawn at 32 px
        # glyphs no HST style draws, replaced by the nearest one every style draws
        self.assertIn("cmd/lc_helpindex.png", added(patch, WRITER))
        self.assertIn("cmd/lc_presentationcurrentslide.png", added(patch, large_icons.RIBBONS["Slides"]))
        # the large Shapes and Snap menu buttons of Slides and Draw
        for app in ("Slides", "Draw"):
            self.assertIn("cmd/lc_basicshapes.diamond.png", added(patch, large_icons.RIBBONS[app]))
        self.assertIn("cmd/lc_snapborder.png", added(patch, large_icons.RIBBONS["Draw"]))


@unittest.skipUnless(os.environ.get("HST_LO_TREE"), "HST_LO_TREE: a tree with the whole series applied")
class TreeTest(unittest.TestCase):
    def test_no_large_button_of_the_four_ribbons_is_off_24px(self):
        tree = os.environ["HST_LO_TREE"]
        for app, path in large_icons.RIBBONS.items():
            found = large_icons.violations(ET.parse(os.path.join(tree, path)).getroot())
            self.assertEqual(found, [], app)


if __name__ == "__main__":
    unittest.main()
