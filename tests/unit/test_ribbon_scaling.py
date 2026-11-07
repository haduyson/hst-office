# SPDX-License-Identifier: AGPL-3.0-only
"""Ribbon collapse ladder (vcl HstRibbonScaling.hxx from hst-ribbon-scaling-helper.patch).

The helper picks, for an available width, the size state of every ribbon group from an ordered
ladder, and moves groups from the right end into the overflow popup when the ladder is used up.
The header has no LibreOffice dependencies, so it is taken from the patch and compiled with a
small driver (skipped when no C++ compiler is available).
"""
import os
import re
import shutil
import subprocess
import tempfile
import unittest

from _paths import ROOT

PATCH = os.path.join(ROOT, "patches", "libreoffice", "hst-ribbon-scaling-helper.patch")
HEADER = "vcl/inc/HstRibbonScaling.hxx"

DRIVER = r"""
#include "HstRibbonScaling.hxx"
#include <cstdio>
using namespace hst::ribbon;
static int failures = 0;
#define CHECK(c) do { if (!(c)) { std::printf("FAIL %s:%d %s\n", __FILE__, __LINE__, #c); ++failures; } } while (0)

// Writer Home shape: Clipboard, Font, Paragraph, Styles (G6, G4, C), Editing, HST, right block.
enum { CLIP, FONT, PARA, STYLES, EDIT, HSTG, RIGHT };
static std::vector<Group> writerHome()
{
    return {
        { { 120, 90, 70, 48 }, false },     // L M S C
        { { 260, 220, 180, 48 }, false },
        { { 240, 200, 160, 48 }, false },
        { { 620, 420, 48 }, false },        // G6 G4 C
        { { 110, 80, 48 }, false },         // L S C
        { { 90, 48 }, false },              // L C
        { { 150, 30 }, true },              // right block: shown, folded
    };
}
static std::vector<Step> writerLadder()
{
    return { { RIGHT, 1 }, { HSTG, 1 }, { STYLES, 1 }, { EDIT, 1 }, { STYLES, 2 }, { PARA, 1 },
             { FONT, 1 }, { EDIT, 2 }, { PARA, 2 }, { FONT, 2 }, { CLIP, 1 }, { PARA, 3 },
             { FONT, 3 }, { CLIP, 3 } };
}

static bool sameLayout(const Layout& a, const Layout& b)
{
    return a.states == b.states && a.overflow == b.overflow && a.appliedSteps == b.appliedSteps
           && a.width == b.width && a.fits == b.fits;
}

int main()
{
    const std::vector<Group> groups = writerHome();
    const std::vector<Step> ladder = writerLadder();
    const long ideal = rowWidth(groups, std::vector<std::size_t>(groups.size(), 0));
    CHECK(ideal == 1590);

    // wide window: nothing changes
    {
        const Layout l = select(groups, ladder, 4000, 25);
        CHECK(l.fits && l.appliedSteps == 0 && l.overflow.empty() && l.width == ideal);
        for (std::size_t s : l.states) CHECK(s == 0);
    }

    // exact boundary: a row exactly as wide as the space fits without another step
    {
        CHECK(select(groups, ladder, ideal, 25).appliedSteps == 0);
        const Layout one = select(groups, ladder, ideal - 1, 25);
        CHECK(one.appliedSteps == 1 && one.states[RIGHT] == 1 && one.width == ideal - 120 && one.fits);
        const long afterTwo = ideal - 120 - 42;
        CHECK(select(groups, ladder, afterTwo, 25).appliedSteps == 2);
        CHECK(select(groups, ladder, afterTwo - 1, 25).appliedSteps == 3);
        CHECK(select(groups, ladder, afterTwo - 1, 25).states[STYLES] == 1);
    }

    // monotonic: narrowing the space one pixel at a time never grows a group back, never
    // un-applies a step, never takes a group out of the overflow, and the width never grows
    {
        Layout prev = select(groups, ladder, 2000, 25);
        for (long avail = 1999; avail >= -10; --avail)
        {
            const Layout l = select(groups, ladder, avail, 25);
            CHECK(l.appliedSteps >= prev.appliedSteps);
            CHECK(l.width <= prev.width);
            CHECK(l.overflow.size() >= prev.overflow.size());
            for (std::size_t g = 0; g < groups.size(); ++g)
                CHECK(l.states[g] >= prev.states[g]);
            for (std::size_t g : prev.overflow)
            {
                bool still = false;
                for (std::size_t h : l.overflow) still = still || h == g;
                CHECK(still);
            }
            CHECK(l.fits == (l.width <= avail));
            CHECK(sameLayout(l, select(groups, ladder, avail, 25)));   // deterministic
            prev = l;
        }
    }

    // every step of this ladder shrinks the row, so they are all applied before any overflow
    const long allSteps = 48 * 6 + 30;
    {
        const Layout l = select(groups, ladder, allSteps, 25);
        CHECK(l.fits && l.overflow.empty() && l.appliedSteps == ladder.size() && l.width == allSteps);
    }

    // overflow: groups leave from the right end, the pinned right block stays, the "»" button counts
    {
        const Layout l = select(groups, ladder, allSteps - 1, 25);
        CHECK(l.appliedSteps == ladder.size());
        // removing HST (48) gives 270 + 25 = 295 <= 317; the pinned right block is skipped
        CHECK(l.overflow.size() == 1 && l.overflow[0] == HSTG);
        CHECK(l.fits && l.width == allSteps - 48 + 25);
        // 103 = Clipboard (48) + right block (30) + "»" (25), exactly
        const Layout tiny = select(groups, ladder, 103, 25);
        CHECK(tiny.fits && tiny.width == 30 + 48 + 25 && tiny.overflow.size() == 5);
        CHECK(tiny.overflow.front() == FONT);
        // too narrow for even the pinned block: everything else overflows, nothing fits
        const Layout none = select(groups, ladder, 10, 25);
        CHECK(!none.fits && none.overflow.size() == 6 && none.width == 30 + 25);
        for (std::size_t g : none.overflow) CHECK(g != RIGHT);
    }

    // skipped steps: unknown group or state, a step back to a larger state, a step that does
    // not shrink; none of them is counted and the state stays
    {
        const std::vector<Group> g2 = { { { 100, 100, 60 } }, { { 80, 50 } } };
        const std::vector<Step> odd = { { 7, 1 }, { 0, 9 }, { 0, 1 }, { 1, 1 }, { 1, 0 }, { 0, 2 } };
        const Layout l = select(g2, odd, 110, 0);
        CHECK(l.appliedSteps == 2 && l.states[0] == 2 && l.states[1] == 1 && l.width == 110 && l.fits);
        const Layout grow = select({ { { 50, 70 } } }, { { 0, 1 } }, 10, 0);
        CHECK(grow.appliedSteps == 0 && grow.states[0] == 0);
        CHECK(grow.overflow.size() == 1 && grow.fits && grow.width == 0);
        CHECK(!select({ { { 50, 70 } } }, { { 0, 1 } }, 10, 25).fits);
    }

    // empty ladder: default right to left, one state at a time across all groups
    {
        const std::vector<Group> g3 = { { { 100, 70, 40 } }, { { 90, 60 } }, { { 80, 50, 30, 20 } } };
        const std::vector<Step> d = defaultLadder(g3);
        CHECK(d.size() == 6);
        const std::size_t expect[][2] = { { 2, 1 }, { 1, 1 }, { 0, 1 }, { 2, 2 }, { 0, 2 }, { 2, 3 } };
        for (std::size_t i = 0; i < d.size() && i < 6; ++i)
            CHECK(d[i].group == expect[i][0] && d[i].state == expect[i][1]);
        CHECK(select(g3, {}, 270, 0).appliedSteps == 0);
        const Layout l = select(g3, {}, 240, 0);
        CHECK(l.appliedSteps == 1 && l.states[2] == 1 && l.states[0] == 0);
        CHECK(sameLayout(select(g3, {}, 150, 0), select(g3, d, 150, 0)));
        CHECK(select(g3, {}, 120, 0).appliedSteps == 6);
        // no groups at all
        const Layout empty = select({}, {}, 500, 25);
        CHECK(empty.fits && empty.width == 0 && empty.states.empty() && empty.overflow.empty());
        CHECK(defaultLadder({}).empty());
        CHECK(defaultLadder({ { { 100 } } }).empty());
        // a group without measured widths counts as zero width and has no states to step to
        const Layout blank = select({ { {} }, { { 40, 20 } } }, {}, 30, 0);
        CHECK(blank.fits && blank.width == 20 && blank.states[1] == 1);
    }

    // negative widths (a failed measurement) count as zero
    CHECK(rowWidth({ { { -5 } }, { { 10 } } }, { 0, 0 }) == 10);

    std::printf("checks done, %d failure(s)\n", failures);
    return failures ? 1 : 0;
}
"""


