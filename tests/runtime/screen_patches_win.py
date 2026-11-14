# SPDX-License-Identifier: AGPL-3.0-only
"""High-rate screen sampling for the tab switch flash checks (Windows, pure ctypes).

Instead of downscaling the whole screen (about 30 grabs/s), a grab copies a grid of small patches of one screen
rectangle (the office window) with BitBlt from the screen DC: several hundred grabs per second, more than the 60 frames
per second the compositor shows, so every composed frame is seen. A grab is classified per patch against three
references: the screen before the switch, the screen after it and the desktop grabbed before the office started.
"""
from screen_patch_compare import classify, describe, near  # noqa: F401 (the checks use them from here)
import ctypes
import threading
import time
from ctypes import wintypes

user32 = ctypes.WinDLL("user32", use_last_error=True)
gdi32 = ctypes.WinDLL("gdi32", use_last_error=True)
user32.GetDC.restype, user32.GetDC.argtypes = wintypes.HDC, [wintypes.HWND]
user32.ReleaseDC.argtypes = [wintypes.HWND, wintypes.HDC]
user32.GetForegroundWindow.restype = wintypes.HWND
user32.SetForegroundWindow.argtypes = user32.BringWindowToTop.argtypes = [wintypes.HWND]
user32.ShowWindow.argtypes = [wintypes.HWND, ctypes.c_int]
user32.GetWindowThreadProcessId.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.DWORD)]
user32.GetClassNameW.argtypes = [wintypes.HWND, wintypes.LPWSTR, ctypes.c_int]
gdi32.CreateCompatibleDC.restype, gdi32.CreateCompatibleDC.argtypes = wintypes.HDC, [wintypes.HDC]
gdi32.SelectObject.restype, gdi32.SelectObject.argtypes = wintypes.HGDIOBJ, [wintypes.HDC, wintypes.HGDIOBJ]
gdi32.DeleteObject.argtypes = [wintypes.HGDIOBJ]
gdi32.DeleteDC.argtypes = [wintypes.HDC]
gdi32.BitBlt.argtypes = [wintypes.HDC] + [ctypes.c_int] * 4 + [wintypes.HDC] + [ctypes.c_int] * 2 + [wintypes.DWORD]
gdi32.CreateDIBSection.restype = wintypes.HBITMAP
gdi32.CreateDIBSection.argtypes = [wintypes.HDC, ctypes.c_void_p, wintypes.UINT, ctypes.POINTER(ctypes.c_void_p),
                                   wintypes.HANDLE, wintypes.DWORD]


class _Header(ctypes.Structure):
    _fields_ = [("biSize", wintypes.DWORD), ("biWidth", wintypes.LONG), ("biHeight", wintypes.LONG),
                ("biPlanes", wintypes.WORD), ("biBitCount", wintypes.WORD), ("biCompression", wintypes.DWORD),
                ("biSizeImage", wintypes.DWORD), ("biXPelsPerMeter", wintypes.LONG),
                ("biYPelsPerMeter", wintypes.LONG), ("biClrUsed", wintypes.DWORD), ("biClrImportant", wintypes.DWORD)]


class Patches:
    """cols x rows patches of size x size pixels spread over the screen rectangle (left, top, right, bottom)."""

    def __init__(self, rect, cols=5, rows=4, size=16):
        left, top, right, bottom = rect
        self.size, self.count = size, cols * rows
        self.points = [(left + (right - left) * (2 * c + 1) // (2 * cols) - size // 2,
                        top + (bottom - top) * (2 * r + 1) // (2 * rows) - size // 2)
                       for r in range(rows) for c in range(cols)]
        self.screen = user32.GetDC(0)
        self.mem = gdi32.CreateCompatibleDC(self.screen)
        header = _Header(ctypes.sizeof(_Header), size * self.count, -size, 1, 32, 0, 0, 0, 0, 0, 0)
        self.bits = ctypes.c_void_p()
        self.dib = gdi32.CreateDIBSection(self.mem, ctypes.byref(header), 0, ctypes.byref(self.bits), None, 0)
        gdi32.SelectObject(self.mem, self.dib)

    def grab(self):
        for n, (x, y) in enumerate(self.points):
            gdi32.BitBlt(self.mem, n * self.size, 0, self.size, self.size, self.screen, x, y, 0x00CC0020)
        return ctypes.string_at(self.bits, self.size * self.count * self.size * 4)

    def patch(self, data, n):
        """Bytes of patch n (rows of the DIB are size*count pixels wide)."""
        row, width = self.size * self.count * 4, self.size * 4
        return b"".join(data[y * row + n * width:y * row + (n + 1) * width] for y in range(self.size))

    def close(self):
        gdi32.DeleteObject(self.dib)
        gdi32.DeleteDC(self.mem)
        user32.ReleaseDC(0, self.screen)


class Recorder(threading.Thread):
    def __init__(self, patches):
        super().__init__(daemon=True)
        self.patches, self.frames, self.errors, self.stop = patches, [], [], threading.Event()

    def run(self):
        while not self.stop.is_set():
            try:
                self.frames.append((time.perf_counter(), self.patches.grab()))
            except Exception as error:  # noqa: BLE001 - reported by the caller; a check must not hang on it
                self.errors.append(repr(error))
                time.sleep(0.05)


def window_process(hwnd):
    pid = wintypes.DWORD()
    user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
    return pid.value


def window_class(hwnd):
    name = ctypes.create_unicode_buffer(128)
    user32.GetClassNameW(hwnd, name, 128)
    return name.value


def bring_to_front(hwnd):
    """Make `hwnd` the foreground window without any key press: attach to the input of the thread that owns the
    current foreground window (the documented way round the foreground lock), raise, detach."""
    kernel32 = ctypes.WinDLL("kernel32")
    front = user32.GetForegroundWindow()
    mine, theirs = kernel32.GetCurrentThreadId(), user32.GetWindowThreadProcessId(front, None) if front else 0
    attached = bool(theirs) and theirs != mine and user32.AttachThreadInput(mine, theirs, True)
    try:
        user32.ShowWindow(hwnd, 5)  # SW_SHOW
        user32.BringWindowToTop(hwnd)
        user32.SetForegroundWindow(hwnd)
    finally:
        if attached:
            user32.AttachThreadInput(mine, theirs, False)
    time.sleep(0.4)
    return user32.GetForegroundWindow() == hwnd


def office_in_front(pids):
    """The foreground window is an HST Office frame of one of `pids` (vcl frames: class SAL*FRAME*); keys are sent
    only then, never blindly to whatever is in front."""
    hwnd = user32.GetForegroundWindow()
    return bool(hwnd) and window_process(hwnd) in pids and "FRAME" in window_class(hwnd).upper()
