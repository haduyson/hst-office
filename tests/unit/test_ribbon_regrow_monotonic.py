# SPDX-License-Identifier: AGPL-3.0-only
"""Ribbon layouts are monotonic in the window width (vcl/inc/HstRibbonRegrow.hxx, hst-ribbon-regrow-chain.patch).

Owner decisions 15/11/2026 (gap list G10): one fixed chain of steps per tab, so widening the window never takes a
group to a narrower state (no label lost, no group collapsed) that a narrower width did not have. The driver lays
out every ribbon tab of
data/ribbon/scaling-priorities.json (its groups and usage priority) with fitByPriority from 900 to 1920 px in 10 px
steps and checks that no group's state gets narrower as the width grows and that the row always fits. The group widths are
synthetic (no per-state widths are recorded outside a running office) but shaped like the measured ones: medium no
wider than large, small 40-90 % of the labelled width, some groups whose labels cost almost nothing, a button of
45-80 px; three width sets per tab, from a fixed seed. Skipped without a C++ compiler.
"""
import json
import os
import random
import shutil
import subprocess
import tempfile
import unittest

from _paths import ROOT
from test_ribbon_grow_order import regrow_header
from test_ribbon_regrow import added_file

PRIORITIES = os.path.join(ROOT, "data", "ribbon", "scaling-priorities.json")

DRIVER_HEAD = r"""
#include "HstRibbonRegrow.hxx"
#include <cstdio>
using namespace hst::ribbon;
static int failures = 0;
static void sweep(const char* pName, const std::vector<Group>& rGroups, const std::vector<std::size_t>& rPriority)
{
    std::vector<std::size_t> aBefore;
    for (long nWidth = 900; nWidth <= 1920; nWidth += 10)
    {
        const Layout l = fitByPriority(rGroups, rPriority, nWidth);
        if (l.fits && (l.width > nWidth || l.width != rowWidth(rGroups, l.states)))
            std::printf("FAIL %s at %ld: row %ld\n", pName, nWidth, l.width), ++failures;
        if (!l.fits)
        {
            aBefore.clear(); // select() and its overflow popup decide
            continue;
        }
        for (std::size_t i = 0; i < aBefore.size(); ++i)
            if (l.states[i] > aBefore[i])
                std::printf("FAIL %s: group %zu in state %zu at %ld px, %zu at %ld px\n", pName, i, l.states[i],
                            nWidth, aBefore[i], nWidth - 10), ++failures;
        aBefore = l.states;
    }
}
int main()
{
"""


def synthetic_groups(rng, count):
    groups = []
    for _ in range(count):
        large = rng.randint(90, 520)
        medium = large if rng.random() < 0.5 else rng.randint(large * 6 // 10, large)
        labelled = min(large, medium)
        small = labelled - rng.randint(0, 12) if rng.random() < 0.2 else rng.randint(labelled * 4 // 10, labelled * 9 // 10)
        groups.append((large, medium, small, rng.randint(45, 80)))
    return groups


def driver_source():
    ladders = json.load(open(PRIORITIES, encoding="utf-8"))["ladders"]
    rng = random.Random(20261115)
    body = []
    for ladder in ladders:
        groups = ladder["groups"]
        priority = [groups.index(g) for g in ladder["priority"] if g in groups]
        for variant in range(3):
            widths = synthetic_groups(rng, len(groups))
            name = f'{ladder["app"]}/{ladder["box"]}#{variant}'
            init = ", ".join("{ { %d, %d, %d, %d }, false }" % w for w in widths)
            prio = ", ".join(str(p) for p in priority)
            body.append(f'    sweep("{name}", {{ {init} }}, {{ {prio} }});')
    # Sheets' Home as measured on Linux at 100 % (test_ribbon_grow_order)
    body.append('    sweep("calc/pmhbHome measured", { { { 110, 110, 110, 95 }, false }, { { 525, 525, 415, 60 }, false }, '
                '{ { 265, 265, 175, 70 }, false }, { { 230, 230, 225, 50 }, false }, { { 130, 130, 70, 50 }, false }, '
                '{ { 190, 190, 110, 45 }, false }, { { 340, 340, 200, 80 }, false } }, { 1, 2, 3, 6, 4, 0, 5 });')
    return DRIVER_HEAD + "\n".join(body) + '\n    std::printf("%d failures\\n", failures);\n    return failures != 0;\n}\n'


class RibbonRegrowMonotonicTest(unittest.TestCase):
    @unittest.skipUnless(shutil.which("g++") and shutil.which("patch"), "no C++ compiler or patch")
    def test_no_group_gets_narrower_as_the_window_widens(self):
        with tempfile.TemporaryDirectory() as tmp:
            with open(os.path.join(tmp, "HstRibbonScaling.hxx"), "w", encoding="utf-8") as handle:
                handle.write(added_file("hst-ribbon-scaling-helper.patch", "vcl/inc/HstRibbonScaling.hxx"))
            with open(os.path.join(tmp, "HstRibbonRegrow.hxx"), "w", encoding="utf-8") as handle:
                handle.write(regrow_header(os.path.join(tmp, "tree")))
            src = os.path.join(tmp, "driver.cxx")
            with open(src, "w", encoding="utf-8") as handle:
                handle.write(driver_source())
            exe = os.path.join(tmp, "driver")
            build = subprocess.run(["g++", "-std=c++20", "-Wall", "-Wextra", "-Werror", "-o", exe, src],
                                   capture_output=True, text=True, check=False)
            self.assertEqual(build.returncode, 0, build.stderr[-3000:])
            run = subprocess.run([exe], capture_output=True, text=True, check=False, timeout=120)
            self.assertEqual(run.returncode, 0, run.stdout[-3000:])

if __name__ == "__main__":
    unittest.main()
