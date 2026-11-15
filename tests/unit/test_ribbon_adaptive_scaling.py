# SPDX-License-Identifier: AGPL-3.0-only
"""Banner width per window, ladder hysteresis (hst-ribbon-adaptive-scaling.patch) and the approved scaling
order of data/ribbon/adaptive-ladders.json (hst-ribbon-adaptive-ladders.patch)."""
import json
import os
import re
import shutil
import subprocess
import tempfile
import unittest

from _paths import ROOT
from patch_sections import added, sections

SCALING = "hst-ribbon-adaptive-scaling.patch"
LADDERS = "hst-ribbon-adaptive-ladders.patch"
GEOMETRY = "include/vcl/HstBannerGeometry.hxx"


def geometry_after():
    """The geometry header as hst-ribbon-adaptive-scaling.patch leaves it (its whole text is in the patch's
    context: the hunk covers the new function, the rest comes from the banner patch)."""
    banner = [line[1:] for line in sections("hst-banner-always-visible.patch")[GEOMETRY] if line.startswith("+")]
    with tempfile.TemporaryDirectory() as tree:
        os.makedirs(os.path.join(tree, os.path.dirname(GEOMETRY)))
        with open(os.path.join(tree, GEOMETRY), "w", encoding="utf-8") as handle:
            handle.write("\n".join(banner) + "\n")
        text = open(os.path.join(ROOT, "patches/libreoffice", SCALING), encoding="utf-8").read()
        part = re.split(r"(?m)^(?=--- a/)", text)
        hunk = "".join(p for p in part if p.startswith(f"--- a/{GEOMETRY}"))
        subprocess.run(["patch", "-d", tree, "-p1", "-s"], input=hunk, text=True, check=True)
        return open(os.path.join(tree, GEOMETRY), encoding="utf-8").read()


DRIVER = r"""
#include "HstBannerGeometry.hxx"
#include <cstdio>
int main()
{
    using namespace hst::banner;
    int f = 0;
    f += windowSlotWidth(1366, 1.0) != 260;
    f += windowSlotWidth(1440, 1.0) != 260;
    f += windowSlotWidth(1680, 1.0) != 310;
    f += windowSlotWidth(1920, 1.0) != 360;
    f += windowSlotWidth(2560, 1.0) != 360;
    f += windowSlotWidth(3840, 2.0) != 720; // 1920 logical px at 200 %
    f += windowSlotWidth(2732, 2.0) != 520;
    std::printf("%d failure(s)\n", f);
    return f;
}
"""


class BannerWidthPerWindow(unittest.TestCase):
    @unittest.skipUnless(shutil.which("g++") and shutil.which("patch"), "no C++ compiler or patch tool")
    def test_width_follows_the_window(self):
        with tempfile.TemporaryDirectory() as tmp:
            open(os.path.join(tmp, "HstBannerGeometry.hxx"), "w", encoding="utf-8").write(geometry_after())
            open(os.path.join(tmp, "d.cxx"), "w", encoding="utf-8").write(DRIVER)
            subprocess.run(["g++", "-std=c++17", "-o", os.path.join(tmp, "d"), os.path.join(tmp, "d.cxx")], check=True)
            run = subprocess.run([os.path.join(tmp, "d")], capture_output=True, text=True)
            self.assertEqual(run.returncode, 0, run.stdout)

    def test_tab_control_uses_it(self):
        code = added(SCALING, "sfx2/source/notebookbar/NotebookbarTabControl.cxx")
        self.assertIn("hst::banner::windowSlotWidth(", code)
        self.assertNotIn("PageFullWidth", code)

    def test_hysteresis(self):
        code = added(SCALING, "vcl/source/control/PriorityMergedHBox.cxx")
        self.assertIn("std::lround(12 * GetDPIScaleFactor())", code)
        self.assertIn("aLayout.states = m_aHstLastStates;", code)


def generated_ladders():
    """{(app, box): {"ladder", "gen", "steps": [[group, state]], "fold"}}: the explicit ladders as the data gives them,
    the rule ladders as the generator resolves them from the tab's groups (scaling-priorities.json, tab order)."""
    import importlib.util
    spec = importlib.util.spec_from_file_location(
        "gen_ladders", os.path.join(ROOT, "scripts/patches/generate-ribbon-adaptive-ladders.py"))
    gen = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(gen)
    groups = {(l["app"], l["box"].replace(" ", "_")): l["groups"] for l in json.load(open(
        os.path.join(ROOT, "data/ribbon/scaling-priorities.json"), encoding="utf-8"))["ladders"]}
    out = {}
    for ladder in json.load(open(os.path.join(ROOT, "data/ribbon/adaptive-ladders.json"), encoding="utf-8"))["ladders"]:
        key = (ladder["app"], ladder["box"])
        steps, fold = gen.rule_chain(groups[(key[0], key[1].replace(" ", "_"))]) if ladder.get("rule") else (ladder["steps"], ladder.get("fold"))
        out[key] = {"ladder": ladder, "gen": gen, "steps": steps, "fold": fold}
    return out


