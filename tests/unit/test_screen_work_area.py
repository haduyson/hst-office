# SPDX-License-Identifier: AGPL-3.0-only
"""The work area a dialog may use: Toolkit.getWorkArea() is the whole display, taskbar included, so Windows reads
SPI_GETWORKAREA and other systems keep a panel margin; the window frame and title bar need room too."""
import types
import unittest
from unittest import mock

import _paths  # noqa: F401
from hst_office import screen_work_area as area


class Toolkit:
    def getWorkArea(self):
        return types.SimpleNamespace(X=0, Y=0, Width=1366, Height=768)


def size(width, height):
    return types.SimpleNamespace(Width=width, Height=height)


class WorkArea(unittest.TestCase):
    def test_windows_uses_the_taskbar_free_area(self):
        with mock.patch.object(area, "_windows_work_area", return_value=(1366, 708)):
            self.assertEqual(area.work_area(Toolkit(), "win32"), (1366, 708))
            self.assertFalse(area.exceeds(Toolkit(), size(775, 658), "win32"))
            self.assertTrue(area.exceeds(Toolkit(), size(775, 720), "win32"))  # 720 + title bar under the taskbar

    def test_windows_falls_back_to_the_display_less_a_margin(self):
        with mock.patch.object(area, "_windows_work_area", side_effect=OSError("no user32")):
            self.assertEqual(area.work_area(Toolkit(), "win32"), (1366, 768 - area.PANEL_MARGIN_PX))

    def test_other_systems_keep_a_panel_margin(self):
        self.assertEqual(area.work_area(Toolkit(), "linux"), (1366, 768 - area.PANEL_MARGIN_PX))
        self.assertTrue(area.exceeds(Toolkit(), size(1400, 300), "linux"))  # too wide
        self.assertFalse(area.exceeds(Toolkit(), size(1283, 768 - area.PANEL_MARGIN_PX - area.DECORATION_PX), "linux"))


if __name__ == "__main__":
    unittest.main()
