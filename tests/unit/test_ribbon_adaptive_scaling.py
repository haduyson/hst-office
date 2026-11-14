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


class ApprovedOrder(unittest.TestCase):
    def test_patch_has_the_data(self):
        data = json.load(open(os.path.join(ROOT, "data/ribbon/adaptive-ladders.json"), encoding="utf-8"))
        text = added(LADDERS, "vcl/inc/HstRibbonLadders.hxx")
        states = {"M": 1, "S": 2, "C": 3}
        for ladder in data["ladders"]:
            steps = ", ".join(f'{{ u"{g}", {states[s]} }}' for g, s in ladder["steps"])
            self.assertIn(f"{ladder['app']}_{ladder['box']}_steps[] = {{ {steps} }};", text)

    def test_insert_symbols_small_before_links_small(self):
        data = json.load(open(os.path.join(ROOT, "data/ribbon/adaptive-ladders.json"), encoding="utf-8"))
        insert = next(l for l in data["ladders"] if l["box"] == "pmhbInsert")["steps"]
        self.assertLess(insert.index(["gdInsertSymbols", "S"]), insert.index(["gdInsertReferences", "S"]))


if __name__ == "__main__":
    unittest.main()