class ApprovedOrder(unittest.TestCase):
    """Ribbon 1.0.2 mockup (plan 261115-2225, phase 1): Writer's Home and Insert carry the mockup's steps, every
    other tab the mockup's rule (generate-ribbon-adaptive-ladders.py rule_chain)."""

    def test_patch_has_the_chains(self):
        text = added(LADDERS, "vcl/inc/HstRibbonLadders.hxx")
        states = {"M": 1, "S": 2, "C": 3}
        for (app, box), got in generated_ladders().items():
            steps = ", ".join(f'{{ u"{g}", {states[s]} }}' for g, s in got["steps"])
            name = app + "_" + re.sub(r"\W", "_", box)
            line = f"inline constexpr Step {name}_steps[] = {{ {steps} }};"
            # a chain the patch leaves as the series had it is not an added line
            if f"Step {name}_steps[]" in text:
                self.assertIn(line, text, (app, box))

    def test_writer_home_and_insert_are_the_mockups(self):
        ladders = generated_ladders()
        insert = ladders[("writer", "pmhbInsert")]["steps"]
        self.assertNotIn(["gdInsertText", "M"], insert)  # the mockup's Text group: L, S, C
        self.assertLess(insert.index(["gdInsertSymbols", "S"]), insert.index(["gdInsertReferences", "S"]))
        home = ladders[("writer", "pmhbHome")]["steps"]
        self.assertEqual(home[:2], [["gdHomeStyle", "M"], ["gdHomeStyle", "S"]])
        self.assertEqual(home[-1], ["gdHomeFont", "C"])

    def test_every_other_tab_follows_the_rule(self):
        checked = 0
        for (app, box), got in generated_ladders().items():
            if not got["ladder"].get("rule"):
                continue
            gen = got["gen"]
            buttons = [g for g, s in got["steps"] if s == "C"]
            self.assertEqual(got["fold"], buttons, (app, box))
            gallery = [g for g in buttons if g in gen.GALLERIES]
            # (a) a gallery goes to M and S first; (d) it becomes its button first
            self.assertEqual(got["steps"][:2 * len(gallery)], [[g, s] for s in "MS" for g in gallery], (app, box))
            self.assertEqual(buttons[:len(gallery)], gallery, (app, box))
            # the formatting groups are the last buttons, Font the very last
            formatting = [g for g in buttons if gen.FORMATTING.search(g) and g not in gallery]
            if formatting:
                self.assertEqual(buttons[-len(formatting):], formatting, (app, box))
                if any("Font" in g for g in formatting):
                    self.assertIn("Font", buttons[-1], (app, box))
            # every group goes down its ladder only: M before S before C
            for group in buttons:
                order = [s for g, s in got["steps"] if g == group]
                self.assertEqual(order, sorted(order, key="MSC".index), (app, box, group))
            checked += 1
        self.assertGreater(checked, 50)

    def test_sheets_home_font_collapses_last(self):
        steps = generated_ladders()[("calc", "pmhbHome")]["steps"]
        self.assertEqual(steps[-1], ["gdHomeFont", "C"])
        # the reference suite's labels: Clipboard's small buttons lose theirs before Cells and Alignment; Alignment
        # (Wrap Text, Merge & Center) keeps them longest
        self.assertEqual(steps[:3], [["gdHomeStyles", "M"], ["gdHomeClipboard", "S"], ["gdHomeCells", "M"]])
        self.assertEqual([s for s in steps if s[1] == "S"][-1], ["gdHomeAlignment", "S"])

    def test_sheets_reference_labels_first_to_go(self):
        ladders = generated_ladders()
        self.assertEqual(ladders[("calc", "pmhbInsert")]["steps"][:4], [["gdInsertText", "S"], ["gdInsertShapes", "C"],
                                                                       ["gdInsertText", "C"], ["gdInsertSymbols", "C"]])
        self.assertEqual(ladders[("calc", "pmhbFunctions")]["steps"][0], ["gdFunctionsCalculation", "S"])
        self.assertEqual(ladders[("calc", "pmhbData")]["steps"][0], ["gdDataExamination", "S"])


if __name__ == "__main__":
    unittest.main()
