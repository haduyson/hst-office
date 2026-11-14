# SPDX-License-Identifier: AGPL-3.0-only
"""Open a contextual ribbon tab of an HST Office window on Windows without real input (check-windows-style-galleries.py).

LibreOffice gives no UI Automation tree there and posted keytips type into the document, so the tab is found on the
window's own pixels (PrintWindow, which works in a disconnected session): a contextual tab label is the only tab text
drawn in the accent blue, right of "Tệp tin". A left click is then posted to that window only (WM_LBUTTONDOWN/UP at
client coordinates), after the guard confirmed the window is this office's.
"""
import ctypes
from ctypes import wintypes
import struct

import windows_gui_guard as guard
from windows_gui_win32 import client_origin, window_rect

user32, gdi32 = ctypes.windll.user32, ctypes.windll.gdi32
user32.PostMessageW.argtypes = (wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM)
user32.PrintWindow.argtypes = (wintypes.HWND, ctypes.c_void_p, wintypes.UINT)
user32.GetDC.restype = ctypes.c_void_p
for _f in (gdi32.CreateCompatibleDC, gdi32.CreateCompatibleBitmap, gdi32.SelectObject):
    _f.restype = ctypes.c_void_p
gdi32.CreateCompatibleDC.argtypes = (ctypes.c_void_p,)
gdi32.CreateCompatibleBitmap.argtypes = (ctypes.c_void_p, ctypes.c_int, ctypes.c_int)
gdi32.SelectObject.argtypes = (ctypes.c_void_p, ctypes.c_void_p)
gdi32.DeleteObject.argtypes = (ctypes.c_void_p,)
gdi32.DeleteDC.argtypes = (ctypes.c_void_p,)
gdi32.GetDIBits.argtypes = (ctypes.c_void_p, ctypes.c_void_p, wintypes.UINT, wintypes.UINT, ctypes.c_void_p, ctypes.c_void_p, wintypes.UINT)
user32.ReleaseDC.argtypes = (wintypes.HWND, ctypes.c_void_p)
WM_MOUSEMOVE, WM_LBUTTONDOWN, WM_LBUTTONUP, MK_LBUTTON = 0x200, 0x201, 0x202, 0x1


def _pixels(hwnd):
    left, top, right, bottom = window_rect(hwnd)
    width, height = right - left, bottom - top
    screen = user32.GetDC(None)
    memory, bitmap = gdi32.CreateCompatibleDC(screen), gdi32.CreateCompatibleBitmap(screen, width, height)
    old = gdi32.SelectObject(memory, bitmap)
    try:
        user32.PrintWindow(wintypes.HWND(hwnd), memory, 2)  # PW_RENDERFULLCONTENT
        header = struct.pack("<IiiHHIIiiII", 40, width, -height, 1, 32, 0, 0, 0, 0, 0, 0)
        data = ctypes.create_string_buffer(width * height * 4)
        gdi32.GetDIBits(memory, bitmap, 0, height, data, ctypes.create_string_buffer(header, 44), 0)
        return width, height, data.raw
    finally:
        gdi32.SelectObject(memory, old)
        gdi32.DeleteObject(bitmap)
        gdi32.DeleteDC(memory)
        user32.ReleaseDC(None, screen)


def contextual_tab_point(hwnd, band=(40, 70), skip_left=290):
    """Window-relative centre of the accent-blue tab label in the tab row, or None."""
    width, _height, data = _pixels(hwnd)
    xs, ys = [], []
    for y in range(*band):
        row = data[y * width * 4:(y + 1) * width * 4]
        for x in range(skip_left, width * 2 // 3):
            b, g, r = row[x * 4], row[x * 4 + 1], row[x * 4 + 2]
            if b > 150 and r < 90 and b - r > 90 and g < 170:  # blue text, not the white or grey of other tabs
                xs.append(x)
                ys.append(y)
    if len(xs) < 20:
        return None
    # label clusters (words inside a label are a few pixels apart); the current tab is blue too, but contextual
    # tabs come last: take the last label, or the first of a last pair (Table Design, Table Layout)
    xs_sorted = sorted(set(xs))
    clusters, start = [], xs_sorted[0]
    for a, b in zip(xs_sorted, xs_sorted[1:] + [10 ** 6]):
        if b - a > 12:
            clusters.append((start, a))
            start = b
    first = clusters[-1]
    if len(clusters) >= 3 and clusters[-1][0] - clusters[-2][1] < 40:
        first = clusters[-2]
    return (first[0] + first[1]) // 2, (min(ys) + max(ys)) // 2


def click_contextual_tab(hwnd, real=False):
    """Click the first contextual tab: posted to the window, or with `real` a guarded SendInput click (an interactive
    console session); False when none was found. Raises BlockedInput when the window is not ours."""
    if not guard.is_ours(hwnd):
        raise guard.BlockedInput("no click posted: %#x is not an HST Office window" % (hwnd or 0))
    point = contextual_tab_point(hwnd)
    if point is None:
        return False
    left, top, _right, _bottom = window_rect(hwnd)
    if real:
        import windows_gui_input as wgi
        wgi.activate(hwnd)
        wgi.click(left + point[0], top + point[1])
        return (left + point[0], top + point[1])
    cx, cy = client_origin(hwnd)
    x, y = point[0] + left - cx, point[1] + top - cy
    lparam = (y << 16) | (x & 0xFFFF)
    user32.PostMessageW(wintypes.HWND(hwnd), WM_MOUSEMOVE, 0, lparam)
    user32.PostMessageW(wintypes.HWND(hwnd), WM_LBUTTONDOWN, MK_LBUTTON, lparam)
    user32.PostMessageW(wintypes.HWND(hwnd), WM_LBUTTONUP, 0, lparam)
    return (x, y)
