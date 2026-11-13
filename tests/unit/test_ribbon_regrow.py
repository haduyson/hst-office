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
    std::vector<bool> aShownBefore(rGroups.size(), false);
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
        // the collapsed groups are the least used ones: a shown group less used than a collapsed one
        // is one whose button would save nothing
        for (std::size_t nMore = 0; nMore < rPriority.size(); ++nMore)
            for (std::size_t nLess = nMore + 1; nLess < rPriority.size(); ++nLess)
            {
                const Group& rLess = rGroups[rPriority[nLess]];
                if (aLayout.states[rPriority[nMore]] == 3 && aLayout.states[rPriority[nLess]] != 3
                    && widthOf(rLess, 3) < widthOf(rLess, smallestShownState(rLess)))
                    std::printf("FAIL order at %ld\n", nWidth), ++failures;
            }
        for (std::size_t i = 0; i < rGroups.size(); ++i)
        {
            const bool bShown = aLayout.states[i] != 3;
            if (aShownBefore[i] && !bShown)
                std::printf("FAIL monotonic: group %zu shown below %ld, a button at %ld\n", i, nWidth, nWidth), ++failures;
            aShownBefore[i] = aShownBefore[i] || bShown;
        }
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

    @unittest.skipUnless(shutil.which("g++"), "no C++ compiler")
    def test_regrow(self):
        with tempfile.TemporaryDirectory() as tmp:
            for patch, name in (("hst-ribbon-scaling-helper.patch", "HstRibbonScaling.hxx"),
                                ("hst-ribbon-ux-engine.patch", "HstRibbonRegrow.hxx")):
                with open(os.path.join(tmp, name), "w", encoding="utf-8") as handle:
                    handle.write(added_file(patch, "vcl/inc/" + name))
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
