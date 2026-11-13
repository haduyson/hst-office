# SPDX-License-Identifier: AGPL-3.0-only
"""Ribbon regrow pass (vcl/inc/HstRibbonRegrow.hxx from hst-ribbon-ux-engine.patch).

select() (HstRibbonScaling.hxx) stops at the first ladder step that fits; fitByPriority() lays the row
out again from the groups' priority: only the least used groups become buttons, the others grow back,
most used first. Both headers are
taken from their patches and compiled with a small driver (skipped without a C++ compiler). The driver
sweeps the window width with ladders built like generate-ribbon-scale.py builds them from a priority
list, and checks the audit's gates: the row never overflows, no group stays a button beside room for
it, and a group shown at some width is shown at every wider width.
"""
import os
import re
import shutil
import subprocess
import tempfile
import unittest

from _paths import ROOT
from test_ribbon_grow_order import regrow_header

PATCHES = os.path.join(ROOT, "patches", "libreoffice")


def added_file(patch, path):
    text = open(os.path.join(PATCHES, patch), encoding="utf-8").read()
    match = re.search(r"^\+\+\+ b/" + re.escape(path) + r"\n@@ [^\n]*\n((?:\+[^\n]*\n)+)", text, re.M)
    if not match:
        raise AssertionError(f"{path} not added by {patch}")
    return "".join(line[1:] + "\n" for line in match.group(1).splitlines())


DRIVER = r"""
#include "HstRibbonRegrow.hxx"
#include <cstdio>
using namespace hst::ribbon;
static int failures = 0;
#define CHECK(c) do { if (!(c)) { std::printf("FAIL line %d: %s\n", __LINE__, #c); ++failures; } } while (0)

// ladder from a priority list (most used first), as generate-ribbon-scale.py writes it: every group to
// medium, then small, then its button, least used first
static std::vector<Step> ladderFrom(const std::vector<std::size_t>& rPriority)
{
    std::vector<Step> aSteps;
    for (std::size_t nState = 1; nState <= 3; ++nState)
        for (auto it = rPriority.rbegin(); it != rPriority.rend(); ++it)
            aSteps.push_back(Step{ *it, nState });
    return aSteps;
}

static Layout layoutFor(const std::vector<Group>& rGroups, const std::vector<std::size_t>& rPriority, long nWidth)
{
    Layout aLayout = select(rGroups, ladderFrom(rPriority), nWidth, 25);
    if (aLayout.overflow.empty())
    {
        const Layout aFit = fitByPriority(rGroups, rPriority, nWidth);
        CHECK(aFit.fits); // select() fitting implies a priority fit
        aLayout = aFit;
    }
    return aLayout;
}

static void sweep(const std::vector<Group>& rGroups, const std::vector<std::size_t>& rPriority, long nFrom, long nTo)
{
    const long nIdeal = rowWidth(rGroups, std::vector<std::size_t>(rGroups.size(), 0));
    for (long nWidth = nFrom; nWidth <= nTo; nWidth += 3)
    {
        const Layout aLayout = layoutFor(rGroups, rPriority, nWidth);
        if (!aLayout.overflow.empty())
            continue;
        CHECK(aLayout.width <= nWidth);
        CHECK(aLayout.width == rowWidth(rGroups, aLayout.states));
        if (nWidth >= nIdeal)
            for (std::size_t s : aLayout.states)
                CHECK(s == 0);
        // no group is a button beside room enough to show it (owner decision: folded groups open again out of
        // the usage order, so folding is no longer monotonic as the window widens)
        for (std::size_t i = 0; i < rGroups.size(); ++i)
            if (aLayout.states[i] == 3
                && aLayout.width - widthOf(rGroups[i], 3) + widthOf(rGroups[i], smallestShownState(rGroups[i])) <= nWidth)
                std::printf("FAIL room: group %zu a button at %ld with room to show it\n", i, nWidth), ++failures;
    }
}

int main()
{
    // Sheets View tab: Dạng xem, Hiện, Thu phóng, Cửa sổ, Macro; widths L M S C. Cửa sổ (freeze panes) is
    // the most used group, Hiện (nine toggles) the least.
    const std::vector<Group> view = {
        { { 230, 230, 150, 70 }, false },
        { { 760, 560, 140, 50 }, false },
        { { 240, 210, 160, 70 }, false },
        { { 400, 400, 180, 70 }, false },
        { { 120, 90, 50, 60 }, false },
    };
    const std::vector<std::size_t> viewPriority = { 3, 0, 2, 4, 1 };
    // 1920 px window: about 1610 px for the groups; Cửa sổ stays open, Hiện gives way first
    {
        const Layout l = layoutFor(view, viewPriority, 1610);
        CHECK(l.overflow.empty() && l.fits);
        CHECK(l.states[3] <= 1);
        for (std::size_t s : l.states)
            CHECK(s != 3);
    }
    // the room goes to the most used groups first; Hiện, the least used, stays small
    {
        const Layout l = fitByPriority(view, viewPriority, 230 + 560 + 160 + 400 + 90);
        CHECK(l.fits && l.states[3] == 0 && l.states[0] == 0 && l.states[1] == 2);
    }
    // narrow: the least used group (Hiện) is the first to become its button
    {
        const Layout l = fitByPriority(view, viewPriority, 150 + 140 + 160 + 180 + 50 - 1);
        CHECK(l.fits && l.states[1] == 3);
        for (std::size_t i : { 0, 2, 3, 4 })
            CHECK(l.states[i] != 3);
    }
    // the room left after folding opens a smaller, less used group again (out of the usage order): with
    // 300 px for Dạng xem (most used, 150 at its smallest), a large group (400) and a small one (60), the large
    // one folds first by usage, then the small one, and the small one comes back into the room left
    {
        const std::vector<Group> row = { { { 150, 150, 150, 70 }, false }, { { 400, 400, 400, 70 }, false },
                                         { { 60, 60, 60, 50 }, false } };
        const Layout l = fitByPriority(row, { 0, 1, 2 }, 300);
        CHECK(l.fits && l.states[0] == 0 && l.states[1] == 3 && l.states[2] == 0 && l.width == 280);
    }
    // too narrow for every button: no fit, select() and its overflow popup decide
    CHECK(!fitByPriority(view, viewPriority, 200).fits);
    // priorityFromFold: the reverse of the fold order, missing groups after
    CHECK((priorityFromFold(4, { 2, 0 }) == std::vector<std::size_t>{ 0, 2, 1, 3 }));
    CHECK((priorityFromFold(3, {}) == std::vector<std::size_t>{ 0, 1, 2 }));

    sweep(view, viewPriority, 300, 2000);
    // Writer Review tab: Soát lỗi, Trợ năng, Ngôn ngữ, Chú thích, Theo dõi thay đổi, Thay đổi, So sánh, Bảo vệ
    const std::vector<Group> review = {
        { { 340, 300, 140, 70 }, false }, { { 170, 120, 40, 70 }, false }, { { 310, 260, 80, 70 }, false },
        { { 300, 260, 120, 70 }, false }, { { 220, 180, 90, 120 }, false }, { { 200, 170, 80, 80 }, false },
        { { 100, 90, 50, 70 }, false }, { { 70, 70, 40, 60 }, false },
    };
    sweep(review, { 4, 5, 3, 0, 7, 6, 2, 1 }, 400, 2200);
    return failures ? 1 : 0;
}
"""


