# SPDX-License-Identifier: AGPL-3.0-only
"""Visible office windows right now, per OS, for scripts/perf/startup-timing.py: [(pid, width, height, title, kind)],
on Windows followed by the window's left and top screen pixel.

Windows: EnumWindows over the windows of soffice.bin / soffice.exe processes; a captionless unowned popup is the
splash, an owned captioned window a dialog, an unowned captioned window a frame. Linux (X11): the mapped children of
the root window owned by oosplash or soffice.bin (_NET_WM_PID), a transient one a dialog, else the size rule. macOS: the on-screen
normal-layer windows of soffice processes (CGWindowListCopyWindowInfo through ctypes), kind left to the size rule.
Sizes are device pixels on Windows and X11 and points on macOS.
"""
import ctypes
import ctypes.util
import os
import sys

NAMES = ("soffice.bin", "soffice.exe", "soffice", "oosplash", "oosplash.exe")


def _windows():
    from ctypes import wintypes
    user32, kernel32 = ctypes.WinDLL("user32"), ctypes.WinDLL("kernel32")
    user32.GetWindow.restype = wintypes.HWND
    user32.GetWindowLongW.restype = ctypes.c_long
    try:
        user32.SetProcessDPIAware()
    except AttributeError:
        pass
    names = {}

    def image(pid):
        if pid not in names:
            handle = kernel32.OpenProcess(0x1000, False, pid)  # PROCESS_QUERY_LIMITED_INFORMATION
            buffer, size = ctypes.create_unicode_buffer(1024), wintypes.DWORD(1024)
            ok = handle and kernel32.QueryFullProcessImageNameW(handle, 0, buffer, ctypes.byref(size))
            if handle:
                kernel32.CloseHandle(handle)
            names[pid] = os.path.basename(buffer.value).lower() if ok else ""
        return names[pid]

    class Rect(ctypes.Structure):
        _fields_ = [("left", ctypes.c_long), ("top", ctypes.c_long), ("right", ctypes.c_long), ("bottom", ctypes.c_long)]

    callback = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)

    def sample():
        found = []

        def visit(hwnd, _param):
            if not user32.IsWindowVisible(hwnd):
                return True
            pid = wintypes.DWORD()
            user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
            if image(pid.value) not in NAMES:
                return True
            rect = Rect()
            user32.GetWindowRect(hwnd, ctypes.byref(rect))
            width, height = rect.right - rect.left, rect.bottom - rect.top
            if width < 150 or height < 100:
                return True
            title = ctypes.create_unicode_buffer(256)
            user32.GetWindowTextW(hwnd, title, 256)
            style = user32.GetWindowLongW(hwnd, -16) & 0xFFFFFFFF  # GWL_STYLE
            captioned = style & 0x00C00000 == 0x00C00000  # WS_CAPTION
            owned = bool(user32.GetWindow(hwnd, 4))  # GW_OWNER
            kind = "dialog" if owned and captioned else "frame" if captioned else "splash" if not owned else ""
            found.append((pid.value, width, height, title.value, kind, rect.left, rect.top))
            return True
        user32.EnumWindows(callback(visit), 0)
        return found
    return sample


