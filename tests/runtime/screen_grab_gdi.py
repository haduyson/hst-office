# SPDX-License-Identifier: AGPL-3.0-only
"""Fast downscaled grabs of the whole Windows screen (GDI StretchBlt) and the "desktop shows through" measure of
check-windows-tab-switch-flash.py. Pure ctypes, no third-party module (runs in the office's own python.exe)."""
import ctypes
import struct
import threading
import time
from ctypes import wintypes

user32 = ctypes.WinDLL("user32", use_last_error=True)
gdi32 = ctypes.WinDLL("gdi32", use_last_error=True)
user32.GetDC.restype, user32.GetDC.argtypes = wintypes.HDC, [wintypes.HWND]
user32.ReleaseDC.argtypes = [wintypes.HWND, wintypes.HDC]
gdi32.CreateCompatibleDC.restype, gdi32.CreateCompatibleDC.argtypes = wintypes.HDC, [wintypes.HDC]
gdi32.SelectObject.restype, gdi32.SelectObject.argtypes = wintypes.HGDIOBJ, [wintypes.HDC, wintypes.HGDIOBJ]
gdi32.DeleteObject.argtypes = [wintypes.HGDIOBJ]
gdi32.DeleteDC.argtypes = [wintypes.HDC]
gdi32.SetStretchBltMode.argtypes = [wintypes.HDC, ctypes.c_int]
gdi32.StretchBlt.argtypes = [wintypes.HDC] + [ctypes.c_int] * 4 + [wintypes.HDC] + [ctypes.c_int] * 4 + [wintypes.DWORD]
gdi32.CreateDIBSection.restype = wintypes.HBITMAP
gdi32.CreateDIBSection.argtypes = [wintypes.HDC, ctypes.c_void_p, wintypes.UINT, ctypes.POINTER(ctypes.c_void_p),
                                   wintypes.HANDLE, wintypes.DWORD]

SCALE = 8  # 1920x1080 -> 240x135: fast enough for ~30 grabs per second, a whole-window flash is still obvious
DESKTOP_SHARE = 0.25
NEAR = 10  # per channel: the same picture (GDI downscaling is deterministic)


class _Header(ctypes.Structure):
    _fields_ = [("biSize", wintypes.DWORD), ("biWidth", wintypes.LONG), ("biHeight", wintypes.LONG),
                ("biPlanes", wintypes.WORD), ("biBitCount", wintypes.WORD), ("biCompression", wintypes.DWORD),
                ("biSizeImage", wintypes.DWORD), ("biXPelsPerMeter", wintypes.LONG),
                ("biYPelsPerMeter", wintypes.LONG), ("biClrUsed", wintypes.DWORD), ("biClrImportant", wintypes.DWORD)]


class Screen:
    """Downscaled BGRA grabs of the whole primary screen."""

    def __init__(self):
        self.full = user32.GetSystemMetrics(0), user32.GetSystemMetrics(1)
        self.w, self.h = self.full[0] // SCALE, self.full[1] // SCALE
        self.screen = user32.GetDC(0)
        self.mem = gdi32.CreateCompatibleDC(self.screen)
        header = _Header(ctypes.sizeof(_Header), self.w, -self.h, 1, 32, 0, 0, 0, 0, 0, 0)
        self.bits = ctypes.c_void_p()
        self.dib = gdi32.CreateDIBSection(self.mem, ctypes.byref(header), 0, ctypes.byref(self.bits), None, 0)
        gdi32.SelectObject(self.mem, self.dib)
        gdi32.SetStretchBltMode(self.mem, 3)  # COLORONCOLOR

    def grab(self):
        gdi32.StretchBlt(self.mem, 0, 0, self.w, self.h, self.screen, 0, 0, self.full[0], self.full[1], 0x00CC0020)
        return ctypes.string_at(self.bits, self.w * self.h * 4)

    def close(self):
        gdi32.DeleteObject(self.dib)
        gdi32.DeleteDC(self.mem)
        user32.ReleaseDC(0, self.screen)

    def save_bmp(self, path, data):
        row = self.w * 4
        rows = b"".join(data[y * row:(y + 1) * row] for y in range(self.h - 1, -1, -1))
        with open(path, "wb") as handle:
            handle.write(b"BM" + struct.pack("<IHHI", 54 + len(rows), 0, 0, 54))
            handle.write(struct.pack("<IiiHHIIiiII", 40, self.w, self.h, 1, 32, 0, len(rows), 0, 0, 0, 0))
            handle.write(rows)


class Recorder(threading.Thread):
    def __init__(self, screen):
        super().__init__(daemon=True)
        self.screen, self.frames, self.stop = screen, [], threading.Event()

    def run(self):
        while not self.stop.is_set():
            self.frames.append((time.perf_counter(), self.screen.grab()))


def same(a, b, i):
    return abs(a[i] - b[i]) < NEAR and abs(a[i + 1] - b[i + 1]) < NEAR and abs(a[i + 2] - b[i + 2]) < NEAR


def desktop_share(frame, before, after, desktop):
    """Share of the pixels that show the desktop although neither the screen before nor after the switch does."""
    total = hits = 0
    for i in range(0, len(frame), 4 * 3):  # every third pixel is plenty for a whole-window flash
        if same(frame, before, i) or same(frame, after, i):
            total += 1
            continue
        total += 1
        hits += same(frame, desktop, i)
    return hits / max(total, 1)
