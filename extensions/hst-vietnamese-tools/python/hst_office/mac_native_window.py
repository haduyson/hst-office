# SPDX-License-Identifier: LicenseRef-HST-Proprietary
"""macOS only: what AppKit knows about an office window (its NSWindow), read through the Objective-C runtime.

The office's UNO API cannot tell whether a window is in native full screen (the green button): XTopWindow3.FullScreen
is the office's own full screen mode, and Toolkit.getWorkArea() is the built-in display only, so a window in full
screen on a second display of another size did not count as full screen (dialog_on_screen). The window's NSView comes
from XSystemDependentWindowPeer.getWindowHandle(SYSTEM_MAC); [[view window] styleMask] says whether it is full screen,
on whichever display. Main thread only (AppKit), as every UNO window callback is. Every function answers None when it
cannot tell (another platform, no handle, no Objective-C runtime): callers keep their earlier rule then.
"""
import ctypes
import sys

SYSTEM_MAC = 3  # com.sun.star.lang.SystemDependent.SYSTEM_MAC
FULL_SCREEN_MASK = 1 << 14  # NSWindowStyleMaskFullScreen
_RUNTIME = {}


def _runtime():
    """(objc library, objc_msgSend address), loaded once; KeyError/OSError off macOS."""
    if "objc" not in _RUNTIME:
        objc = ctypes.cdll.LoadLibrary("/usr/lib/libobjc.A.dylib")
        objc.sel_registerName.restype = ctypes.c_void_p
        objc.sel_registerName.argtypes = [ctypes.c_char_p]
        _RUNTIME["objc"] = objc
        _RUNTIME["send"] = ctypes.cast(objc.objc_msgSend, ctypes.c_void_p).value
    return _RUNTIME["objc"], _RUNTIME["send"]


def send(obj, selector, restype=ctypes.c_void_p):
    """[obj selector] for a selector without arguments; None for a nil receiver."""
    if not obj:
        return None
    objc, address = _runtime()
    function = ctypes.CFUNCTYPE(restype, ctypes.c_void_p, ctypes.c_void_p)(address)
    return function(obj, objc.sel_registerName(selector.encode()))


def ns_window(peer):
    """The NSWindow (address) of an office top window peer, or None."""
    import uno
    handle = peer.getWindowHandle(uno.ByteSequence(bytes(16)), SYSTEM_MAC)  # the process id is not checked
    if not isinstance(handle, int) or handle == 0:
        return None
    return send(handle, "window") or None


def is_full_screen(peer, platform=None):
    """True/False: the window is in native full screen (any display); None when that cannot be read."""
    if (platform or sys.platform) != "darwin" or peer is None:
        return None
    try:
        window = ns_window(peer)
        if window is None:
            return None
        return bool((send(window, "styleMask", ctypes.c_ulong) or 0) & FULL_SCREEN_MASK)
    except Exception:  # noqa: BLE001 - no runtime or a disposed window: unknown
        return None
