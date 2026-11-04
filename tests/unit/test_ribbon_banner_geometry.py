# SPDX-License-Identifier: AGPL-3.0-only
"""Ribbon banner geometry (sfx2 HstBannerGeometry.hxx from hst-ribbon-banner.patch).

The slot adapts to the ribbon: its height comes from the tab page that holds the 2-row groups,
the width keeps the 360:104 ratio capped at 360 logical px, and every image, whatever its pixel
size, is aspect-fitted inside it. The header has no LibreOffice dependencies, so it is taken
from the patch and compiled with a small driver (skipped when no C++ compiler is available).
"""
import os
import re
import shutil
import subprocess
import tempfile
import unittest

from _paths import ROOT

PATCH = os.path.join(ROOT, "patches", "libreoffice", "hst-ribbon-banner.patch")
HEADER = "sfx2/source/notebookbar/HstBannerGeometry.hxx"

DRIVER = r"""
#include "HstBannerGeometry.hxx"
#include <cstdio>
using namespace hst::banner;
static int failures = 0;
#define CHECK(c) do { if (!(c)) { std::printf("FAIL %s:%d %s\n", __FILE__, __LINE__, #c); ++failures; } } while (0)
static bool inside(const Rect& a, const Rect& b)
{ return a.x >= b.x && a.y >= b.y && a.x + a.w <= b.x + b.w && a.y + a.h <= b.y + b.h; }
int main()
{
    // 100 %: Writer page of the Tabbed ribbon, 110 px high; the slot takes the page height
    const Rect page{ 3, 40, 1479, 110 };
    const Rect slot = slotFor(page, 1.0);
    CHECK(slot.h == 106 && slot.w == 360 && slot.y == 42);
    CHECK(slot.x + slot.w == page.x + page.w - 4);
    CHECK(pageWidthBeside(page, slot, 1.0) == slot.x - 8 - page.x);
    // a lower ribbon gives a smaller, proportional slot (never taller than the page)
    const Rect low = slotFor(Rect{ 0, 0, 1400, 90 }, 1.0);
    CHECK(low.h == 86 && low.w == 86 * 360 / 104);
    // 200 %: everything doubles, the width cap too
    const Rect hi = slotFor(Rect{ 6, 80, 2958, 220 }, 2.0);
    CHECK(hi.h == 212 && hi.w == 720 && hi.y == 84);
    // visibility: wide windows only, never in a one-row (compact) ribbon
    CHECK(visibleFor(1485, 110, 1.0));
    CHECK(visibleFor(1280, 110, 1.0));
    CHECK(!visibleFor(1279, 110, 1.0));
    CHECK(!visibleFor(1100, 110, 1.0));
    CHECK(!visibleFor(1485, 40, 1.0));
    CHECK(visibleFor(2970, 220, 2.0));
    CHECK(!visibleFor(2200, 220, 2.0));
    // artwork 360x104 in the inner box: fitted, centred, aspect kept
    const Rect box{ 3, 3, 354, 100 };
    const Rect art = fit(box, 360, 104);
    CHECK(art.h == 100 && art.w == 346 && inside(art, box));
    // an oversized remote image (2000x600) is fitted, it never grows the slot
    const Rect big = fit(box, 2000, 600);
    CHECK(big.h == 100 && big.w == 333 && big.x == 13 && inside(big, box));
    // odd sizes: very wide, very tall, tiny and huge all stay inside the box
    const long sizes[][2] = { { 5000, 10 }, { 10, 5000 }, { 1, 1 }, { 100000, 30000 }, { 359, 105 } };
    for (const auto& s : sizes)
    {
        const Rect r = fit(box, s[0], s[1]);
        CHECK(inside(r, box) && r.w >= 1 && r.h >= 1);
    }
    CHECK(fit(box, 0, 10).w == 0);
    // source variant: exact size uses its variant, otherwise the next larger one (downscale only)
    CHECK(sourceScale(104) == 1);
    CHECK(sourceScale(100) == 2);
    CHECK(sourceScale(208) == 2);
    CHECK(sourceScale(200) == 3);
    CHECK(sourceScale(312) == 3);
    CHECK(sourceScale(900) == 3);
    std::printf("checks done, %d failure(s)\n", failures);
    return failures ? 1 : 0;
}
"""


def header_from_patch():
    """Contents of the new geometry header as added by the patch."""
    text = open(PATCH, encoding="utf-8").read()
    match = re.search(r"^\+\+\+ b/" + re.escape(HEADER) + r"\n@@ [^\n]*\n((?:\+[^\n]*\n)+)", text, re.M)
    if not match:
        raise AssertionError(f"{HEADER} not added by {os.path.basename(PATCH)}")
    return "".join(line[1:] + "\n" for line in match.group(1).splitlines())


class RibbonBannerGeometryTest(unittest.TestCase):
    def test_patch_adds_header(self):
        header = header_from_patch()
        self.assertIn("namespace hst::banner", header)
        self.assertIn("ART_WIDTH = 360", header)
        self.assertIn("MIN_WINDOW_WIDTH = 1280", header)

    @unittest.skipUnless(shutil.which("g++"), "no C++ compiler")
    def test_geometry(self):
        with tempfile.TemporaryDirectory() as tmp:
            with open(os.path.join(tmp, "HstBannerGeometry.hxx"), "w", encoding="utf-8") as handle:
                handle.write(header_from_patch())
            with open(os.path.join(tmp, "driver.cxx"), "w", encoding="utf-8") as handle:
                handle.write(DRIVER)
            exe = os.path.join(tmp, "driver")
            build = subprocess.run(["g++", "-std=c++20", "-Wall", "-Werror", "-o", exe, os.path.join(tmp, "driver.cxx")],
                                   capture_output=True, text=True)
            self.assertEqual(build.returncode, 0, build.stderr)
            run = subprocess.run([exe], capture_output=True, text=True)
            self.assertEqual(run.returncode, 0, run.stdout)


if __name__ == "__main__":
    unittest.main()
