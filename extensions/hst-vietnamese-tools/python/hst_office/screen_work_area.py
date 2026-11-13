# SPDX-License-Identifier: AGPL-3.0-only
"""The part of the screen a dialog may use, in device pixels like a peer's getPosSize().

com.sun.star.awt.Toolkit.getWorkArea() returns the whole display (VCLXToolkit::getWorkArea is
Application::GetScreenPosSizePixel), taskbar included: a dialog sized to it ends under the Windows taskbar. On Windows
the real work area comes from SystemParametersInfo(SPI_GETWORKAREA) (the office process is DPI aware, so both are
device pixels); elsewhere a margin is kept for panels and docks. A dialog also needs room for its window frame and
title bar (DECORATION_PX), which getPosSize() does not count.
"""
import sys

DECORATION_PX = 48
PANEL_MARGIN_PX = 64  # Linux panels / the macOS menu bar and Dock, when the real work area is not known


def _windows_work_area():
    import ctypes
    rect = (ctypes.c_long * 4)()
    if ctypes.windll.user32.SystemParametersInfoW(0x0030, 0, rect, 0):  # SPI_GETWORKAREA
        return rect[2] - rect[0], rect[3] - rect[1]
    return None


def work_area(toolkit, platform=None):
    """(width, height) in pixels a dialog window may cover."""
    screen = toolkit.getWorkArea()
    if (platform or sys.platform) == "win32":
        try:
            area = _windows_work_area()
            if area:
                return area
        except Exception:  # noqa: BLE001 - no user32: fall back to the display less a margin
            pass
    return screen.Width, screen.Height - PANEL_MARGIN_PX


def exceeds(toolkit, size, platform=None):
    """Whether a dialog whose peer is `size` (getPosSize) does not fit, frame and title bar included."""
    width, height = work_area(toolkit, platform)
    return size.Width > width or size.Height + DECORATION_PX > height
