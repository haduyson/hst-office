# SPDX-License-Identifier: AGPL-3.0-only
"""Uniform layout of the ribbon groups (scripts/patches/ribbon_layout_rules.py, generate-ribbon-ux-uniform.py,
check-ribbon-layout.py; hst-ribbon-ux-uniform-layout.patch and hst-ribbon-ux-few-command-groups.patch).

Owner decision (13/11/2026): groups of few commands show large buttons filling the group's height; small stacks
only in groups of many commands, with no small button alone in its column. The rules run here on small groups;
on the real ribbons they run in the fresh-tree check (check-ribbon-layout.py --tree)."""
import importlib.util
import os
import sys
import unittest
import xml.etree.ElementTree as ET

from _paths import ROOT

PATCHES = os.path.join(ROOT, "patches", "libreoffice")
sys.path.insert(0, os.path.join(ROOT, "scripts", "patches"))
import ribbon_layout_rules as R  # noqa: E402


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, os.path.join(ROOT, path))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


gen = load("generate_ribbon_ux_uniform", "scripts/patches/generate-ribbon-ux-uniform.py")
check = load("check_ribbon_layout", "scripts/patches/check-ribbon-layout.py")


def toolbox(oid, left, top, commands=("A",), height=1, big=False):
    style = ('<property name="toolbar-style">both</property><property name="icon_size">3</property>' if big
             else '<property name="toolbar-style">both-horiz</property>')
    buttons = "".join(f'<child><object class="GtkToolButton" id="btn{oid}{c}"><property name="action-name">'
                      f'{c if c.startswith(".uno:") else ".uno:" + c}</property></object></child>' for c in commands)
    size = f'<property name="height">{height}</property>' if height != 1 else ""
    return (f'<child><object class="sfxlo-NotebookbarToolBox" id="{oid}">{style}{buttons}</object><packing>'
            f'<property name="left-attach">{left}</property><property name="top-attach">{top}</property>{size}'
            f'</packing></child>')


def ribbon(*cells, caption_top=2):
    return ET.fromstring(
        '<interface><object class="sfxlo-PriorityMergedHBox" id="pmhbHome"><child>'
        '<object class="GtkGrid" id="gdTest">' + "".join(cells) +
        '<child><object class="GtkLabel" id="lbTest"><property name="valign">end</property></object><packing>'
        f'<property name="left-attach">0</property><property name="top-attach">{caption_top}</property></packing>'
        '</child><child><object class="GtkSeparator"/><packing><property name="left-attach">2</property>'
        '<property name="top-attach">0</property><property name="height">3</property></packing></child>'
        '</object></child></object></interface>')


def cell(root, oid):
    hold = next(h for h in root.iter("child") if h.find("object") is not None and h.find("object").get("id") == oid)
    return {p.get("name"): p.text for p in hold.find("packing")}, hold.find("object")


class RulesTest(unittest.TestCase):
    def test_few_commands_must_be_large(self):
        root = ribbon(toolbox("bxA", 0, 0, height=2, big=True), toolbox("bxB", 1, 0), toolbox("bxC", 1, 1))
        [(group, rule, items, _)] = R.check_root(root)
        self.assertEqual((group.id, rule, [i.id for i in items]), ("gdTest", "few", ["bxB", "bxC"]))

    def test_controls_and_many_commands_are_not_few(self):
        combo = toolbox("bxFont", 0, 0, commands=(".uno:CharFontName",))
        self.assertEqual(R.check_root(ribbon(combo, toolbox("bxB", 1, 0), toolbox("bxC", 1, 1))), [])
        many = ribbon(toolbox("bxA", 0, 0, ("A", "B")), toolbox("bxB", 0, 1, ("C", "D")))
        self.assertEqual(R.check_root(many), [])

    def test_lone_small_button(self):
        root = ribbon(toolbox("bxA", 0, 0, ("A", "B")), toolbox("bxB", 0, 1, ("C", "D")), toolbox("bxE", 1, 0))
        self.assertEqual([(r, [i.id for i in items]) for _, r, items, _ in R.check_root(root)], [("lone", ["bxE"])])
        floating = ribbon(toolbox("bxA", 0, 0, ("A", "B")), toolbox("bxB", 0, 1, ("C", "D")),
                          toolbox("bxE", 1, 0, height=2))
        self.assertEqual([r for _, r, _, _ in R.check_root(floating)], ["lone"])
        spanned = ribbon(toolbox("bxA", 0, 0, ("A", "B")), toolbox("bxB", 0, 1, ("C", "D")), toolbox("bxE", 1, 0),
                         toolbox("bxF", 1, 1, ("F", "G")))
        self.assertEqual(R.check_root(spanned), [])


