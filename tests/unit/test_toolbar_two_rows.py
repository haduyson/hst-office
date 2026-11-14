# SPDX-License-Identifier: AGPL-3.0-only
"""Two even toolbar rows beside the window banner (hst-toolbar-two-rows.patch).

vcl/inc/HstToolbarRows.hxx decides where the lone docked toolbar of the Single toolbar and Sidebar user
interfaces breaks into its second row. The header has no LibreOffice dependencies, so it is taken from the
patch and compiled with a small driver (skipped without a C++ compiler); the wiring in vcl and framework is
checked on the patch text.
"""
import os
import shutil
import subprocess
import tempfile
import unittest

from _paths import ROOT
from patch_sections import added

PATCH = "hst-toolbar-two-rows.patch"
HEADER = "vcl/inc/HstToolbarRows.hxx"

DRIVER = r"""
#include "HstToolbarRows.hxx"
#include <cstdio>
#include <cstdlib>
using namespace hst::toolbar;
static int failures = 0;
#define CHECK(c) do { if (!(c)) { std::printf("FAIL %s:%d %s\n", __FILE__, __LINE__, #c); ++failures; } } while (0)
static RowItem B(long w = 26) { return RowItem{ w, true, false, true }; }
static RowItem S() { return RowItem{ 7, true, true, false }; }
static RowItem W(long w) { return RowItem{ w, true, false, false }; } // item window (font name box)
static RowItem H() { return RowItem{ 26, false, false, true }; } // hidden button
static long row(const std::vector<RowItem>& v, std::size_t from, std::size_t to)
{ long n = 0; for (std::size_t i = from; i < to; ++i) if (v[i].bVisible) n += v[i].nWidth; return n; }
static long diff(const std::vector<RowItem>& v, std::size_t b)
{ return std::labs(row(v, 0, b) - row(v, b, v.size())); }
// the rows as drawn: a separator that ends the first row is not drawn
static long shown(const std::vector<RowItem>& v, std::size_t b)
{ return std::labs(row(v, 0, b) - (v[b - 1].bSeparator ? v[b - 1].nWidth : 0) - row(v, b, v.size())); }
int main()
{
    // nothing to split
    CHECK(balancedBreak({}) == 0);
    CHECK(balancedBreak({ B() }) == 0);
    CHECK(balancedBreak({ S(), S() }) == 0);
    // 8 equal buttons: 4 + 4
    {
        std::vector<RowItem> v(8, B());
        CHECK(balancedBreak(v) == 4);
    }
    // 7 buttons: the top row is the longer one (4 + 3)
    {
        std::vector<RowItem> v(7, B());
        CHECK(balancedBreak(v) == 4);
    }
    // groups 4 | 3 | 1: the break after the first separator keeps the groups whole and the rows even
    {
        std::vector<RowItem> v{ B(), B(), B(), B(), S(), B(), B(), B(), S(), B() };
        CHECK(balancedBreak(v) == 5);
    }
    // groups 3 | 2 | 1: a group break would leave the rows a button and more apart, it breaks inside a group
    {
        std::vector<RowItem> v{ B(), B(), B(), S(), B(), B(), S(), B() };
        CHECK(balancedBreak(v) == 4 || diff(v, balancedBreak(v)) <= 26);
    }
    // groups 3 | 3: within one button (the trailing separator counts in the top row)
    {
        std::vector<RowItem> v{ B(), B(), B(), S(), B(), B(), B() };
        CHECK(balancedBreak(v) == 4);
    }
    // one big group and a small one: an even break inside the group wins over a lopsided group break
    {
        std::vector<RowItem> v{ B(), B(), B(), B(), B(), B(), B(), B(), B(), B(), S(), B() };
        const std::size_t b = balancedBreak(v);
        CHECK(!v[b - 1].bSeparator);
        CHECK(diff(v, b) <= 26);
    }
    // the break after a separator lands right after it, also when hidden items follow it
    {
        std::vector<RowItem> v{ B(), B(), B(), S(), H(), H(), B(), B(), B() };
        CHECK(balancedBreak(v) == 4);
    }
    // a row never starts with a separator, hidden items do not count
    {
        std::vector<RowItem> v{ B(), H(), H(), H(), B(), S(), S(), B(), B() };
        const std::size_t b = balancedBreak(v);
        CHECK(b > 0 && !v[b].bSeparator);
    }
    // a wide item window (font name box) is weighed by its width
    {
        std::vector<RowItem> v{ W(150), S(), B(), B(), B(), B(), B(), B(), B(), B(), B(), B() };
        const std::size_t b = balancedBreak(v);
        CHECK(diff(v, b) <= 26);
    }
    // the evenest break at all is never beaten by more than one button
    {
        std::vector<RowItem> v{ B(), B(), S(), B(40), B(), S(), B(), B(), B(), S(), W(90), B(), S(), B(), B() };
        long best = -1;
        for (std::size_t i = 1; i < v.size(); ++i)
            if (!v[i].bSeparator && (best < 0 || diff(v, i) < best))
                best = diff(v, i);
        CHECK(diff(v, balancedBreak(v)) <= best + 26);
    }
    // Writer's Sidebar interface (standardbar, gtk3 at 100 %, 33 and 44 px buttons): the evenest break is the
    // group break, 601 and 637 px as drawn: within one button
    {
        const long G = 8;
        std::vector<RowItem> v{ B(44), B(44), B(44), RowItem{ G, true, true, false }, B(33), B(33), B(33),
            RowItem{ G, true, true, false }, B(33), B(33), B(44), RowItem{ G, true, true, false }, B(33),
            RowItem{ G, true, true, false }, B(44), B(44), RowItem{ G, true, true, false }, B(33), B(33), B(33),
            RowItem{ G, true, true, false }, B(44), B(33), B(33), B(33), RowItem{ G, true, true, false }, B(33),
            B(44), B(44), RowItem{ G, true, true, false }, B(33), B(33), B(33), B(33), B(33),
            RowItem{ G, true, true, false }, B(33), B(33), RowItem{ G, true, true, false }, B(33), B(44), B(33) };
        CHECK(balancedBreak(v) == 21 && shown(v, 21) == 36);
    }
    CHECK(typicalButtonWidth({ B(26), B(26), B(38), W(150) }) == 26);
    std::printf("checks done, %d failure(s)\n", failures);
    return failures ? 1 : 0;
}
"""


