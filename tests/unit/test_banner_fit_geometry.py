# SPDX-License-Identifier: LicenseRef-HST-Proprietary
# Copyright (C) 2026 HASON TECH
"""The banner fits snugly: its slot is exactly its artwork (include/vcl/HstBannerGeometry.hxx as the patch series
leaves it, compiled with a small driver; skipped when no C++ compiler or patch tool is available).

A host gives the banner a room; the banner takes the artwork's width at the room's height (snugSlot) and paints the
artwork over its whole allocation (artRect): no inset, no letterbox, no filler band, at 100 % and 125 %, for the
bundled 360 x 104 artwork (1x, 2x, 3x) and the standard 360/640/960 x 96 sizes; the Start Center's slot takes the
artwork's height for the column's width (heightForWidth).
"""
import os
import re
import shutil
import subprocess
import tempfile
import unittest

from _paths import ROOT

PATCHES = os.path.join(ROOT, "patches", "libreoffice")
GEOMETRY = "include/vcl/HstBannerGeometry.hxx"


def geometry_header(tree):
    """Write the geometry header as the whole series leaves it into tree; returns its path."""
    with open(os.path.join(PATCHES, "series"), encoding="utf-8") as handle:
        series = [line.strip() for line in handle if line.strip() and not line.startswith("#")]
    os.makedirs(os.path.join(tree, os.path.dirname(GEOMETRY)))
    for name in series:
        with open(os.path.join(PATCHES, name), encoding="utf-8") as handle:
            text = handle.read()
        parts = re.split(r"(?m)^(?=--- (?:a/|/dev/null))", text)
        hunk = "".join(p for p in parts if re.search(rf"(?m)^\+\+\+ b/{re.escape(GEOMETRY)}$", p))
        if hunk:
            subprocess.run(["patch", "-d", tree, "-p1", "-s", "-F0"], input=hunk, text=True, check=True)
    return os.path.join(tree, GEOMETRY)


DRIVER = r"""
#include "HstBannerGeometry.hxx"
#include <cstdio>
using namespace hst::banner;
static int failures = 0;
#define CHECK(c) do { if (!(c)) { std::printf("FAIL line %d: %s\n", __LINE__, #c); ++failures; } } while (0)
static bool whole(const Rect& r, long w, long h) { return r.x == 0 && r.y == 0 && r.w == w && r.h == h; }
int main()
{
    // the ribbon: a room 96 logical px high and 360..960 wide, at 100 % and 125 %
    for (double fDpi : { 1.0, 1.25 })
    {
        const long nH = scaled(96, fDpi);
        const Rect room{ 500, 46, scaled(700, fDpi), nH };
        // the bundled artwork (1x, 2x and 3x variants have one ratio)
        for (long nScale : { 1L, 2L, 3L })
        {
            const long aw = 360 * nScale, ah = 104 * nScale;
            const Rect left = snugSlot(room, aw, ah, true);
            CHECK(left.x == room.x && left.y == room.y && left.h == nH);
            CHECK(left.w == widthForHeight(nH, aw, ah) && left.w < room.w);
            const Rect right = snugSlot(room, aw, ah, false);
            CHECK(right.x + right.w == room.x + room.w && right.w == left.w);
            // painted over the whole allocation: no background pixel around the artwork
            CHECK(whole(artRect(left.w, left.h, aw, ah), left.w, left.h));
        }
        // the standard sizes are 96 high: exactly their width
        for (long nWidth : { 360L, 640L, 960L })
        {
            const Rect slot = snugSlot(Rect{ 0, 0, scaled(960, fDpi), nH }, nWidth, 96, true);
            CHECK(slot.w == scaled(nWidth, fDpi) && slot.h == nH);
            CHECK(whole(artRect(slot.w, slot.h, nWidth * 2, 96 * 2), slot.w, slot.h));
        }
        // the compact ribbon and the toolbar strip: a 260 x 75 room holds the bundled artwork exactly
        const Rect strip = snugSlot(Rect{ 0, 0, scaled(260, fDpi), scaled(75, fDpi) }, 360, 104, false);
        CHECK(whole(artRect(strip.w, strip.h, 360, 104), strip.w, strip.h));
        // the Start Center: the column's width, the artwork's height
        for (long nColumn : { 248L, 260L, 310L })
        {
            const long w = scaled(nColumn, fDpi);
            for (long nArtW : { 360L, 640L })
            {
                const long nArtH = nArtW == 360 ? 104 : 96;
                const long h = heightForWidth(w, nArtW, nArtH);
                CHECK(whole(artRect(w, h, nArtW, nArtH), w, h));
            }
        }
    }
    // a room too narrow for the artwork's width at its height: full width, the artwork's height, centred
    const Rect narrow = snugSlot(Rect{ 0, 0, 200, 96 }, 360, 104, false);
    CHECK(narrow.w == 200 && narrow.h == heightForWidth(200, 360, 104) && narrow.y == (96 - narrow.h) / 2);
    // a slot of another ratio (a new artwork before the host resized it) is fitted, centred
    const Rect other = artRect(700, 96, 360, 104);
    CHECK(other.h == 96 && other.w == 332 && other.x == (700 - 332) / 2);
    // nothing to paint
    CHECK(artRect(0, 96, 360, 104).w == 0);
    CHECK(snugSlot(Rect{ 0, 0, 0, 96 }, 360, 104, true).w == 0);
    CHECK(widthForHeight(96, 0, 104) == 0 && heightForWidth(260, 360, 0) == 0);
    std::printf("%d failure(s)\n", failures);
    return failures;
}
"""


class BannerFitGeometry(unittest.TestCase):
    @unittest.skipUnless(shutil.which("g++") and shutil.which("patch"), "no C++ compiler or patch tool")
    def test_the_slot_is_exactly_the_artwork(self):
        with tempfile.TemporaryDirectory() as tmp:
            header = geometry_header(os.path.join(tmp, "tree"))
            shutil.copy(header, os.path.join(tmp, "HstBannerGeometry.hxx"))
            with open(os.path.join(tmp, "d.cxx"), "w", encoding="utf-8") as handle:
                handle.write(DRIVER)
            build = subprocess.run(["g++", "-std=c++17", "-Wall", "-Werror", "-I", tmp, "-o",
                                    os.path.join(tmp, "d"), os.path.join(tmp, "d.cxx")],
                                   capture_output=True, text=True)
            self.assertEqual(build.returncode, 0, build.stderr[-2000:])
            run = subprocess.run([os.path.join(tmp, "d")], capture_output=True, text=True)
            self.assertEqual(run.returncode, 0, run.stdout)


if __name__ == "__main__":
    unittest.main()