class GeneratorTest(unittest.TestCase):
    def test_few_commands_become_one_row_of_large_buttons(self):
        root = ribbon(toolbox("bxB", 0, 1), toolbox("bxA", 0, 0), toolbox("bxC", 1, 0), caption_top=1)
        self.assertEqual(gen.apply_rules(root), 1)
        self.assertEqual(R.check_root(root), [])
        for left, oid in enumerate(("bxA", "bxB", "bxC")):
            pack, obj = cell(root, oid)
            self.assertEqual((pack["left-attach"], pack["top-attach"], pack["height"]), (str(left), "0", "2"))
            self.assertEqual(R.prop(obj, "icon_size"), "3")
        pack, _ = cell(root, "lbTest")
        self.assertEqual((pack["top-attach"], pack["width"]), ("2", "3"))

    def test_lone_button_becomes_large(self):
        root = ribbon(toolbox("bxA", 0, 0, ("A", "B")), toolbox("bxB", 0, 1, ("C", "D")), toolbox("bxE", 1, 1))
        gen.apply_rules(root)
        pack, obj = cell(root, "bxE")
        self.assertEqual((pack["top-attach"], pack["height"]), ("0", "2"))
        self.assertEqual(R.prop(obj, "toolbar-style"), "both")
        self.assertEqual(R.check_root(root), [])

    def test_ladder_patch_follows_grow_order(self):
        with open(os.path.join(PATCHES, "series"), encoding="utf-8") as handle:
            series = [line.strip() for line in handle if line.strip() and not line.startswith("#")]
        # both edit HstRibbonLadder.cxx; the layout generator reads the tree after every app generator
        self.assertLess(series.index("hst-ribbon-ux-grow-order.patch"),
                        series.index("hst-ribbon-ux-few-command-groups.patch"))
        for name in ("hst-ribbon-ux-writer.patch", "hst-ribbon-ux-calc.patch", "hst-ribbon-ux-impress-draw.patch"):
            self.assertLess(series.index(name), series.index("hst-ribbon-ux-uniform-layout.patch"))

    def test_ladder_keeps_few_commands_large(self):
        with open(os.path.join(PATCHES, "hst-ribbon-ux-few-command-groups.patch"), encoding="utf-8") as handle:
            text = handle.read()
        self.assertIn(f"+constexpr int FEW_COMMANDS = {R.FEW_COMMANDS};", text)
        # large at every state; only the labels go at the small state, a step before the group folds
        self.assertIn("+    const bool bLabels = rData.mbHstKeepLarge || nState < GroupSmall;", text)
        self.assertIn("|| (bFewCommands && rData.meHstAuthoredSize == ToolBoxButtonSize::Large);", text)


class BannerShotTest(unittest.TestCase):
    def setUp(self):
        try:
            from PIL import Image, ImageDraw
        except ImportError:
            self.skipTest("Pillow is not installed")
        self.Image, self.Draw = Image, ImageDraw

    def shot(self, banner):
        image = self.Image.new("RGB", (1366, 250), (246, 245, 244))
        draw = self.Draw.Draw(image)
        draw.rectangle((0, 45, 1366 - 10 - banner, 165), fill=(255, 255, 255))
        if banner:
            draw.rectangle((1366 - 5 - banner, 66, 1366 - 6, 140), fill=(240, 247, 252))
            draw.text((1366 - banner, 90), "HASON TECH", fill=(30, 60, 90))
        return image

    def test_free_room(self):
        image = self.shot(260)
        draw = self.Draw.Draw(image)
        draw.rectangle((10, 70, 700, 140), fill=(40, 40, 40))  # the groups end at x 700
        self.assertAlmostEqual(check.free_room(image), 1366 - 10 - 260 - 700, delta=3)

    def test_banner_width(self):
        self.assertGreaterEqual(check.banner_width(self.shot(260)), 255)
        self.assertEqual(check.banner_width(self.shot(0)), 0)


if __name__ == "__main__":
    unittest.main()
