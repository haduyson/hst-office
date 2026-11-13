# SPDX-License-Identifier: AGPL-3.0-only
"""Compact banner geometry (HstBannerGeometry.hxx after hst-ribbon-banner-compact.patch).

Windows narrower than 1280 logical px show the 160x104 compact artwork, so the banner keeps a slot;
one-row ribbons show none. The slot keeps the exact artwork ratio and is centred on the page. The
header is rebuilt from hst-ribbon-banner.patch plus the compact patch and compiled with a driver
(skipped when no C++ compiler is available).
"""
import os
import re
import shutil
import subprocess
import tempfile
import unittest

from _paths import ROOT

PATCHES = os.path.join(ROOT, "patches", "libreoffice")
HEADER = "sfx2/source/notebookbar/HstBannerGeometry.hxx"
CHAIN = ("hst-ribbon-banner.patch", "hst-ribbon-banner-compact.patch", "hst-ribbon-banner-slot-anchor.patch",
         "hst-ribbon-banner-narrow.patch")

DRIVER = r"""
#include "HstBannerGeometry.hxx"
#include <cstdio>
using namespace hst::banner;
static int failures = 0;
#define CHECK(c) do { if (!(c)) { std::printf("FAIL %s:%d %s\n", __FILE__, __LINE__, #c); ++failures; } } while (0)
// h is w * 104 / artW rounded down: the slot ratio equals the artwork ratio up to one pixel of height
static bool ratioOk(const Rect& r, long artW) { return r.h * artW <= r.w * ART_HEIGHT && r.h * artW > r.w * ART_HEIGHT - artW; }
int main()
{
    // modes: wide from 1280 logical px, compact below, hidden for one-row ribbons at any width
    CHECK(modeFor(1280, 110, 1.0) == Mode::Wide);
    CHECK(modeFor(1279, 110, 1.0) == Mode::Compact);
    CHECK(modeFor(800, 110, 1.0) == Mode::Compact);
    CHECK(modeFor(1920, 40, 1.0) == Mode::Hidden);
    CHECK(modeFor(1000, 59, 1.0) == Mode::Hidden);
    CHECK(modeFor(2560, 220, 2.0) == Mode::Wide);
    CHECK(modeFor(2558, 220, 2.0) == Mode::Compact);
    CHECK(artWidth(Mode::Wide) == 360 && artWidth(Mode::Compact) == 160 && artWidth(Mode::Hidden) == 0);
    // wide slot: exact 360x104 at 100 %, centred in the 106 px of room, flush right as before
    const Rect page{ 3, 40, 1479, 110 };
    const Rect wide = slotFor(page, 1.0);
    CHECK(wide.w == 360 && wide.h == 104 && wide.y == 43);
    CHECK(wide.x + wide.w == page.x + page.w - 4);
    // a taller page (the 360x125 slot of the backlog) keeps the ratio: 360x104, centred
    const Rect tall = slotFor(Rect{ 0, 30, 1400, 129 }, 1.0);
    CHECK(tall.w == 360 && tall.h == 104 && tall.y == 30 + 2 + (125 - 104) / 2);
    // compact slot: 160x104 at 100 %, 320x208 at 200 %
    const Rect compact = slotFor(Rect{ 3, 40, 1000, 110 }, 1.0, artWidth(Mode::Compact));
    CHECK(compact.w == 160 && compact.h == 104 && compact.y == 43);
    CHECK(compact.x + compact.w == 3 + 1000 - 4);
    CHECK(pageWidthBeside(Rect{ 3, 40, 1000, 110 }, compact, 1.0) == compact.x - 8 - 3);
    const Rect compact2 = slotFor(Rect{ 6, 80, 2000, 220 }, 2.0, COMPACT_ART_WIDTH);
    CHECK(compact2.w == 320 && compact2.h == 208);
    // a low page gives smaller slots that keep the ratio and fit the page
    for (long h = 60; h <= 240; ++h)
        for (long art : { ART_WIDTH, COMPACT_ART_WIDTH })
        {
            const Rect r = slotFor(Rect{ 0, 0, 1400, h }, 1.0, art);
            CHECK(r.h <= h - 4 && r.w <= art && r.y >= 2 && r.y + r.h <= h - 2);
            CHECK(ratioOk(r, art));
        }
    // no artwork: empty slot, no division by zero
    const Rect none = slotFor(page, 1.0, 0);
    CHECK(none.w == 0 && none.h == 0);
    // the compact art uses the same height variants as the wide art
    CHECK(fit(Rect{ 0, 0, 160, 104 }, COMPACT_ART_WIDTH, ART_HEIGHT).h == 104);
    CHECK(sourceScale(208) == 2);
    // the wide slot narrows (ratio kept) when the tab's groups need the room, down to 260 logical px
    const Rect wpage{ 3, 40, 1479, 110 };
    CHECK(wideSlotWidth(wpage, -1, 0, 1.0) == 360);  // groups not measured yet: full width
    CHECK(wideSlotWidth(wpage, 1000, 0, 1.0) == 360);  // they fit beside the full slot
    CHECK(wideSlotWidth(wpage, 1479 - 12 - 300, 0, 1.0) == 300);  // the room they leave
    CHECK(wideSlotWidth(wpage, 1400, 0, 1.0) == 260);  // never narrower than the minimum
    CHECK(wideSlotWidth(Rect{ 6, 80, 2958, 220 }, 2958 - 24 - 600, 0, 2.0) == 600);  // scaled
    // hysteresis: a change of less than 12 px keeps the last width, the ends are always reached
    CHECK(wideSlotWidth(wpage, 1479 - 12 - 305, 300, 1.0) == 300);
    CHECK(wideSlotWidth(wpage, 1479 - 12 - 312, 300, 1.0) == 312);
    CHECK(wideSlotWidth(wpage, 1000, 355, 1.0) == 360 && wideSlotWidth(wpage, 1400, 265, 1.0) == 260);
    // the narrowed slot keeps the artwork ratio, centred on the page, flush right
    const Rect narrow = slotFor(wpage, 1.0, ART_WIDTH, 300);
    CHECK(narrow.w == 300 && ratioOk(narrow, ART_WIDTH) && narrow.x + narrow.w == wpage.x + wpage.w - 4);
    CHECK(narrow.y == wpage.y + 2 + (106 - narrow.h) / 2);
    CHECK(slotFor(wpage, 1.0, ART_WIDTH, 0).w == 360);  // no maximum: as before
    std::printf("checks done, %d failure(s)\n", failures);
    return failures ? 1 : 0;
}
"""


