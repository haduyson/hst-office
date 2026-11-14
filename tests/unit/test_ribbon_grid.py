# SPDX-License-Identifier: AGPL-3.0-only
"""Even 3-row grid of ribbon groups at their medium/small size (vcl/inc/HstRibbonGrid.hxx from
hst-ribbon-adaptive-grid.patch, compiled with a small driver) and the patch's wiring into ToolBox."""
import os
import shutil
import subprocess
import tempfile
import unittest

from patch_sections import added, sections

PATCH = "hst-ribbon-adaptive-grid.patch"
HEADER = "vcl/inc/HstRibbonGrid.hxx"

DRIVER = r"""
#include "HstRibbonGrid.hxx"
#include <cstdio>
using namespace hst::ribbon;
static int failures = 0;
#define CHECK(x) do { if (!(x)) { std::printf("FAIL %d %s\n", __LINE__, #x); ++failures; } } while (0)
int main()
{
    // five labelled buttons: columns of three, filled top to bottom, every item at its column's left edge
    std::vector<GridItem> items{ { 40, 22 }, { 60, 22 }, { 50, 22 }, { 30, 22 }, { 70, 22 } };
    GridLayout g = gridLayout(items, 3, 24, 2, 6, 1);
    CHECK(g.height == 3 * 24 + 2 * 2);
    CHECK(g.cells[0].x == 0 && g.cells[1].x == 0 && g.cells[2].x == 0);
    CHECK(g.cells[0].y == 0 && g.cells[1].y == 26 && g.cells[2].y == 52);
    CHECK(g.cells[3].x == 60 + 6 && g.cells[4].x == 66 && g.cells[4].y == 26);
    CHECK(g.width == 66 + 70);
    // a separator closes the column and stands across the whole grid
    items = { { 40, 22 }, { 30, 22 }, { 0, 0, true }, { 50, 22 } };
    g = gridLayout(items, 3, 24, 2, 6, 1);
    CHECK(g.cells[2].x == 46 && g.cells[2].h == g.height && g.cells[3].x == 53 && g.cells[3].y == 0);
    // hidden items take no cell; a leading or trailing separator does not stand alone
    items = { { 0, 0, true }, { 40, 22, false, false }, { 30, 22 }, { 0, 0, true } };
    g = gridLayout(items, 3, 24, 2, 6, 1);
    CHECK(g.cells[0].w == 0 && g.cells[1].w == 0 && g.cells[2].x == 0 && g.cells[3].w == 0 && g.width == 30);
    // rows grow to the tallest item; nothing makes the grid lower than three rows
    items = { { 40, 30 } };
    g = gridLayout(items, 3, 24, 2, 6, 1);
    CHECK(g.height == 3 * 30 + 4 && g.width == 40);
    CHECK(LABEL_WRAP == 62);
    // a group's large buttons, one toolbox each: three of them make one column of three; the separator after
    // them moves left and spans the extra row and the caption; the caption keeps its columns, below row 3
    std::vector<GroupCell> links{ { 0, 2, 3, 1, false, true }, { 0, 0, 1, 2, true }, { 1, 0, 1, 2, true },
                                  { 2, 0, 1, 2, true }, { 3, 0, 1, 3 } };
    CHECK(stackGroup(links));
    CHECK(links[1].left == 0 && links[1].top == 0 && links[2].top == 1 && links[3].top == 2 && links[3].left == 0);
    CHECK(links[4].left == 1 && links[4].height == 4);
    CHECK(links[0].top == 3 && links[0].left == 0 && links[0].width == 1);
    // four buttons: a column of three and one more; a 2-row small column after them keeps its rows
    std::vector<GroupCell> four{ { 0, 2, 6, 1, false, true }, { 0, 0, 1, 2, true }, { 1, 0, 1, 2, true },
                                 { 2, 0, 1, 2, true }, { 3, 0, 1, 2, true }, { 4, 0, 1, 1 }, { 4, 1, 1, 1 },
                                 { 5, 0, 1, 2, false } };
    CHECK(stackGroup(four));
    CHECK(four[4].left == 1 && four[4].top == 0 && four[5].left == 2 && four[6].left == 2 && four[6].top == 1);
    CHECK(four[7].left == 3 && four[7].height == 3 && four[0].width == 4);
    // a single large button (or Paste beside small rows) is left as authored
    std::vector<GroupCell> paste{ { 0, 2, 2, 1, false, true }, { 0, 0, 1, 2, false }, { 1, 0, 1, 1 }, { 1, 1, 1, 1 } };
    const std::vector<GroupCell> before = paste;
    CHECK(!stackGroup(paste) && paste[1].left == before[1].left && paste[0].width == 2);
    std::printf("checks done, %d failure(s)\n", failures);
    return failures ? 1 : 0;
}
"""


def new_file(path):
    return "\n".join(line[1:] for line in sections(PATCH)[path] if line.startswith("+")) + "\n"


class RibbonGrid(unittest.TestCase):
    @unittest.skipUnless(shutil.which("g++"), "no C++ compiler")
    def test_grid_geometry(self):
        with tempfile.TemporaryDirectory() as tmp:
            with open(os.path.join(tmp, "HstRibbonGrid.hxx"), "w", encoding="utf-8") as handle:
                handle.write(new_file(HEADER))
            with open(os.path.join(tmp, "driver.cxx"), "w", encoding="utf-8") as handle:
                handle.write(DRIVER)
            exe = os.path.join(tmp, "driver")
            subprocess.run(["g++", "-std=c++17", "-o", exe, os.path.join(tmp, "driver.cxx")], check=True)
            run = subprocess.run([exe], capture_output=True, text=True)
            self.assertEqual(run.returncode, 0, run.stdout)

    def test_grid_is_opt_in_for_ribbon_toolboxes(self):
        toolbox = added(PATCH, "vcl/source/window/toolbox.cxx")
        self.assertIn("if (mpData->mnHstGridRows > 0 && mbHorz && !ImplIsFloatingMode())", toolbox)
        self.assertIn("void ToolBox::HstSetGridRows( int nRows )", toolbox)
        ladder = added(PATCH, "vcl/source/control/HstRibbonLadder.cxx")
        self.assertIn("rData.meHstAuthoredSize == ToolBoxButtonSize::Large && commandCount(rToolBox) >= 2 ? 3 : 0", ladder)
        self.assertIn("stackLargeButtons(rGroup, nState, bFewCommands);", ladder)

    def test_labels_wrap_and_menu_buttons_split(self):
        toolbox = added(PATCH, "vcl/source/window/toolbox.cxx")
        self.assertIn("if (!rData.mbHstOwnerDraw || ePosition != ToolBoxTextPosition::Bottom", toolbox)
        self.assertIn("item.mbHstSplitBelow = true;", toolbox)
        self.assertIn("aRect.SetTop(maRect.Top() + mnHstSplitTop);", added(PATCH, "vcl/source/window/toolbox2.cxx"))


if __name__ == "__main__":
    unittest.main()