def header_from_patch():
    """Contents of the new ladder header as added by the patch."""
    text = open(PATCH, encoding="utf-8").read()
    match = re.search(r"^\+\+\+ b/" + re.escape(HEADER) + r"\n@@ [^\n]*\n((?:\+[^\n]*\n)+)", text, re.M)
    if not match:
        raise AssertionError(f"{HEADER} not added by {os.path.basename(PATCH)}")
    return "".join(line[1:] + "\n" for line in match.group(1).splitlines())


class RibbonScalingTest(unittest.TestCase):
    def test_patch_adds_header_without_libreoffice_types(self):
        header = header_from_patch()
        self.assertIn("namespace hst::ribbon", header)
        includes = re.findall(r"^#include\s+[<\"]([^>\"]+)[>\"]", header, re.M)
        self.assertEqual(sorted(includes), ["cstddef", "vector"])
        self.assertNotRegex(header, r"\b(OUString|tools::|vcl::|VclPtr|sal_)")

    @unittest.skipUnless(shutil.which("g++"), "no C++ compiler")
    def test_ladder(self):
        with tempfile.TemporaryDirectory() as tmp:
            with open(os.path.join(tmp, "HstRibbonScaling.hxx"), "w", encoding="utf-8") as handle:
                handle.write(header_from_patch())
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
