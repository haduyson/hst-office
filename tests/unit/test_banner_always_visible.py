# SPDX-License-Identifier: AGPL-3.0-only
"""The HASON TECH banner in every user interface and in HST PDF (hst-banner-always-visible.patch).

Owner decision 14/11/2026: no user interface hides the banner; it always draws its artwork, at least
260 x 75 logical px, in a strip at least that high. These tests read the patch and compile the strip
geometry (include/vcl/HstBannerGeometry.hxx, a new file of the patch) with a small driver.
"""
import os
import re
import shutil
import subprocess
import tempfile
import unittest

from patch_sections import added, after, sections

PATCH = "hst-banner-always-visible.patch"
GEOMETRY = "include/vcl/HstBannerGeometry.hxx"
CORE = "vcl/source/control/HstBannerCore.cxx"
BORDER = "vcl/source/window/brdwin.cxx"
TOOLBARS = "framework/source/layoutmanager/toolbarlayoutmanager.cxx"
TABS = "sfx2/source/notebookbar/NotebookbarTabControl.cxx"
UI = "xmlsecurity/uiconfig/ui/hstpdfviewer.ui"
WINDOW = "xmlsecurity/source/hstpdf/pdfviewerwindow.cxx"

DRIVER = r"""
#include "HstBannerGeometry.hxx"
#include <cstdio>
using namespace hst::banner;
static int failures = 0;
#define CHECK(x) do { if (!(x)) { std::printf("FAIL %s:%d %s\n", __FILE__, __LINE__, #x); ++failures; } } while (0)
int main()
{
    // the minimum strip holds the artwork at 260 x 75 (its 360:104 ratio) with 2 px margins
    CHECK(minStripHeight(1.0) == 79);
    const StripSlot min = stripSlot(minStripHeight(1.0), 1.0);
    CHECK(min.w == 260 && min.h == 75);
    // a lower strip never shrinks the banner below its minimum (the strip grows instead)
    const StripSlot low = stripSlot(40, 1.0);
    CHECK(low.w == 260 && low.h == 75);
    // a taller strip widens it, ratio kept, up to the artwork's logical size
    const StripSlot mid = stripSlot(94, 1.0);
    CHECK(mid.w == 311 && mid.h == 311 * 104 / 360);
    const StripSlot big = stripSlot(300, 1.0);
    CHECK(big.w == 360 && big.h == 104);
    // scaled windows (Windows 200 %)
    CHECK(minStripHeight(2.0) == 158);
    const StripSlot hidpi = stripSlot(minStripHeight(2.0), 2.0);
    CHECK(hidpi.w == 520 && hidpi.h == 150);
    std::printf("checks done, %d failure(s)\n", failures);
    return failures ? 1 : 0;
}
"""


def new_file(path):
    """Contents of a file the patch adds."""
    lines = sections(PATCH)[path]
    return "\n".join(line[1:] for line in lines if line.startswith("+")) + "\n"


class StripGeometry(unittest.TestCase):
    def test_header_is_new_in_vcl(self):
        header = new_file(GEOMETRY)
        self.assertIn("constexpr long MIN_STRIP_HEIGHT = 75;", header)
        self.assertIn("inline StripSlot stripSlot(", header)
        self.assertNotIn("COMPACT_ART_WIDTH", added(PATCH, CORE))  # the compact card is gone

    @unittest.skipUnless(shutil.which("g++"), "no C++ compiler")
    def test_strip_slot(self):
        with tempfile.TemporaryDirectory() as tmp:
            with open(os.path.join(tmp, "HstBannerGeometry.hxx"), "w", encoding="utf-8") as handle:
                handle.write(new_file(GEOMETRY))
            with open(os.path.join(tmp, "driver.cxx"), "w", encoding="utf-8") as handle:
                handle.write(DRIVER)
            exe = os.path.join(tmp, "driver")
            subprocess.run(["g++", "-std=c++17", "-o", exe, os.path.join(tmp, "driver.cxx")], check=True)
            run = subprocess.run([exe], capture_output=True, text=True)
            self.assertEqual(run.returncode, 0, run.stdout)