def _x11():
    xlib = ctypes.CDLL(ctypes.util.find_library("X11") or "libX11.so.6")
    xlib.XOpenDisplay.restype = ctypes.c_void_p
    display = xlib.XOpenDisplay(None)
    if not display:
        raise RuntimeError("no X display")
    xlib.XDefaultRootWindow.restype = ctypes.c_ulong
    xlib.XDefaultRootWindow.argtypes = [ctypes.c_void_p]
    xlib.XInternAtom.restype = ctypes.c_ulong
    xlib.XInternAtom.argtypes = [ctypes.c_void_p, ctypes.c_char_p, ctypes.c_int]
    root = xlib.XDefaultRootWindow(display)
    pid_atom = xlib.XInternAtom(display, b"_NET_WM_PID", False)

    class Attributes(ctypes.Structure):
        _fields_ = [("x", ctypes.c_int), ("y", ctypes.c_int), ("width", ctypes.c_int), ("height", ctypes.c_int),
                    ("border_width", ctypes.c_int), ("depth", ctypes.c_int), ("visual", ctypes.c_void_p),
                    ("root", ctypes.c_ulong), ("class", ctypes.c_int), ("bit_gravity", ctypes.c_int),
                    ("win_gravity", ctypes.c_int), ("backing_store", ctypes.c_int),
                    ("backing_planes", ctypes.c_ulong), ("backing_pixel", ctypes.c_ulong),
                    ("save_under", ctypes.c_int), ("colormap", ctypes.c_ulong), ("map_installed", ctypes.c_int),
                    ("map_state", ctypes.c_int), ("all_event_masks", ctypes.c_long),
                    ("your_event_mask", ctypes.c_long), ("do_not_propagate_mask", ctypes.c_long),
                    ("override_redirect", ctypes.c_int), ("screen", ctypes.c_void_p)]

    xlib.XQueryTree.argtypes = [ctypes.c_void_p, ctypes.c_ulong, ctypes.POINTER(ctypes.c_ulong),
                                ctypes.POINTER(ctypes.c_ulong), ctypes.POINTER(ctypes.POINTER(ctypes.c_ulong)),
                                ctypes.POINTER(ctypes.c_uint)]
    xlib.XGetWindowAttributes.argtypes = [ctypes.c_void_p, ctypes.c_ulong, ctypes.POINTER(Attributes)]
    xlib.XFetchName.argtypes = [ctypes.c_void_p, ctypes.c_ulong, ctypes.POINTER(ctypes.c_char_p)]
    xlib.XGetWindowProperty.argtypes = [ctypes.c_void_p, ctypes.c_ulong, ctypes.c_ulong, ctypes.c_long, ctypes.c_long,
                                        ctypes.c_int, ctypes.c_ulong, ctypes.POINTER(ctypes.c_ulong),
                                        ctypes.POINTER(ctypes.c_int), ctypes.POINTER(ctypes.c_ulong),
                                        ctypes.POINTER(ctypes.c_ulong), ctypes.POINTER(ctypes.c_void_p)]
    xlib.XFree.argtypes = [ctypes.c_void_p]
    xlib.XGetTransientForHint.argtypes = [ctypes.c_void_p, ctypes.c_ulong, ctypes.POINTER(ctypes.c_ulong)]
    handler = ctypes.CFUNCTYPE(ctypes.c_int, ctypes.c_void_p, ctypes.c_void_p)(lambda _display, _event: 0)
    xlib.XSetErrorHandler(handler)  # a window that vanished between XQueryTree and the next call is not an error

    def window_pid(window):
        kind, fmt, count, after, data = ctypes.c_ulong(), ctypes.c_int(), ctypes.c_ulong(), ctypes.c_ulong(), \
            ctypes.c_void_p()
        if xlib.XGetWindowProperty(display, window, pid_atom, 0, 1, False, 6, ctypes.byref(kind), ctypes.byref(fmt),
                                   ctypes.byref(count), ctypes.byref(after), ctypes.byref(data)) or not data.value:
            return 0
        pid = ctypes.cast(data, ctypes.POINTER(ctypes.c_ulong))[0] if count.value else 0
        xlib.XFree(data)
        return pid

    def owner(pid):
        try:
            with open("/proc/%d/comm" % pid, encoding="utf-8") as handle:
                return handle.read().strip()
        except OSError:
            return ""

    def sample(_keep=handler):
        found = []
        parent, root_out, children, count = ctypes.c_ulong(), ctypes.c_ulong(), \
            ctypes.POINTER(ctypes.c_ulong)(), ctypes.c_uint()
        if not xlib.XQueryTree(display, root, ctypes.byref(root_out), ctypes.byref(parent), ctypes.byref(children),
                               ctypes.byref(count)):
            return found
        windows = [children[i] for i in range(count.value)]
        if children:
            xlib.XFree(children)
        for window in windows:
            attributes = Attributes()
            if not xlib.XGetWindowAttributes(display, window, ctypes.byref(attributes)):
                continue
            if attributes.map_state != 2 or attributes.width < 150 or attributes.height < 100:  # IsViewable
                continue
            pid = window_pid(window)
            name = owner(pid) if pid else ""
            if pid and not any(name.startswith(n[:15]) for n in NAMES):
                continue
            title = ctypes.c_char_p()
            text = ""
            if xlib.XFetchName(display, window, ctypes.byref(title)) and title.value:
                text = title.value.decode("utf-8", "replace")
                xlib.XFree(title)
            transient = ctypes.c_ulong()
            dialog = xlib.XGetTransientForHint(display, window, ctypes.byref(transient)) and transient.value
            found.append((pid, attributes.width, attributes.height, text, "dialog" if dialog else ""))
        return found
    return sample


