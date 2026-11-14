# SPDX-License-Identifier: AGPL-3.0-only
"""High-rate screen sampling for the Linux tab switch flash check (X11, pure ctypes, no compositor needed).

A grab reads a grid of small patches of one rectangle of the root window with XGetImage (each a few hundred
microseconds on a local X server), so a window that is mapped before it is painted, or a gap between unmapping the
old tab and mapping the new one, is seen. The layout of a grab is that of screen_patches_win.Patches (patches side by
side, BGRA), so screen_patch_compare classifies both.
"""
import ctypes
import ctypes.util
import threading
import time

xlib = ctypes.cdll.LoadLibrary(ctypes.util.find_library("X11"))
xlib.XOpenDisplay.restype = ctypes.c_void_p
xlib.XOpenDisplay.argtypes = [ctypes.c_char_p]
xlib.XDefaultRootWindow.restype = ctypes.c_ulong
xlib.XDefaultRootWindow.argtypes = [ctypes.c_void_p]
xlib.XGetImage.restype = ctypes.c_void_p
xlib.XGetImage.argtypes = [ctypes.c_void_p, ctypes.c_ulong, ctypes.c_int, ctypes.c_int, ctypes.c_uint, ctypes.c_uint,
                           ctypes.c_ulong, ctypes.c_int]
xlib.XFree.argtypes = [ctypes.c_void_p]
xlib.XCloseDisplay.argtypes = [ctypes.c_void_p]
ZPIXMAP = 2


class _XImage(ctypes.Structure):
    _fields_ = [("width", ctypes.c_int), ("height", ctypes.c_int), ("xoffset", ctypes.c_int), ("format", ctypes.c_int),
                ("data", ctypes.c_void_p), ("byte_order", ctypes.c_int), ("bitmap_unit", ctypes.c_int),
                ("bitmap_bit_order", ctypes.c_int), ("bitmap_pad", ctypes.c_int), ("depth", ctypes.c_int),
                ("bytes_per_line", ctypes.c_int), ("bits_per_pixel", ctypes.c_int)]


class Patches:
    """cols x rows patches of size x size pixels spread over (left, top, right, bottom) of `display`'s root window."""

    def __init__(self, display, rect, cols=5, rows=4, size=16):
        left, top, right, bottom = rect
        self.size, self.count = size, cols * rows
        self.points = [(left + (right - left) * (2 * c + 1) // (2 * cols) - size // 2,
                        top + (bottom - top) * (2 * r + 1) // (2 * rows) - size // 2)
                       for r in range(rows) for c in range(cols)]
        self.dpy = xlib.XOpenDisplay(display.encode())
        if not self.dpy:
            raise OSError("cannot open display %s" % display)
        self.root = xlib.XDefaultRootWindow(self.dpy)

    def _patch_rows(self, x, y):
        image = xlib.XGetImage(self.dpy, self.root, x, y, self.size, self.size, 0xFFFFFFFF, ZPIXMAP)
        if not image:
            return [b"\0" * (self.size * 4)] * self.size
        info = _XImage.from_address(image)
        rows = [ctypes.string_at(info.data + y * info.bytes_per_line, self.size * 4) for y in range(self.size)]
        xlib.XFree(info.data)
        xlib.XFree(image)
        return rows

    def grab(self):
        patches = [self._patch_rows(x, y) for x, y in self.points]
        return b"".join(b"".join(p[y] for p in patches) for y in range(self.size))

    def patch(self, data, n):
        row, width = self.size * self.count * 4, self.size * 4
        return b"".join(data[y * row + n * width:y * row + (n + 1) * width] for y in range(self.size))

    def close(self):
        xlib.XCloseDisplay(self.dpy)


class Recorder(threading.Thread):
    def __init__(self, patches):
        super().__init__(daemon=True)
        self.patches, self.frames, self.errors, self.stop = patches, [], [], threading.Event()

    def run(self):
        while not self.stop.is_set():
            try:
                self.frames.append((time.perf_counter(), self.patches.grab()))
            except Exception as error:  # noqa: BLE001 - reported by the caller
                self.errors.append(repr(error))
                time.sleep(0.05)
