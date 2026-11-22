# SPDX-License-Identifier: LicenseRef-HST-Proprietary
# Copyright (C) 2026 HASON TECH
"""The fixed collapse chain (hst-ribbon-mockup-chain.patch) gives Writer's Home and Insert the states of the 1.0.2
mockup, except where the reference suite keeps labels the mockup drops (owner decision 16/11/2026 00:45):
hst::ribbon::select() of HstRibbonScaling.hxx, fed with the mockup's own group widths
(data/ribbon/mockup-1-0-2-expected.json, from the plan 261115-2225) and the chains of adaptive-ladders.json,
returns WANT's state vector at every width the mockup was rendered at; and the box keeps select()'s states."""
import json
import os
import re
import subprocess
import tempfile
import unittest

from _paths import ROOT
from test_ribbon_regrow import added_file

PATCHES = os.path.join(ROOT, "patches", "libreoffice")
EXPECTED = os.path.join(ROOT, "data", "ribbon", "mockup-1-0-2-expected.json")  # copy of the plan's reference/mockup-expected.json
STATES = "LMSC"
# mockup group key -> HST group id, per tab, in tab order
GROUPS = {
    "home": [("clip", "gdHomeClipboard"), ("font", "gdHomeFont"), ("para", "gdHomeParagraph"), ("styles", "gdHomeStyle"),
             ("edit", "gdHomeHstEditing"), ("viet", "gdHomeHstVietnamese")],
    "insert": [("pages", "gdInsertPage"), ("tables", "gdInsertTables"), ("illus", "gdInsertGraphic"),
               ("links", "gdInsertReferences"), ("comments", "gdInsertComments"), ("hf", "gdInsertHeaderFooter"),
               ("text", "gdInsertText"), ("symbols", "gdInsertSymbols")],
}
BOX = {"home": "pmhbHome", "insert": "pmhbInsert"}
# states in GROUPS order. Against the mockup: Home keeps Clipboard large down to 1440 px and gives the Vietnamese
# group's labels up first (1280-1440); Insert keeps Header & Footer large at 1440 and, as the reference suite's
# narrow sweep, sends Links, Pages and Symbols to their buttons while Illustrations keeps its labels. The mockup's
# widths leave 28 px too few for a labelled Clipboard at 1366: the real widths decide there (HST_RIBBON_DUMP_WIDTHS)
WANT = {"home": {1100: "SLSCLS", 1280: "SLSSLS", 1366: "SLSSLS", 1440: "LLSSLS", 1485: "LLSSLM", 1600: "LLSSLM",
                 1920: "LLLMLL"},
        "insert": {1100: "CLSCLMSC", 1280: "CLLCLMSC", 1366: "LLLCLMSL", 1440: "LLLMLLSL", 1485: "LLLLLLSL",
                   1600: "LLLLLLSL", 1920: "LLLLLLLL"}}
DRIVER = r"""
#include "HstRibbonScaling.hxx"
#include <cstdio>
#include <iostream>
using namespace hst::ribbon;
int main()
{
    std::size_t nGroups, nSteps, nWidths;
    while (std::cin >> nGroups)
    {
        std::vector<Group> aGroups(nGroups);
        for (Group& rGroup : aGroups)
        {
            rGroup.widths.resize(4);
            for (long& n : rGroup.widths)
                std::cin >> n;
        }
        std::cin >> nSteps;
        std::vector<Step> aSteps(nSteps);
        for (Step& rStep : aSteps)
            std::cin >> rStep.group >> rStep.state;
        std::cin >> nWidths;
        for (std::size_t w = 0; w < nWidths; ++w)
        {
            long nAvailable;
            std::cin >> nAvailable;
            const Layout aLayout = select(aGroups, aSteps, nAvailable, 0);
            for (std::size_t s : aLayout.states)
                std::printf("%zu ", s);
            std::printf("\n");
        }
    }
}
"""


def banner_width(window):
    # the mockup's bannerFull(): 260 up to 1440 px, then growing to 360 at 1920
    return round(260 if window <= 1440 else min(360, 260 + (window - 1440) * 100 / 480))


def available(window):
    # the mockup's layout(): W - (banner + 2 x 8 px gap) - 4
    return window - (banner_width(window) + 16) - 4