def _macos():
    cg = ctypes.CDLL("/System/Library/Frameworks/CoreGraphics.framework/CoreGraphics")
    cf = ctypes.CDLL("/System/Library/Frameworks/CoreFoundation.framework/CoreFoundation")
    void = ctypes.c_void_p
    cg.CGWindowListCopyWindowInfo.restype = void
    cg.CGWindowListCopyWindowInfo.argtypes = [ctypes.c_uint32, ctypes.c_uint32]
    cf.CFArrayGetCount.restype, cf.CFArrayGetCount.argtypes = ctypes.c_long, [void]
    cf.CFArrayGetValueAtIndex.restype, cf.CFArrayGetValueAtIndex.argtypes = void, [void, ctypes.c_long]
    cf.CFDictionaryGetValue.restype, cf.CFDictionaryGetValue.argtypes = void, [void, void]
    cf.CFStringCreateWithCString.restype = void
    cf.CFStringCreateWithCString.argtypes = [void, ctypes.c_char_p, ctypes.c_uint32]
    cf.CFStringGetCString.argtypes = [void, ctypes.c_char_p, ctypes.c_long, ctypes.c_uint32]
    cf.CFNumberGetValue.argtypes = [void, ctypes.c_int, void]
    cf.CFRelease.argtypes = [void]
    cg.CGRectMakeWithDictionaryRepresentation.argtypes = [void, void]

    class Rect(ctypes.Structure):
        _fields_ = [("x", ctypes.c_double), ("y", ctypes.c_double), ("w", ctypes.c_double), ("h", ctypes.c_double)]

    keys = {name: cf.CFStringCreateWithCString(None, name.encode(), 0x08000100)
            for name in ("kCGWindowOwnerName", "kCGWindowOwnerPID", "kCGWindowLayer", "kCGWindowBounds",
                         "kCGWindowName")}

    def text(value):
        if not value:
            return ""
        buffer = ctypes.create_string_buffer(512)
        return buffer.value.decode("utf-8", "replace") if cf.CFStringGetCString(value, buffer, 512, 0x08000100) else ""

    def number(value):
        out = ctypes.c_int64()
        return out.value if value and cf.CFNumberGetValue(value, 4, ctypes.byref(out)) else 0  # kCFNumberSInt64Type

    def sample():
        found = []
        array = cg.CGWindowListCopyWindowInfo(1, 0)  # kCGWindowListOptionOnScreenOnly
        if not array:
            return found
        try:
            for index in range(cf.CFArrayGetCount(array)):
                info = cf.CFArrayGetValueAtIndex(array, index)
                owner = text(cf.CFDictionaryGetValue(info, keys["kCGWindowOwnerName"]))
                if "soffice" not in owner and "HST Office" not in owner:
                    continue
                if number(cf.CFDictionaryGetValue(info, keys["kCGWindowLayer"])) != 0:
                    continue
                rect = Rect()
                cg.CGRectMakeWithDictionaryRepresentation(cf.CFDictionaryGetValue(info, keys["kCGWindowBounds"]),
                                                          ctypes.byref(rect))
                if rect.w < 150 or rect.h < 100:
                    continue
                found.append((number(cf.CFDictionaryGetValue(info, keys["kCGWindowOwnerPID"])), int(rect.w),
                              int(rect.h), text(cf.CFDictionaryGetValue(info, keys["kCGWindowName"])), ""))
        finally:
            cf.CFRelease(array)
        return found
    return sample


def sampler():
    """A function returning the visible office windows of this OS."""
    if sys.platform == "win32":
        return _windows()
    if sys.platform == "darwin":
        return _macos()
    return _x11()
