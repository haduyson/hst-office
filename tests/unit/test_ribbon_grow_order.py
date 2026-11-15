# SPDX-License-Identifier: AGPL-3.0-only
"""Ribbon growth order and menu buttons at the small state (hst-ribbon-ux-grow-order.patch); the banner always wide.

fitByPriority() (vcl/inc/HstRibbonRegrow.hxx) collapses the least used groups first and lets the shown ones
grow back in the ladder's growth order when it has one (ladders::growths, generate-ribbon-priorities.py):
Sheets' Font group collapses last yet gives up its labels first. The headers are rebuilt from their
patches (engine patch, then this one) and compiled with small drivers (skipped without g++ or patch).
"""
import os
import re
import shutil
import subprocess
import tempfile
import unittest

from _paths import ROOT

PATCHES = os.path.join(ROOT, "patches", "libreoffice")
PATCH = "hst-ribbon-ux-grow-order.patch"
TOOLS = shutil.which("g++") and shutil.which("patch")


def read(patch):
    with open(os.path.join(PATCHES, patch), encoding="utf-8") as handle:
        return handle.read()


def added_file(patch, path):
    match = re.search(r"^\+\+\+ b/" + re.escape(path) + r"\n@@ [^\n]*\n((?:\+[^\n]*\n)+)", read(patch), re.M)
    if not match:
        raise AssertionError(f"{path} not added by {patch}")
    return "".join(line[1:] + "\n" for line in match.group(1).splitlines())


def section(patch, path):
    """The part of a patch that changes path, up to the next file."""
    match = re.search(r"^--- a/" + re.escape(path) + r"\n.*?(?=^--- |\Z)", read(patch), re.M | re.S)
    if not match:
        raise AssertionError(f"{path} not changed by {patch}")
    return match.group(0)


def apply(tmp, path, base, patches):
    """path written from base, then changed by each patch in turn; its final text."""
    full = os.path.join(tmp, path)
    os.makedirs(os.path.dirname(full), exist_ok=True)
    with open(full, "w", encoding="utf-8") as handle:
        handle.write(base)
    for patch in patches:
        run = subprocess.run(["patch", "-p1", "--fuzz=0", "-s", "-d", tmp], input=section(patch, path),
                             capture_output=True, text=True)
        if run.returncode:
            raise AssertionError(f"{patch}: {run.stdout}{run.stderr}")
    with open(full, encoding="utf-8") as handle:
        return handle.read()


def regrow_header(tmp):
    """HstRibbonRegrow.hxx as the series leaves it."""
    return apply(tmp, "vcl/inc/HstRibbonRegrow.hxx",
                 added_file("hst-ribbon-ux-engine.patch", "vcl/inc/HstRibbonRegrow.hxx"),
                 [PATCH, "hst-ribbon-ux-folded-groups.patch"])



REGROW_DRIVER = r"""
#include "HstRibbonRegrow.hxx"
#include <cstdio>
using namespace hst::ribbon;
static int failures = 0;
#define CHECK(c) do { if (!(c)) { std::printf("FAIL line %d: %s\n", __LINE__, #c); ++failures; } } while (0)
int main()
{
    // Sheets' Home: Bảng tạm, Phông chữ, Căn chỉnh, Số, Kiểu, Ô, Chỉnh sửa; widths L M S C. Font's labels
    // cost 110 px; Font is the most used group and collapses last
    const std::vector<Group> home = {
        { { 110, 110, 110, 95 }, false }, { { 525, 525, 415, 60 }, false }, { { 265, 265, 175, 70 }, false },
        { { 230, 230, 225, 50 }, false }, { { 130, 130, 70, 50 }, false }, { { 190, 190, 110, 45 }, false },
        { { 340, 340, 200, 80 }, false },
    };
    const std::vector<std::size_t> priority = { 1, 2, 3, 6, 4, 0, 5 };
    const std::vector<std::size_t> growth = { 6, 5, 4, 2, 3, 0, 1 };
    CHECK((growthOrder(7, priority, {}) == priority));
    CHECK((growthOrder(4, { 2, 9, 0 }, { 3, 1, 3 }) == std::vector<std::size_t>{ 3, 1, 2, 0 }));
    // room for every group at its largest but Font: by priority Font grows and Cells stays small; by the
    // growth order every other group grows and Font gives up its labels
    const long nRoom = 110 + 415 + 265 + 230 + 130 + 190 + 340 + 60;
    const Layout byPriority = fitByPriority(home, priority, nRoom);
    CHECK(byPriority.fits && byPriority.states[1] == 0 && byPriority.states[5] == 2);
    const Layout byGrowth = fitByPriority(home, priority, nRoom, growth);
    CHECK(byGrowth.fits && byGrowth.states[1] == 2 && byGrowth.width <= nRoom);
    for (std::size_t i : { 0, 2, 3, 4, 5, 6 })
        CHECK(byGrowth.states[i] == 0);
    // the growth order never changes which groups collapse: the least used, Font last
    for (long nWidth = 300; nWidth <= 2000; nWidth += 7)
    {
        const Layout a = fitByPriority(home, priority, nWidth);
        const Layout b = fitByPriority(home, priority, nWidth, growth);
        CHECK(a.fits == b.fits);
        if (!b.fits)
            continue;
        CHECK(b.width <= nWidth && b.width == rowWidth(home, b.states));
        for (std::size_t i = 0; i < home.size(); ++i)
            CHECK((a.states[i] == 3) == (b.states[i] == 3));
    }
    return failures ? 1 : 0;
}
"""

