# SPDX-License-Identifier: AGPL-3.0-only
"""Visible office windows on Linux (X11), for scripts/perf/startup_window_samplers.py: the mapped children of the root
window owned by oosplash or soffice.bin (_NET_WM_PID) as [(pid, width, height, title, kind)], kind "dialog" for a
transient window, else left to the size rule. Sizes are device pixels."""
import ctypes
import ctypes.util

from startup_window_samplers import NAMES


def x11_sampler():
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