class ToolbarTwoRowsTest(unittest.TestCase):
    def test_series_lists_patch_after_banner_host(self):
        with open(os.path.join(ROOT, "patches", "libreoffice", "series"), encoding="utf-8") as handle:
            series = [line.strip() for line in handle if line.strip() and not line.startswith("#")]
        self.assertIn(PATCH, series)
        self.assertLess(series.index("hst-banner-always-visible.patch"), series.index(PATCH))

    def test_vcl_opt_in_only(self):
        header = added(PATCH, "include/vcl/toolbox.hxx")
        self.assertIn("void                HstSetBalancedLines( sal_uInt16 nLines );", header)
        self.assertIn("mnHstBalancedLines = 0", added(PATCH, "vcl/inc/toolbox.h"))  # vcl only: no ABI change
        code = added(PATCH, "vcl/source/window/toolbox.cxx")
        # docked, horizontal, with the menu, and only when asked for
        self.assertIn("mnHstBalancedLines >= 2 && mbHorz && !ImplIsFloatingMode() && IsMenuEnabled()", code)
        self.assertIn("hst::toolbar::balancedBreak( aRow )", code)
        self.assertIn("!ImplHstBalanced()", code)  # no single-line stretch for two rows
        self.assertNotIn("CallEventListeners", code)

    def test_framework_opts_in_for_lone_toolbar_beside_banner(self):
        code = added(PATCH, "framework/source/layoutmanager/toolbarlayoutmanager.cxx")
        self.assertIn("bBanner && rRows.size() == 1 && rRows[0].aRowColumnWindows.size() == 1", code)
        self.assertIn("aTwoRows.Height() <= nTopHeight && aTwoRows.Width() <= nRowWidth", code)
        self.assertIn("implts_hstTwoRowsOff( e.Source )", code)
        # nothing of the two rows reaches the persisted window state
        self.assertNotIn("implts_writeWindowStateData", code)

    @unittest.skipUnless(shutil.which("g++"), "no C++ compiler")
    def test_break_placement(self):
        with tempfile.TemporaryDirectory() as tmp:
            with open(os.path.join(tmp, "HstToolbarRows.hxx"), "w", encoding="utf-8") as handle:
                handle.write(added(PATCH, HEADER) + "\n")
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
