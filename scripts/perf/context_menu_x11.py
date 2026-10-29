# SPDX-License-Identifier: AGPL-3.0-only
"""Minimal Xlib/XTest driver (ctypes) for timing popup-window appearance on X11.

Detection = a new, viewable top-level window (child of root) that was not viewable in
the snapshot taken just before the click. Works with and without a window manager
(menus are override-redirect or transient top-levels, both root children).
"""
from __future__ import annotations

import ctypes
import ctypes.util
import time


class XWinAttr(ctypes.Structure):
    _fields_ = [("x", ctypes.c_int), ("y", ctypes.c_int), ("width", ctypes.c_int),
                ("height", ctypes.c_int), ("border_width", ctypes.c_int), ("depth", ctypes.c_int),
                ("visual", ctypes.c_void_p), ("root", ctypes.c_ulong), ("klass", ctypes.c_int),
                ("bit_gravity", ctypes.c_int), ("win_gravity", ctypes.c_int),
                ("backing_store", ctypes.c_int), ("backing_planes", ctypes.c_ulong),
                ("backing_pixel", ctypes.c_ulong), ("save_under", ctypes.c_int),
                ("colormap", ctypes.c_ulong), ("map_installed", ctypes.c_int),
                ("map_state", ctypes.c_int), ("all_event_masks", ctypes.c_long),
                ("your_event_mask", ctypes.c_long), ("do_not_propagate_mask", ctypes.c_long),
                ("override_redirect", ctypes.c_int), ("screen", ctypes.c_void_p)]


IS_VIEWABLE = 2
XK_ESCAPE = 0xFF1B
VP = ctypes.c_void_p


class X11Driver:
    def __init__(self, display: str):
        x11, xtst = ctypes.util.find_library("X11"), ctypes.util.find_library("Xtst")
        if not x11 or not xtst:
            raise RuntimeError("libX11/libXtst not found (install libx11-6 libxtst6)")
        self.x, self.t = ctypes.CDLL(x11), ctypes.CDLL(xtst)
        self.x.XOpenDisplay.restype = VP
        self.x.XOpenDisplay.argtypes = [ctypes.c_char_p]
        self.x.XDefaultRootWindow.restype = ctypes.c_ulong
        self.x.XDefaultRootWindow.argtypes = [VP]
        self.x.XQueryTree.argtypes = [VP, ctypes.c_ulong, VP, VP, VP, VP]
        self.x.XGetWindowAttributes.argtypes = [VP, ctypes.c_ulong, VP]
        self.x.XKeysymToKeycode.argtypes = [VP, ctypes.c_ulong]
        self.x.XFlush.argtypes = [VP]
        self.x.XCloseDisplay.argtypes = [VP]
        self.x.XFree.argtypes = [VP]
        self.t.XTestFakeMotionEvent.argtypes = [VP, ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_ulong]
        self.t.XTestFakeButtonEvent.argtypes = [VP, ctypes.c_uint, ctypes.c_int, ctypes.c_ulong]
        self.t.XTestFakeKeyEvent.argtypes = [VP, ctypes.c_uint, ctypes.c_int, ctypes.c_ulong]
        self.dpy = self.x.XOpenDisplay(display.encode())
        if not self.dpy:
            raise RuntimeError(f"cannot open X display {display}")
        self.root = self.x.XDefaultRootWindow(self.dpy)

    def close(self) -> None:
        if self.dpy:
            self.x.XCloseDisplay(self.dpy)
            self.dpy = None

    def viewable_windows(self) -> dict[int, tuple[int, int, int, int]]:
        """{window id: (x, y, w, h)} for viewable root children."""
        root_r, parent_r = ctypes.c_ulong(), ctypes.c_ulong()
        kids, n = ctypes.POINTER(ctypes.c_ulong)(), ctypes.c_uint()
        ok = self.x.XQueryTree(self.dpy, self.root, ctypes.byref(root_r), ctypes.byref(parent_r),
                               ctypes.byref(kids), ctypes.byref(n))
        out: dict[int, tuple[int, int, int, int]] = {}
        if not ok:
            return out
        for i in range(n.value):
            attr = XWinAttr()
            if self.x.XGetWindowAttributes(self.dpy, kids[i], ctypes.byref(attr)) and attr.map_state == IS_VIEWABLE:
                out[kids[i]] = (attr.x, attr.y, attr.width, attr.height)
        if kids:
            self.x.XFree(kids)
        return out

    def move(self, px: int, py: int) -> None:
        self.t.XTestFakeMotionEvent(self.dpy, -1, px, py, 0)
        self.x.XFlush(self.dpy)

    def button(self, button: int, press: bool) -> None:
        self.t.XTestFakeButtonEvent(self.dpy, button, 1 if press else 0, 0)
        self.x.XFlush(self.dpy)

    def key(self, keysym: int) -> None:
        code = self.x.XKeysymToKeycode(self.dpy, keysym)
        for press in (1, 0):
            self.t.XTestFakeKeyEvent(self.dpy, code, press, 0)
        self.x.XFlush(self.dpy)

    def right_click_and_wait(self, px: int, py: int, timeout_s: float, poll_s: float = 0.002) -> dict:
        """Press button 3 at (px,py); return {'ms','timeout','window'} for the first new popup."""
        before = set(self.viewable_windows())
        self.move(px, py)
        time.sleep(0.05)
        t0 = time.perf_counter()
        self.button(3, True)
        deadline = t0 + timeout_s
        while time.perf_counter() < deadline:
            now = self.viewable_windows()
            new = {w: g for w, g in now.items() if w not in before and g[2] >= 20 and g[3] >= 20}
            if new:
                ms = (time.perf_counter() - t0) * 1000.0
                win = max(new, key=lambda w: new[w][2] * new[w][3])
                self.button(3, False)
                return {"ms": round(ms, 2), "timeout": False, "window": [win, *new[win]]}
            time.sleep(poll_s)
        self.button(3, False)
        return {"ms": None, "timeout": True, "window": None}

    def dismiss_popup(self, before: set[int], settle_s: float = 0.5) -> None:
        """Escape until no new viewable windows remain, then let the app settle."""
        for _ in range(4):
            self.key(XK_ESCAPE)
            time.sleep(0.15)
            if not (set(self.viewable_windows()) - before):
                break
        time.sleep(settle_s)
