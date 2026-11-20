# SPDX-License-Identifier: AGPL-3.0-only
"""hst-ribbon-item-window-fits-toolbox.patch: a ribbon toolbox shows all of an item window.

vcl/inc/HstRibbonItemFit.hxx is compiled with a small driver and fed the places the Windows 125 % dumps measured:
a fill style box 24 px high set 1-3 px below the 24 px toolbox's top, colour boxes of 26-27 px and font boxes of
28 px in it. Each must end up wholly inside the toolbox (shown height = window height); boxes that fit (100 %)
stay where the toolbox put them."""
import os
import shutil
import subprocess
import tempfile
import unittest

from patch_sections import added

PATCH = "hst-ribbon-item-window-fits-toolbox.patch"
HEADER = "vcl/inc/HstRibbonItemFit.hxx"

DRIVER = r"""
#include "HstRibbonItemFit.hxx"
#include <iostream>
int main()
{
    long top, height, innerTop, inner;
    while (std::cin >> top >> height >> innerTop >> inner)
    {
        const hst::ribbon::ItemSpan s = hst::ribbon::fitItemWindow(top, height, innerTop, inner);
        std::cout << s.top << ' ' << s.height << '\n';
    }
}
"""


def shown(top, height, inner_top, inner):
    """The rows of the window the toolbox's band [inner_top, inner_top + inner) shows."""
    return max(0, min(top + height, inner_top + inner) - max(top, inner_top))


def fit_all(header, cases):
    with tempfile.TemporaryDirectory() as tmp:
        with open(os.path.join(tmp, "HstRibbonItemFit.hxx"), "w", encoding="utf-8") as handle:
            handle.write(header + "\n")
        with open(os.path.join(tmp, "drv.cxx"), "w", encoding="utf-8") as handle:
            handle.write(DRIVER)
        subprocess.run(["g++", "-std=c++20", "-Wall", "-Wextra", "-Werror", "-o", os.path.join(tmp, "drv"),
                        os.path.join(tmp, "drv.cxx")], check=True)
        run = subprocess.run([os.path.join(tmp, "drv")], input="".join(f"{' '.join(map(str, c))}\n" for c in cases),
                             text=True, capture_output=True, check=True)
    return [tuple(int(v) for v in line.split()) for line in run.stdout.splitlines()]


# (top, height, inner top, inner height) as the toolbox placed the window, from the 125 % and 100 % dumps
CUT_AT_125 = [
    (1, 24, 0, 24),  # fill style (Picture, Shape): line 26, the box 1 px low
    (3, 24, 0, 24),  # fill style (Table Design): line 30, the box 3 px low
    (2, 26, 0, 24),  # brightness, contrast, transparency, gamma
    (2, 27, 0, 24),  # colour mode
    (0, 28, 0, 24),  # font name, font size
]
FITS_AT_100 = [(0, 23, 0, 24), (1, 22, 0, 24), (0, 24, 0, 24)]


@unittest.skipUnless(shutil.which("g++"), "needs g++")
class ItemWindowFitTest(unittest.TestCase):
    def test_a_box_the_toolbox_cut_at_125_is_shown_whole(self):
        for case, (top, height) in zip(CUT_AT_125, fit_all(added(PATCH, HEADER), CUT_AT_125)):
            with self.subTest(case=case):
                self.assertEqual(shown(top, height, case[2], case[3]), height)
                self.assertEqual(height, min(case[1], case[3]))  # as high as it asks, up to the toolbox

    def test_a_box_that_fits_stays_where_the_toolbox_put_it(self):
        self.assertEqual(fit_all(added(PATCH, HEADER), FITS_AT_100), [c[:2] for c in FITS_AT_100])

    def test_a_toolbox_not_laid_out_yet_moves_nothing(self):
        self.assertEqual(fit_all(added(PATCH, HEADER), [(3, 28, 0, 0)]), [(3, 28)])

    def test_the_toolbox_places_its_item_windows_with_it(self):
        code = added(PATCH, "vcl/source/window/toolbox.cxx")
        self.assertIn("#include <HstRibbonItemFit.hxx>", code)
        self.assertIn("if ( ( mpData->mbHstOwnerDraw || mpData->mbHstStretch ) && mbHorz && !ImplIsFloatingMode() )", code)
        self.assertIn("item.mpWindow->GetSizePixel().Height(), 0, mnDY );", code)  # the whole toolbox, borders too
        self.assertIn("aPos.setY( aFit.top );", code)

    def test_a_toolbox_given_a_height_that_cuts_an_item_window_formats_again(self):
        code = added(PATCH, "vcl/source/window/toolbox.cxx")
        self.assertIn("if ( ( mpData->mbHstOwnerDraw || mpData->mbHstStretch ) && nOldDY != mnDY", code)
        self.assertIn("rItem.mpWindow->GetPosPixel().Y() < 0", code)  # only a window the new height cuts
        self.assertIn("+ rItem.mpWindow->GetSizePixel().Height() > mnDY );", code)
        self.assertIn("mbFormat = true;", code)


if __name__ == "__main__":
    unittest.main()
