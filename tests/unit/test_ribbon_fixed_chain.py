# SPDX-License-Identifier: AGPL-3.0-only
"""The fixed collapse chain (hst-ribbon-mockup-chain.patch) gives Writer's Home and Insert exactly the states of the
approved 1.0.2 mockup: hst::ribbon::select() of HstRibbonScaling.hxx, fed with the mockup's own group widths
(data/ribbon/mockup-1-0-2-expected.json, from the plan 261115-2225) and the chains of adaptive-ladders.json,
returns the mockup's state vector at every width it was rendered at; and the box keeps select()'s states."""
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
    def test_writer_home_and_insert_match_the_mockup(self):
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
            cases += [(tab, w, [STATES.index(expected["states"][f"{tab}-{w}"]["states"][k]) for k, _g in groups])
                      for w in windows]
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