def compile_and_run(test, tmp, headers, driver):
    for name, text in headers.items():
        with open(os.path.join(tmp, name), "w", encoding="utf-8") as handle:
            handle.write(text)
    with open(os.path.join(tmp, "driver.cxx"), "w", encoding="utf-8") as handle:
        handle.write(driver)
    exe = os.path.join(tmp, "driver")
    build = subprocess.run(["g++", "-std=c++20", "-Wall", "-Wextra", "-Werror", "-o", exe,
                            os.path.join(tmp, "driver.cxx")], capture_output=True, text=True)
    test.assertEqual(build.returncode, 0, build.stderr)
    run = subprocess.run([exe], capture_output=True, text=True)
    test.assertEqual(run.returncode, 0, run.stdout)


class RibbonGrowOrderTest(unittest.TestCase):
    @unittest.skipUnless(TOOLS, "no C++ compiler or patch")
    def test_growth_order(self):
        with tempfile.TemporaryDirectory() as tmp:
            regrow = regrow_header(os.path.join(tmp, "tree"))
            self.assertIn("const std::vector<std::size_t>& rGrowth = {}", regrow)
            includes = re.findall(r"^#include\s+[<\"]([^>\"]+)[>\"]", regrow, re.M)
            self.assertEqual(sorted(includes), ["HstRibbonScaling.hxx", "cstddef", "vector"])
            compile_and_run(self, tmp, {
                "HstRibbonScaling.hxx": added_file("hst-ribbon-scaling-helper.patch", "vcl/inc/HstRibbonScaling.hxx"),
                "HstRibbonRegrow.hxx": regrow}, REGROW_DRIVER)

    def test_engine_wiring(self):
        text = read(PATCH)
        # every fitByPriority call of the box gets the ladder's growth order
        self.assertEqual(text.count("+    m_aHstPlanGrowth.clear();"), 1)
        self.assertEqual(len(re.findall(r"^\+.*(?:m_aHstPlanGrowth|aShownGrowth)\);$", text, re.M)), 3)
        self.assertIn("hst::ribbon::ladders::growths", text)
        # menu buttons drop their label at the small state only, and get it back
        self.assertIn("const bool bHide = nState == GroupSmall && !!rButton.GetModeImage();", text)
        self.assertIn("rButton.SetText(it->second.first);", text)
        self.assertIn("VclEventId::ObjectDying", text)

    def test_banner_always_wide(self):
        # owner decision: the wide banner at every width, never compact or hidden on a two-row ribbon; it
        # narrows down to its legible minimum and the groups collapse instead
        added = "".join(l for l in read("hst-ribbon-ux-banner-yield.patch").splitlines(True) if l.startswith("+"))
        self.assertIn("m_pHstBanner->SetCompact(false);", added)
        self.assertIn("? hst::banner::Mode::Wide", added)
        self.assertNotIn("Mode::Compact", added)
        self.assertNotIn("modeFor(", added)
        self.assertIn("hst::banner::wideSlotWidth(", added)

    def test_series_order(self):
        series = [n.strip() for n in read("series").splitlines() if n.strip() and not n.startswith("#")]
        if PATCH not in series:
            self.skipTest("not in the series yet")
        for before in ("hst-ribbon-ux-engine.patch", "hst-ribbon-scale-ladders-ux.patch",
                       "hst-ribbon-ux-banner-yield.patch"):
            self.assertLess(series.index(before), series.index(PATCH))


if __name__ == "__main__":
    unittest.main()