@unittest.skipUnless(os.path.exists(EXPECTED), "the mockup reference is in the plan")
class MockupStates(unittest.TestCase):
    def test_writer_home_and_insert_states(self):
        expected = json.load(open(EXPECTED, encoding="utf-8"))
        ladders = {l["box"]: l for l in json.load(open(os.path.join(ROOT, "data/ribbon/adaptive-ladders.json"),
                                                       encoding="utf-8"))["ladders"] if l["app"] == "writer"}
        cases, inputs = [], []
        for tab, groups in GROUPS.items():
            widths = []
            for key, _gid in groups:
                w = expected["group_widths"][f"{tab}:{key}"]
                row, last = [], None
                for state in STATES:  # a state the group does not have measures as the one before (never taken)
                    last = w.get(state, last)
                    row.append(round(last))
                widths.append(row)
            index = {gid: i for i, (_k, gid) in enumerate(groups)}
            steps = [(index[g], STATES.index(s)) for g, s in ladders[BOX[tab]]["steps"]]
            windows = sorted(int(k.split("-")[1]) for k in expected["states"] if k.startswith(tab + "-"))
            inputs += [str(len(groups))] + [" ".join(map(str, r)) for r in widths]
            inputs += [str(len(steps))] + [f"{g} {s}" for g, s in steps]
            inputs += [str(len(windows))] + [str(available(w)) for w in windows]
            cases += [(tab, w, [STATES.index(s) for s in WANT[tab][w]]) for w in windows]
        with tempfile.TemporaryDirectory() as tmp:
            with open(os.path.join(tmp, "HstRibbonScaling.hxx"), "w", encoding="utf-8") as handle:
                handle.write(added_file("hst-ribbon-scaling-helper.patch", "vcl/inc/HstRibbonScaling.hxx"))
            with open(os.path.join(tmp, "d.cxx"), "w", encoding="utf-8") as handle:
                handle.write(DRIVER)
            subprocess.run(["g++", "-std=c++17", "-I", tmp, "-o", os.path.join(tmp, "d"), os.path.join(tmp, "d.cxx")],
                           check=True)
            run = subprocess.run([os.path.join(tmp, "d")], input="\n".join(inputs) + "\n", capture_output=True,
                                 text=True, check=True)
        got = [[int(x) for x in line.split()] for line in run.stdout.splitlines()]
        self.assertEqual(len(got), len(cases))
        for (tab, window, want), states in zip(cases, got):
            self.assertEqual("".join(STATES[s] for s in states), "".join(STATES[s] for s in want), f"{tab} {window}")


GROW_DRIVER = r"""
#include "HstRibbonFixedChain.hxx"
#include <cstdio>
using namespace hst::ribbon;
int main()
{
    // Writer Home at 1485 px (1193 px for the groups), widths measured on the 1.0.2 build with Paragraph at the
    // mockup's 143 px: select() stops at Clipboard S with 113 px free; the Vietnamese group grows back to L
    const std::vector<Group> aGroups{ { { 190, 190, 76, 81 } }, { { 324, 324, 324, 89 } }, { { 262, 262, 143, 80 } },
                                      { { 602, 410, 314, 49 } }, { { 85, 85, 65, 83 } }, { { 216, 159, 138, 94 } } };
    const std::vector<Step> aSteps{ { 3, 1 }, { 3, 2 }, { 5, 1 }, { 2, 2 }, { 5, 2 }, { 0, 2 }, { 4, 3 } };
    for (long nWidth : { 1193L, 1083L, 2000L })
    {
        const Layout aLayout = select(aGroups, aSteps, nWidth, 0);
        const std::vector<std::size_t> aGrown = growBack(aGroups, aSteps, nWidth, aLayout.states);
        for (std::size_t n : aGrown)
            std::printf("%zu", n);
        std::printf(" %ld\n", rowWidth(aGroups, aGrown));
    }
}
"""


class GrowBack(unittest.TestCase):
    def test_groups_grow_back_into_the_room_and_still_fit(self):
        with tempfile.TemporaryDirectory() as tmp:
            for name, patch in (("HstRibbonScaling.hxx", "hst-ribbon-scaling-helper.patch"),
                                ("HstRibbonFixedChain.hxx", "hst-ribbon-mockup-chain.patch")):
                with open(os.path.join(tmp, name), "w", encoding="utf-8") as handle:
                    handle.write(added_file(patch, "vcl/inc/" + name))
            with open(os.path.join(tmp, "g.cxx"), "w", encoding="utf-8") as handle:
                handle.write(GROW_DRIVER)
            subprocess.run(["g++", "-std=c++17", "-I", tmp, "-o", os.path.join(tmp, "g"), os.path.join(tmp, "g.cxx")],
                           check=True)
            got = subprocess.run([os.path.join(tmp, "g")], capture_output=True, text=True, check=True).stdout.split()
        # 1485: Clipboard S, Paragraph S, Styles S, Vietnamese back to L (select gave S); 1366: as select;
        # 2000: nothing applied, all large
        self.assertEqual(got, ["202200", "1158", "202202", "1080", "000000", "1679"])


class EngineWiring(unittest.TestCase):
    def setUp(self):
        self.patch = open(os.path.join(PATCHES, "hst-ribbon-mockup-chain.patch"), encoding="utf-8").read()

    def test_series_order(self):
        series = [l.strip() for l in open(os.path.join(PATCHES, "series"), encoding="utf-8") if l.strip()]
        self.assertLess(series.index("hst-ribbon-dump-widths.patch"), series.index("hst-ribbon-mockup-chain.patch"))

    def test_no_regrow_by_usage_under_the_fixed_chain(self):
        added = "".join(l[1:] + "\n" for l in self.patch.splitlines() if l.startswith("+"))
        self.assertIn("officecfg::Office::HSTRibbon::FixedChain::get()", added)
        self.assertIn("m_bHstFixedChain = bOwnLadder && lcl_HstFixedChainEnabled();", added)
        self.assertIn("if (aLayout.overflow.empty() && !m_bHstFixedChain)", added)
        self.assertIn("aShownFit.fits && !m_bHstFixedChain", added)
        self.assertIn("pChild->set_hexpand(false);", added)
        self.assertRegex(self.patch, re.compile(r'oor:name="FixedChain".*?<value>true</value>', re.S))


if __name__ == "__main__":
    unittest.main()
