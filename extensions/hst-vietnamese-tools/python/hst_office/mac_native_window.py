# SPDX-License-Identifier: LicenseRef-HST-Proprietary
"""macOS only: what AppKit knows about an office window (its NSWindow), read through the Objective-C runtime.

The office's UNO API cannot tell whether a window is in native full screen (the green button): XTopWindow3.FullScreen
is the office's own full screen mode, and Toolkit.getWorkArea() is the built-in display only, so a window in full
screen on a second display of another size did not count as full screen (dialog_on_screen). The window's NSView comes
from XSystemDependentWindowPeer.getWindowHandle(SYSTEM_MAC); [[view window] styleMask] says whether it is full screen,
on whichever display. adopt_dialogs() moves a dialog left behind in another full screen Space onto the window the
user is in. Main thread only (AppKit), as every UNO window callback is. Every function answers None when it
cannot tell (another platform, no handle, no Objective-C runtime): callers keep their earlier rule then.
"""
import ctypes
import sys

SYSTEM_MAC = 3  # com.sun.star.lang.SystemDependent.SYSTEM_MAC
FULL_SCREEN_MASK = 1 << 14  # NSWindowStyleMaskFullScreen
TITLED_MASK = 1  # NSWindowStyleMaskTitled: dialogs; menus, tooltips and the document tab strip have no title bar
ABOVE = 1  # NSWindowAbove
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


def send(obj, selector, restype=ctypes.c_void_p, argtypes=(), *args):
    """[obj selector...] with `args` of the C types `argtypes`; None for a nil receiver."""
    if not obj:
        return None
    objc, address = _runtime()
    function = ctypes.CFUNCTYPE(restype, ctypes.c_void_p, ctypes.c_void_p, *argtypes)(address)
    return function(obj, objc.sel_registerName(selector.encode()), *args)


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


def _flag(window, selector):
    return bool(send(window, selector, ctypes.c_bool))


def _mask(window):
    return send(window, "styleMask", ctypes.c_ulong) or 0


def app_windows():
    """[NSApp windows] as addresses."""
    objc, _address = _runtime()
    objc.objc_getClass.restype = ctypes.c_void_p
    objc.objc_getClass.argtypes = [ctypes.c_char_p]
    array = send(send(objc.objc_getClass(b"NSApplication"), "sharedApplication"), "windows")
    count = send(array, "count", ctypes.c_ulong) or 0
    return [send(array, "objectAtIndex:", ctypes.c_void_p, (ctypes.c_ulong,), i) for i in range(count)]


def stranded_dialogs(target, windows):
    """The dialogs (shown titled child windows) whose parent is in native full screen on a Space the user left, while
    `target` is on the Space the user is in: what a document opened in its own full screen Space leaves behind."""
    if not target or not _flag(target, "isOnActiveSpace"):
        return []
    found = []
    for window in windows:
        parent = send(window, "parentWindow")
        if not parent or parent == target or window == target:
            continue
        if not (_flag(window, "isVisible") and _mask(window) & TITLED_MASK):
            continue
        if _mask(parent) & FULL_SCREEN_MASK and not _flag(parent, "isOnActiveSpace"):
            found.append((window, parent))
    return found


def adopt_dialogs(peer, platform=None):
    """Move the dialogs stranded in another full screen Space (stranded_dialogs) onto the window of `peer`: a child
    window shows in its parent's Space. The office keeps its own parent for the dialog (the document it acts on);
    when the dialog closes the office brings that document back. Returns how many moved; 0 off macOS. Raises when
    AppKit cannot be asked (the caller logs it)."""
    if (platform or sys.platform) != "darwin" or peer is None:
        return 0
    target = ns_window(peer)
    moved = 0
    for window, parent in stranded_dialogs(target, app_windows()):
        send(parent, "removeChildWindow:", None, (ctypes.c_void_p,), window)
        send(target, "addChildWindow:ordered:", None, (ctypes.c_void_p, ctypes.c_long), window, ABOVE)
        send(window, "makeKeyAndOrderFront:", None, (ctypes.c_void_p,), None)
        moved += 1
    return moved
