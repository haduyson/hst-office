# SPDX-License-Identifier: LicenseRef-HST-Proprietary
# Copyright (C) 2026 HASON TECH
"""Ribbon banner geometry (sfx2 HstBannerGeometry.hxx from hst-ribbon-banner.patch; the 1.0.2 mockup's banner in the
106 px body from hst-ribbon-mockup-frame.patch, class MockupFrameGeometryTest).

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
from test_ribbon_adaptive_scaling import geometry_after

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


FRAME = os.path.join(ROOT, "patches", "libreoffice", "hst-ribbon-mockup-frame.patch")
GEOMETRY = "include/vcl/HstBannerGeometry.hxx"

# 1100..1920 px at 100/125/150 %: body 106 logical px; banner w x w*104/360, 8 px from the right edge, centred
FRAME_DRIVER = r"""
#include "HstBannerGeometry.hxx"
#include <cmath>
#include <cstdio>
using namespace hst::banner;
static int failures = 0;
#define CHECK(c) do { if (!(c)) { std::printf("FAIL line %d W=%ld dpi=%.2f %s\n", __LINE__, W, dpi, #c); ++failures; } } while (0)
static Rect slotAt(long W, double dpi, long* pBody = nullptr)
{
    const long nDev = std::lround(W * dpi), nBody = scaled(RIBBON_BODY_HEIGHT, dpi);
    const Rect page{ 3, scaled(35, dpi) + 3, nDev - 6, nBody };
    if (pBody) *pBody = nBody;
    return slotFor(page, dpi, ART_WIDTH, windowSlotWidth(nDev, dpi), page.x + page.w - scaled(RIGHT_GAP, dpi));
}
int main()
{
    long W = 0; double dpi = 1.0;
    for (const double d : { 1.0, 1.25, 1.5 })
        for (long w = 1100; w <= 1920; w += 10)
        {
            W = w; dpi = d;
            long nBody = 0;
            const Rect s = slotAt(W, dpi, &nBody);
            const Rect page{ 3, scaled(35, dpi) + 3, std::lround(W * dpi) - 6, nBody };
            const long nLogical = W <= 1440 ? 260 : std::min(360L, 260 + (W - 1440) * 100 / 480);
            CHECK(s.w == std::lround(nLogical * dpi));
            CHECK(s.h == (s.w * 104 + 180) / 360);
            CHECK(s.h >= std::lround(75 * dpi) && s.h <= nBody);
            CHECK(s.x + s.w == page.x + page.w - scaled(8, dpi));
            const long nTop = s.y - page.y, nBottom = page.y + page.h - s.y - s.h;
            CHECK(nTop >= 0 && nBottom >= 0 && std::labs(nTop - nBottom) <= 1);
            CHECK(pageWidthBeside(page, s, dpi) == s.x - scaled(8, dpi) - page.x);
        }
    // the mockup's table (reference/mockup-expected.json, plan 4.2)
    W = 1366; dpi = 1.0;
    CHECK(slotAt(1366, 1.0).w == 260 && slotAt(1366, 1.0).h == 75);
    W = 1485; CHECK(slotAt(1485, 1.0).w == 269 && slotAt(1485, 1.0).h == 78);
    W = 1920; CHECK(slotAt(1920, 1.0).w == 360 && slotAt(1920, 1.0).h == 104);
    CHECK(slotAt(1920, 1.0).y == 35 + 3 + 1); // 1 px above and below, not 353 x 102
    W = 1280; dpi = 1.5; CHECK(slotAt(1280, 1.5).w == 390 && slotAt(1280, 1.5).h == 113);
    CHECK(scaled(RIBBON_BODY_HEIGHT, 1.0) == 106 && scaled(RIBBON_BODY_HEIGHT, 1.25) == 133
          && scaled(RIBBON_BODY_HEIGHT, 1.5) == 159);
    CHECK(compactSlot(1.0).w == 260 && compactSlot(1.0).h == 75);
    CHECK(compactSlot(1.25).w == 325 && compactSlot(1.25).h == 94);
    CHECK(compactSlot(1.5).w == 390 && compactSlot(1.5).h == 113);
    // no right edge: 4 px inside the page; no artwork: empty; a low page: never taller than it
    const Rect page{ 3, 41, 1479, 106 };
    CHECK(slotFor(page, 1.0).x + slotFor(page, 1.0).w == page.x + page.w - 4 && slotFor(page, 1.0, 0).w == 0);
    CHECK(slotFor(Rect{ 0, 0, 1400, 60 }, 1.0, ART_WIDTH, 360).h <= 60);
    std::printf("checks done, %d failure(s)\n", failures);
    return failures ? 1 : 0;
}
"""


def header_after_frame():
    """The geometry header as hst-ribbon-mockup-frame.patch leaves it."""
    with tempfile.TemporaryDirectory() as tree:
        os.makedirs(os.path.join(tree, os.path.dirname(GEOMETRY)))
        with open(os.path.join(tree, GEOMETRY), "w", encoding="utf-8") as handle:
            handle.write(geometry_after())
        text = open(FRAME, encoding="utf-8").read()
        hunk = "".join(p for p in re.split(r"(?m)^(?=--- a/)", text) if p.startswith(f"--- a/{GEOMETRY}"))
        subprocess.run(["patch", "-d", tree, "-p1", "-s", "--fuzz=0"], input=hunk, text=True, check=True)
        return open(os.path.join(tree, GEOMETRY), encoding="utf-8").read()


class MockupFrameGeometryTest(unittest.TestCase):
    @unittest.skipUnless(shutil.which("g++") and shutil.which("patch"), "no C++ compiler or patch tool")
    def test_banner_in_the_106_px_body(self):
        with tempfile.TemporaryDirectory() as tmp:
            open(os.path.join(tmp, "HstBannerGeometry.hxx"), "w", encoding="utf-8").write(header_after_frame())
            open(os.path.join(tmp, "frame.cxx"), "w", encoding="utf-8").write(FRAME_DRIVER)
            exe = os.path.join(tmp, "frame")
            build = subprocess.run(["g++", "-std=c++20", "-Wall", "-Werror", "-o", exe, os.path.join(tmp, "frame.cxx")],
                                   capture_output=True, text=True)
            self.assertEqual(build.returncode, 0, build.stderr)
            run = subprocess.run([exe], capture_output=True, text=True)
            self.assertEqual(run.returncode, 0, run.stdout)


if __name__ == "__main__":
    unittest.main()
