# SPDX-License-Identifier: LicenseRef-HST-Proprietary
# Copyright (C) 2026 HASON TECH
"""The v3 group packing (vcl/inc/HstRibbonV3Pack.hxx from hst-ribbon-v3-layout.patch) reproduces the owner-locked
mockup: every group of data/ribbon/ribbon-v3.json, at the states L (with and without the sparse tab's fill), M and S,
gets the blocks and looks that the mockup's own packItems()/packRun()/eff() draw.

The expected blocks are tests/unit/data/ribbon-v3-mockup-blocks.txt, written by
scripts/patches/ribbon-v3-mockup-blocks.js from mockup-chot-v3.html (rerun it when the design changes)."""
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest

from _paths import ROOT
from patch_sections import added

sys.path.insert(0, os.path.join(ROOT, "scripts", "patches"))
from ribbon_v3_ui import layout_spec  # noqa: E402

PATCH = "hst-ribbon-v3-layout.patch"
HEADER = "vcl/inc/HstRibbonV3Pack.hxx"
EXPECTED = os.path.join(ROOT, "tests", "unit", "data", "ribbon-v3-mockup-blocks.txt")

DRIVER = r"""
#include "HstRibbonV3Pack.hxx"
#include <iostream>
#include <sstream>
using namespace hst::ribbon::v3;
int main()
{
    std::string app, tab, group, spec, paste;
    char state;
    int big;
    while (std::cin >> app >> tab >> group >> state >> big >> spec >> paste)
    {
        const Spec s = parseSpec(spec);
        if (!s.valid)
            return 2;
        Input in{ s.kinds, {}, std::vector<bool>(s.kinds.size(), true), s.rows, state, big != 0 };
        for (char c : paste)
            in.paste.push_back(c == '1');
        std::ostringstream o;
        for (const auto& b : structure(in))
        {
            if (o.tellp() > 0)
                o << ' ';
            o << (b.type == BlockType::Large ? 'L' : b.type == BlockType::Gallery ? 'G'
                  : b.type == BlockType::Column ? 'C' : 'R') << '[';
            for (std::size_t l = 0; l < b.lines.size(); ++l)
                for (std::size_t k = 0; k < b.lines[l].size(); ++k)
                {
                    o << (l && !k ? "/" : k ? "," : "");
                    if (b.lines[l][k].second == '|')
                        o << '|';
                    else
                        o << b.lines[l][k].first << b.lines[l][k].second;
                }
            o << ']';
        }
        std::cout << app << ' ' << tab << ' ' << group << ' ' << state << ' ' << big << " => " << o.str() << '\n';
    }
    // positions: Paste large, a column of three icons 4 px after it; the column's labelled buttons share a width
    Input clip{ "LSSS", { true, false, false, false }, { true, true, true, true }, {}, 'L', false };
    const Plan p = place(clip, [](std::size_t i, char c) { return c == 'L' ? 40L : 24L + long(i); }, 52);
    if (p.cells.size() != 4 || p.cells[0].w != 52 || p.cells[1].x != 56 || p.cells[2].y != 26 || p.cells[3].y != 52
        || p.width != 56 + 27)
        return 3;
    Input labels{ "MMM", { false, false, false }, { true, true, true }, {}, 'L', false };
    const Plan q = place(labels, [](std::size_t i, char) { return 50L + 10 * long(i); }, 0);
    if (q.cells[0].w != 70 || q.cells[1].w != 70 || q.cells[2].w != 70 || q.width != 70)
        return 4;
    return 0;
}
"""


def cases():
    with open(os.path.join(ROOT, "data", "ribbon", "ribbon-v3.json"), encoding="utf-8") as handle:
        data = json.load(handle)
    for app in data["apps"]:
        for tab in app["tabs"]:
            for group in tab["groups"]:
                spec = layout_spec(group, [item["kind"] for item in group["items"]])
                paste = "".join("1" if item["k"] == "Paste" else "0" for item in group["items"])
                for state in "LMS":
                    for big in (0, 1) if state == "L" else (0,):
                        yield f"{app['id']} {tab['id']} {group['id']} {state} {big} {spec} {paste}"


@unittest.skipUnless(shutil.which("g++"), "needs g++")
class V3Pack(unittest.TestCase):
    def test_every_group_packs_as_the_mockup(self):
        with tempfile.TemporaryDirectory() as tmp:
            with open(os.path.join(tmp, "HstRibbonV3Pack.hxx"), "w", encoding="utf-8") as handle:
                handle.write(added(PATCH, HEADER) + "\n")
            with open(os.path.join(tmp, "driver.cxx"), "w", encoding="utf-8") as handle:
                handle.write(DRIVER)
            subprocess.run(["g++", "-std=c++20", "-Wall", "-Wextra", "-Werror", "-o", os.path.join(tmp, "drv"),
                            os.path.join(tmp, "driver.cxx")], check=True)
            run = subprocess.run([os.path.join(tmp, "drv")], input="\n".join(cases()) + "\n", text=True,
                                 capture_output=True)
        self.assertEqual(run.returncode, 0, run.stderr)
        with open(EXPECTED, encoding="utf-8") as handle:
            expected = handle.read().splitlines()
        got = run.stdout.splitlines()
        self.assertEqual(len(got), len(expected))
        mismatches = [(e, g) for e, g in zip(expected, got) if e != g]
        self.assertEqual(mismatches, [], mismatches[:5])


if __name__ == "__main__":
    unittest.main()