def file_section(patch_text, path):
    """The '--- a/... +++ b/...' section of one file in a patch."""
    sections = re.split(r"(?m)^(?=--- (?:a/|/dev/null))", patch_text)
    found = [s for s in sections if re.search(r"^\+\+\+ b/" + re.escape(path) + r"\s*$", s, re.M)]
    if len(found) != 1:
        raise AssertionError(f"{path} not changed exactly once")
    return found[0]


def header_after_chain(tmp):
    """Apply the header's sections of every patch in CHAIN, in order, to an empty tree."""
    for name in CHAIN:
        text = open(os.path.join(PATCHES, name), encoding="utf-8").read()
        run = subprocess.run(["patch", "-d", tmp, "-p1", "--fuzz=0", "-s", "-f"],
                             input=file_section(text, HEADER), capture_output=True, text=True)
        if run.returncode:
            raise AssertionError(f"{name}: {run.stdout}{run.stderr}")
    return open(os.path.join(tmp, HEADER), encoding="utf-8").read()


class RibbonBannerCompactTest(unittest.TestCase):
    @unittest.skipUnless(shutil.which("patch"), "no patch tool")
    def test_patch_chain_builds_header(self):
        with tempfile.TemporaryDirectory() as tmp:
            header = header_after_chain(tmp)
        self.assertIn("COMPACT_ART_WIDTH = 160", header)
        self.assertIn("inline Mode modeFor(", header)
        self.assertIn("constexpr bool SLOT_CENTRED = true;", header)  # shipped: centred on the page
        self.assertIn("constexpr long MIN_WINDOW_WIDTH = 1280;", header)  # compact card below, as before
        self.assertIn("constexpr long MIN_WIDE_ART_WIDTH = 260;", header)
        self.assertIn("inline long wideSlotWidth(", header)

    @unittest.skipUnless(shutil.which("g++") and shutil.which("patch"), "no C++ compiler or patch tool")
    def test_geometry(self):
        with tempfile.TemporaryDirectory() as tmp:
            tree = os.path.join(tmp, "tree")
            os.mkdir(tree)
            header = header_after_chain(tree)
            with open(os.path.join(tmp, "HstBannerGeometry.hxx"), "w", encoding="utf-8") as handle:
                handle.write(header)
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
