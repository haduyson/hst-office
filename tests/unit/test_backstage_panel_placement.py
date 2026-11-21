# SPDX-License-Identifier: AGPL-3.0-only
"""hst-backstage-panel-beside-banner.patch: the File panel takes the window's width below the document tab strip.

sfx2/source/backstage/hstbackstageplacement.hxx is compiled with a small driver. The case that cut the Print page:
a 1042 px window at 125 % on Windows, the banner (x 562, above the document tab strip) ending above the panel's
top. The panel must reach the window's right edge there, and stop left of the banner only where the banner is
beside it (no document tab strip: the panel starts at the tab row, over the ribbon's body)."""
import os
import shutil
import subprocess
import tempfile
import unittest

from patch_sections import added

PATCH = "hst-backstage-panel-beside-banner.patch"
HEADER = "sfx2/source/backstage/hstbackstageplacement.hxx"

DRIVER = r"""
#include "hstbackstageplacement.hxx"
#include <iostream>
int main()
{
    long frame, inset, top, left, bottom;
    int banner;
    while (std::cin >> frame >> inset >> top >> banner >> left >> bottom)
        std::cout << sfx2::backstage::panelRight(frame, inset, top, banner != 0, left, bottom) << '\n';
}
"""


def rights(cases):
    with tempfile.TemporaryDirectory() as tmp:
        with open(os.path.join(tmp, "hstbackstageplacement.hxx"), "w", encoding="utf-8") as handle:
            handle.write(added(PATCH, HEADER) + "\n")
        with open(os.path.join(tmp, "drv.cxx"), "w", encoding="utf-8") as handle:
            handle.write(DRIVER)
        subprocess.run(["g++", "-std=c++20", "-Wall", "-Wextra", "-Werror", "-o", os.path.join(tmp, "drv"),
                        os.path.join(tmp, "drv.cxx")], check=True)
        run = subprocess.run([os.path.join(tmp, "drv")], text=True, capture_output=True, check=True,
                             input="".join(" ".join(map(str, c)) + "\n" for c in cases))
    return [int(v) for v in run.stdout.split()]


INSET = 10  # 8 px at 125 %


@unittest.skipUnless(shutil.which("g++"), "needs g++")
class PanelPlacementTest(unittest.TestCase):
    def test_below_the_tab_strip_the_panel_takes_the_window_width(self):
        # 1024 and 1042 px windows at 125 %: the banner ends at y 150, the panel starts at y 190
        for frame in (1024, 1042, 1366):
            with self.subTest(frame=frame):
                self.assertEqual(rights([(frame, INSET, 190, 1, 562, 150)]), [frame - INSET])

    def test_beside_the_banner_the_panel_stops_left_of_it(self):
        # no document tab strip: the panel starts at the tab row (y 60), the banner spans y 60-150 of the ribbon
        self.assertEqual(rights([(1042, INSET, 60, 1, 562, 150)]), [562 - INSET])

    def test_a_banner_ending_at_the_panel_top_is_not_beside_it(self):
        self.assertEqual(rights([(1042, INSET, 150, 1, 562, 150)]), [1042 - INSET])

    def test_without_a_banner_the_panel_takes_the_window_width(self):
        self.assertEqual(rights([(1042, INSET, 60, 0, 0, 0)]), [1042 - INSET])

    def test_the_panel_placement_uses_it(self):
        code = added(PATCH, "sfx2/source/backstage/hstbackstagewindow.cxx")
        self.assertIn('#include "hstbackstageplacement.hxx"', code)
        self.assertIn("const tools::Long nRight = sfx2::backstage::panelRight(", code)
        self.assertIn("bBanner ? aBanner.Y() + pBanner->GetOutputSizePixel().Height() : tools::Long(0));", code)


if __name__ == "__main__":
    unittest.main()