class EveryUserInterface(unittest.TestCase):
    def test_sfx2_files_moved_to_vcl(self):
        text = open(os.path.join(os.path.dirname(__file__), "..", "..", "patches", "libreoffice", PATCH),
                    encoding="utf-8").read()
        for path in ("HstBannerGeometry.hxx", "HstRibbonBanner.cxx", "HstRibbonBanner.hxx"):
            self.assertRegex(text, r"--- a/sfx2/source/notebookbar/%s\n\+\+\+ /dev/null" % re.escape(path))
        for path in ("include/vcl/HstBanner.hxx", CORE, "vcl/source/control/HstBanner.cxx",
                     "vcl/source/control/HstBannerWidget.cxx"):
            self.assertIn(path, sections(PATCH))
        self.assertIn("vcl/source/control/HstBannerCore \\", added(PATCH, "vcl/Library_vcl.mk"))

    def test_core_user_events_keep_the_core_alive(self):
        core = added(PATCH, CORE)
        # a reference link is only valid for vcl::Window instances: the core holds itself instead
        self.assertEqual(len(re.findall(r"PostUserEvent\([^;]*, false\);", core)), 2)
        self.assertEqual(core.count("acquire();"), 2)
        self.assertIn("Application::PostUserEvent(LINK(this, Core, DeliverHdl), pData.release(), false);", core)

    def test_tabbed_ribbon_claims_its_banner(self):
        self.assertIn("pBar->HstSetOwnBanner(true);", added(PATCH, TABS))
        self.assertNotIn("SetCompact", added(PATCH, TABS))

    def test_other_notebookbars_get_the_border_banner(self):
        border = added(PATCH, BORDER)
        self.assertIn("rTopBorder += HstNotebookBarStripHeight();", border)
        self.assertIn("!mpNotebookBar->HstHasOwnBanner()", border)
        self.assertIn("hst::banner::minStripHeight(GetDPIScaleFactor())", border)
        # a bar wider than its room (grouped compact) is cut at the banner, never painted under it
        self.assertIn("mpNotebookBar->SetWindowRegionPixel(", border)
        # screen readers find the border's banner as a child of the work window, like the notebookbar
        a11y = added(PATCH, "vcl/source/window/accessibility.cxx")
        self.assertIn("static_cast<ImplBorderWindow*>(pParent)->GetHstBanner() == this", a11y)
        self.assertIn("if (lcl_HstBorderBanner(pWorkWindow->mpWindowImpl->mpBorderWindow))", a11y)

    def test_toolbar_modes_reserve_the_top_docking_area(self):
        toolbars = added(PATCH, TOOLBARS)
        # height floor even without toolbars, rows beside the banner, recomputed when a notebookbar comes or goes
        self.assertIn("hst::banner::minStripHeight( implts_hstDpi() )", toolbars)
        self.assertIn("aRowContainerSize.setWidth( std::max< tools::Long >( 0, aContainerSize.Width() - nHstReserved ) );",
                      toolbars)
        self.assertIn("implts_hstBannerWanted() != m_bHstFloored", toolbars)
        for module in ("text.TextDocument", "sheet.SpreadsheetDocument", "presentation.PresentationDocument",
                       "drawing.DrawingDocument"):
            self.assertIn(f'"com.sun.star.{module}"', toolbars)
        self.assertNotIn("StartModule", toolbars)  # the Start Center has its own banner

    def test_no_setting_hides_it(self):
        text = "".join(added(PATCH, path) for path in sections(PATCH))
        self.assertNotRegex(text, r"officecfg|HideBanner|ShowBanner|BannerVisible")


class PdfViewer(unittest.TestCase):
    def test_two_rows_and_the_banner_at_the_right(self):
        ui = after(PATCH, UI)
        strip = ui.index('id="toolbarstrip"')
        self.assertLess(strip, ui.index('id="toolbar"'))
        self.assertLess(ui.index('id="toolrow1"'), ui.index('id="toolrow2"'))
        self.assertLess(ui.index('id="toolrow2"'), ui.index('class="GtkDrawingArea" id="banner"'))
        row1 = ui[ui.index('id="toolrow1"'):ui.index('id="toolrow2"')]
        row2 = ui[ui.index('id="toolrow2"'):ui.index('class="GtkDrawingArea" id="banner"')]
        self.assertEqual(re.findall(r'<object class="[^"]+" id="([^"]+)"', row1),
                         ["open", "print", "savecopy", "sep1", "zoomout", "zoom", "zoomentry", "zoomin",
                          "fitpage", "fitwidth", "rotate"])
        self.assertEqual(re.findall(r'<object class="[^"]+" id="([^"]+)"', row2),
                         ["prevpage", "pagelabel", "page", "pagecount", "nextpage", "sep2", "search",
                          "findprev", "findnext", "sep3", "edit", "sign", "sep4", "menu"])

    def test_banner_widget_is_built_and_reported(self):
        window = added(PATCH, WINDOW)
        self.assertIn('new weld::CustomWeld(*m_xBuilder, u"banner"_ustr, *m_xBanner)', window)
        self.assertIn("HstBannerWidget::MinimumSize(GetDPIScaleFactor()).Width() - 12", window)
        self.assertIn('u"BannerScreen"_ustr', window)
        # the weld before the controller, both before the builder goes
        self.assertLess(window.index("m_xBannerWeld.reset();"), window.index("m_xBanner.reset();"))


if __name__ == "__main__":
    unittest.main()
