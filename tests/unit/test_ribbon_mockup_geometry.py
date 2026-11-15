# SPDX-License-Identifier: AGPL-3.0-only
"""Ribbon buttons and groups at the approved 1.0.2 mockup's geometry (hst-ribbon-mockup-geometry.patch):
vcl/inc/HstRibbonGeometry.hxx (new) and vcl/inc/HstRibbonGrid.hxx (as hst-ribbon-adaptive-grid.patch creates it,
then this patch) compiled with a driver, and the wiring into ToolBox, the ladder and the ribbon paint."""
import os
import shutil
import subprocess
import tempfile
import unittest

from patch_sections import added, sections

PATCH = "hst-ribbon-mockup-geometry.patch"
GRID = "vcl/inc/HstRibbonGrid.hxx"
GEOMETRY = "vcl/inc/HstRibbonGeometry.hxx"

DRIVER = r"""
#include "HstRibbonGrid.hxx"
#include <cstdio>
using namespace hst::ribbon;
using namespace hst::ribbon::geometry;
static int failures = 0;
#define CHECK(x) do { if (!(x)) { std::printf("FAIL %d %s\n", __LINE__, #x); ++failures; } } while (0)
int main()
{
    // labels split as the mockup's twoLines(): Dán, Cỡ chữ stay; Sao chép | định dạng; Chèn chú | thích
    CHECK(firstLineWords({ 3 }) == 1 && firstLineWords({ 2, 3 }) == 2);
    CHECK(firstLineWords({ 3, 4, 4, 4 }) == 2 && firstLineWords({ 4, 3, 5 }) == 2);
    CHECK(firstLineWords({ 2, 3 }, true) == 1 && firstLineWords({}) == 0);
    CHECK(LABEL_WRAP == 72);
    // a large button: 76 high, at least 42 wide, icon in the 32 px slot 6 px down, label after PushButton's gap
    LargeButton l = largeButton(24, 30, 0, true, 17, 1.0);
    CHECK(l.height == 76 && l.width == 42 && l.iconY == 10 && l.textY == 38 && l.linePitch == 17 && l.arrowWidth == 7);
    l = largeButton(24, 50, 56, true, 17, 1.0);
    CHECK(l.arrowWidth == 10 && l.width == 56 + 10 + 8);
    CHECK(l.textY + 2 * l.linePitch <= l.height);
    l = largeButton(36, 75, 80, false, 25, 1.5);
    CHECK(l.height == 114 && l.iconY == 14 && l.textY == 14 + 36 + 8 && l.textY + 2 * l.linePitch <= l.height - 6);
    // Paste's 32 px icon: the same label line as a 24 px icon, the icon on the same centre
    LargeButton p = largeButton(32, 30, 0, true, 17, 1.0);
    CHECK(p.textY == 38 && p.iconY == 6);
    // a taller font moves the icon up so that two lines keep 4 px over the bottom (PushButton's frame)
    l = largeButton(24, 30, 40, false, 18, 1.0);
    CHECK(l.iconY == 7 && l.textY == 7 + 24 + 5 && l.textY + 2 * 18 == 76 - 4);
    // medium: 4 + icon + 5 + label + 4; small: 22; split: + 12
    // the icon at (4, 4) whether the button has a label or not: an icon-only button is 4 + 16 + 4
    CHECK(smallButtonWidth(16, 40, false, 1.0) == 69 && smallButtonWidth(16, 0, false, 1.0) == 24);
    CHECK(smallButtonWidth(16, 0, true, 1.0) == 36 && smallButtonWidth(24, 0, false, 1.5) == 36);
    // two rows spread over the 76 px content: icons at 9 + 4 = 13 and 9 + 24 + 9 + 4 = 46 (mockup 13.3, 46.7)
    CHECK(twoRowGap(1.0) == 9 && twoRowGap(1.5) == 14);
    // folded: 98 high, the name's last line 4 px over the bottom
    FoldedButton f = foldedButton(24, 20, 20, 1, 17, 1.0);
    CHECK(f.height == 98 && f.width == 48 && f.iconY == 6 && f.textY == 98 - 4 - 17 && f.arrowWidth == 11);
    CHECK(foldedButton(24, 80, 60, 2, 17, 1.0).width == 80 + 12 && foldedButton(24, 80, 60, 2, 17, 1.0).textY == 60);
    // the 3-row grid: four items are two columns of two; five are three and two; seven are 3, 3, 1
    std::vector<GridItem> items(4, GridItem{ 30, 24 });
    GridLayout g = gridLayout(items, 3, 24, 2, 2, 7);
    CHECK(g.cells[1].y == 26 && g.cells[2].x == 32 && g.cells[2].y == 0 && g.cells[3].y == 26 && g.width == 62);
    items.assign(5, GridItem{ 30, 24 });
    g = gridLayout(items, 3, 24, 2, 2, 7);
    CHECK(g.cells[2].x == 0 && g.cells[2].y == 52 && g.cells[3].x == 32 && g.cells[4].y == 26);
    items.assign(7, GridItem{ 30, 24 });
    g = gridLayout(items, 3, 24, 2, 2, 7);
    CHECK(g.cells[6].x == 64 && g.cells[6].y == 0);
    // runs between separators are balanced on their own: 2 | 4 -> one column of 2, two of 2
    items = { { 30, 24 }, { 30, 24 }, { 0, 0, true }, { 30, 24 }, { 30, 24 }, { 30, 24 }, { 30, 24 } };
    g = gridLayout(items, 3, 24, 2, 2, 7);
    CHECK(g.cells[1].y == 26 && g.cells[4].y == 26 && g.cells[5].y == 0 && g.cells[5].x > g.cells[3].x);
    // a group authored with three rows: its caption in row 3, three large buttons 3 rows high stack in a column
    std::vector<GroupCell> cells{ { 0, 3, 4, 1, false, true }, { 0, 0, 1, 3, true }, { 1, 0, 1, 3, true },
                                  { 2, 0, 1, 3, true }, { 3, 0, 1, 1 }, { 3, 1, 1, 1 }, { 3, 2, 1, 1 },
                                  { 4, 0, 1, 4 } };
    CHECK(contentRows(cells) == 3);
    CHECK(stackGroup(cells));
    CHECK(cells[1].left == 0 && cells[2].top == 1 && cells[3].top == 2 && cells[3].left == 0);
    CHECK(cells[4].left == 1 && cells[6].top == 2 && cells[7].left == 2 && cells[7].height == 4);
    CHECK(cells[0].top == 3 && cells[0].width == 2);
    std::printf("checks done, %d failure(s)\n", failures);
    return failures ? 1 : 0;
}
"""