class RibbonRegrowTest(unittest.TestCase):
    def test_header_has_no_libreoffice_types(self):
        header = added_file("hst-ribbon-ux-engine.patch", "vcl/inc/HstRibbonRegrow.hxx")
        includes = re.findall(r"^#include\s+[<\"]([^>\"]+)[>\"]", header, re.M)
        self.assertEqual(sorted(includes), ["HstRibbonScaling.hxx", "cstddef", "vector"])
        self.assertNotRegex(header, r"\b(OUString|tools::|vcl::|VclPtr|sal_)")

    def test_engine_uses_regrow_for_every_tab(self):
        text = open(os.path.join(PATCHES, "hst-ribbon-ux-engine.patch"), encoding="utf-8").read()
        self.assertIn("hst::ribbon::fitByPriority(aGroups, m_aHstPlanPriority, nWidth)", text)
        self.assertIn("-    if (aLayout.overflow.empty() && !bOwnLadder)", text)

    @unittest.skipUnless(shutil.which("g++") and shutil.which("patch"), "no C++ compiler or patch")
    def test_regrow(self):
        with tempfile.TemporaryDirectory() as tmp:
            with open(os.path.join(tmp, "HstRibbonScaling.hxx"), "w", encoding="utf-8") as handle:
                handle.write(added_file("hst-ribbon-scaling-helper.patch", "vcl/inc/HstRibbonScaling.hxx"))
            # the header as the series leaves it (with the growth order, hst-ribbon-ux-grow-order.patch): the
            # default growth order is the priority's, so every gate here holds unchanged
            with open(os.path.join(tmp, "HstRibbonRegrow.hxx"), "w", encoding="utf-8") as handle:
                handle.write(regrow_header(os.path.join(tmp, "tree")))
            with open(os.path.join(tmp, "driver.cxx"), "w", encoding="utf-8") as handle:
                handle.write(DRIVER)
            exe = os.path.join(tmp, "driver")
            build = subprocess.run(["g++", "-std=c++20", "-Wall", "-Wextra", "-Werror", "-o", exe,
                                    os.path.join(tmp, "driver.cxx")], capture_output=True, text=True)
            self.assertEqual(build.returncode, 0, build.stderr)
            run = subprocess.run([exe], capture_output=True, text=True)
            self.assertEqual(run.returncode, 0, run.stdout)


if __name__ == "__main__":
    unittest.main()