def new_file(name, path):
    return "\n".join(line[1:] for line in sections(name)[path] if line.startswith("+")) + "\n"


def hunks(name, path):
    """The unified diff of one file of a patch, as `patch` reads it."""
    return f"--- a/{path}\n+++ b/{path}\n" + "\n".join(sections(name)[path]) + "\n"


class MockupGeometry(unittest.TestCase):
    @unittest.skipUnless(shutil.which("g++") and shutil.which("patch"), "no C++ compiler or patch")
    def test_geometry_and_grid(self):
        with tempfile.TemporaryDirectory() as tmp:
            for name, path in (("hst-ribbon-adaptive-grid.patch", GRID), (PATCH, GEOMETRY)):
                with open(os.path.join(tmp, os.path.basename(path)), "w", encoding="utf-8") as handle:
                    handle.write(new_file(name, path))
            with open(os.path.join(tmp, "grid.diff"), "w", encoding="utf-8") as handle:
                handle.write(hunks(PATCH, GRID))
            subprocess.run(["patch", "-s", os.path.join(tmp, "HstRibbonGrid.hxx"), os.path.join(tmp, "grid.diff")],
                           check=True)
            with open(os.path.join(tmp, "driver.cxx"), "w", encoding="utf-8") as handle:
                handle.write(DRIVER)
            exe = os.path.join(tmp, "driver")
            subprocess.run(["g++", "-std=c++17", "-Wall", "-o", exe, os.path.join(tmp, "driver.cxx")], check=True)
            run = subprocess.run([exe], capture_output=True, text=True)
            self.assertEqual(run.returncode, 0, run.stdout)

    def test_toolbox_draws_ribbon_buttons_at_the_geometry(self):
        toolbox = added(PATCH, "vcl/source/window/toolbox.cxx")
        self.assertIn("if (!rData.mbHstOwnerDraw || !bHorz || !bImage || rItem.mpWindow", toolbox)
        self.assertIn("hst::ribbon::geometry::firstLineWords(aWords, bTooWide)", toolbox)
        self.assertIn("item.maItemSize = item.maContentSize = Size( aLarge.width, aLarge.height );", toolbox)
        self.assertIn("&& ( meTextPosition == ToolBoxTextPosition::Right ) && !mpData->mbHstOwnerDraw )", toolbox)
        self.assertIn("nImageOffY = pItem->maRect.Top() + aHstLarge.iconY;", toolbox)
        # a ribbon toolbox's rows are as high as its buttons and visible item windows, not a native combo box
        self.assertIn("if ( mpData->mbHstOwnerDraw )\n        mnWinHeight = 0;", toolbox)
        # the icon of a medium and of a small button at the same (4, 4)
        self.assertIn("nImageOffX = pItem->maRect.Left() + hst::ribbon::geometry::px(hst::ribbon::geometry::SMALL_PAD", toolbox)

    def test_ladder_places_menu_buttons_and_frames_groups(self):
        ladder = added(PATCH, "vcl/source/control/HstRibbonLadder.cxx")
        self.assertIn("aLarge.textY - geometry::imageTextGap(rButton.GetTextHeight()) - aImage.Height() - nInner", ladder)
        self.assertIn("placeLargeMenuButton(rButton, rLabel, bLarge);", ladder)
        self.assertIn("normaliseGroupFrame(*pGrid, aChildren, aCells);", ladder)
        self.assertIn("aCells[i].caption = aCells[i].top >= 2 && aCells[i].top == nBottom", ladder)
        self.assertIn("aCells[i].height == nContentRows && !keepsLarge(*aChildren[i]);", ladder)
        # the alternative layout of Writer's Paragraph at the small size, and its hidden boxes kept in the key
        self.assertIn('{ u"gdHomeParagraph", GroupSmall, 3, 3,', ladder)
        self.assertIn("rToolBox.IsVisible() || hiddenByLayout().count(&rToolBox)", ladder)

    def test_writer_style_gallery_is_shown_at_every_size(self):
        # Writer's Styles gallery shares Sheets' id bxHomeStylesPreview but has no Cell Styles button: the per-size
        # visibility applies only where both are in the group, so Writer keeps 6/4/3 tiles at L/M/S
        ladder = added(PATCH, "vcl/source/control/HstRibbonLadder.cxx")
        self.assertIn('{ u"bxHomeStylesPreview", u"btnHomeHstCellStyles", 1 << GroupLarge },', ladder)
        self.assertIn("if (hasId(rWindow, rShown.id) && hasSibling(rWindow, rShown.sibling))", ladder)
        writer = os.path.join(os.path.dirname(__file__), "..", "..", "patches", "libreoffice",
                              "hst-ribbon-mockup-writer.patch")
        if os.path.exists(writer):
            with open(writer, encoding="utf-8") as handle:
                self.assertNotIn("btnHomeHstCellStyles", handle.read())

    def test_file_button_is_24_px_centred(self):
        self.assertIn("inline constexpr tools::Long FILE_BUTTON_HEIGHT = 24;", added(PATCH, "include/vcl/HstRibbonPaint.hxx"))
        paint = added(PATCH, "vcl/source/control/HstRibbonPaint.cxx")
        self.assertIn("rItem.Top() + (rItem.GetHeight() - nHeight) / 2", paint)

    def test_only_the_caption_row_expands(self):
        ladder = added(PATCH, "vcl/source/control/HstRibbonLadder.cxx")
        self.assertIn("setIfChanged<bool>(rChild.get_vexpand(), false", ladder)
        self.assertIn("eSize == ToolBoxButtonSize::Size32", ladder)

    def test_icon_dump_is_opt_in(self):
        toolbox = added(PATCH, "vcl/source/window/toolbox.cxx")
        self.assertIn('const char* pPath = std::getenv("HST_RIBBON_DUMP_ICONS");', toolbox)
        self.assertIn("if ( eHst != HstKind::None )\n            ImplHstDumpIcon(", toolbox)

    def test_menu_buttons_use_the_tool_font(self):
        ladder = added(PATCH, "vcl/source/control/HstRibbonLadder.cxx")
        self.assertIn("rButton.SetControlFont(rToolFont);", ladder)

    def test_folded_button_contract(self):
        header = added(PATCH, "include/vcl/HstRibbonPaint.hxx")
        self.assertIn("VCL_DLLPUBLIC Size FoldedButtonSize(const OutputDevice& rDev", header)
        self.assertIn("VCL_DLLPUBLIC void DrawFoldedButton(vcl::RenderContext& rDev", header)

    def test_series_order(self):
        with open(os.path.join(os.path.dirname(__file__), "..", "..", "patches", "libreoffice", "series"),
                  encoding="utf-8") as handle:
            series = [line.strip() for line in handle if line.strip() and not line.startswith("#")]
        self.assertLess(series.index("hst-ribbon-large-menu-labels.patch"), series.index(PATCH))
        self.assertLess(series.index("hst-ribbon-adaptive-grid.patch"), series.index(PATCH))


if __name__ == "__main__":
    unittest.main()
