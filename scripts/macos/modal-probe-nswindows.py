# SPDX-License-Identifier: AGPL-3.0-only
"""In-process probe script (profile Scripts/python): dumps the NSWindows of the office (visibility, native full
screen, native tab group and selection, parent window, Space) from the main thread to a JSON file. Evidence only."""
import ctypes
import json

import unohelper
from com.sun.star.awt import XCallback

_objc = ctypes.cdll.LoadLibrary("/usr/lib/libobjc.A.dylib")
ctypes.cdll.LoadLibrary("/System/Library/Frameworks/AppKit.framework/AppKit")
_objc.objc_getClass.restype = ctypes.c_void_p
_objc.objc_getClass.argtypes = [ctypes.c_char_p]
_objc.sel_registerName.restype = ctypes.c_void_p
_objc.sel_registerName.argtypes = [ctypes.c_char_p]
_SEND = ctypes.cast(_objc.objc_msgSend, ctypes.c_void_p).value


def _send(obj, sel, restype=ctypes.c_void_p, argtypes=(), *args):
    if not obj:
        return None
    fn = ctypes.CFUNCTYPE(restype, ctypes.c_void_p, ctypes.c_void_p, *argtypes)(_SEND)
    return fn(obj, _objc.sel_registerName(sel.encode()), *args)


def _text(ns):
    raw = _send(ns, "UTF8String", ctypes.c_char_p)
    return raw.decode("utf-8", "replace") if raw else ""


def _numbers(array):
    n = _send(array, "count", ctypes.c_ulong) or 0
    return [_send(_send(array, "objectAtIndex:", ctypes.c_void_p, (ctypes.c_ulong,), i), "windowNumber", ctypes.c_long)
            for i in range(n)]


def dump():
    app = _send(_objc.objc_getClass(b"NSApplication"), "sharedApplication")
    windows = _send(app, "windows")
    rows = []
    for i in range(_send(windows, "count", ctypes.c_ulong) or 0):
        w = _send(windows, "objectAtIndex:", ctypes.c_void_p, (ctypes.c_ulong,), i)
        title = _text(_send(w, "title"))
        group = _send(w, "tabGroup")
        tabbed = _send(w, "tabbedWindows")
        parent = _send(w, "parentWindow")
        row = {
            "number": _send(w, "windowNumber", ctypes.c_long), "title": title,
            "visible": bool(_send(w, "isVisible", ctypes.c_bool)),
            "key": bool(_send(w, "isKeyWindow", ctypes.c_bool)),
            "on_active_space": bool(_send(w, "isOnActiveSpace", ctypes.c_bool)),
            "fullscreen": bool((_send(w, "styleMask", ctypes.c_ulong) or 0) & (1 << 14)),
            "tabbed_windows": _numbers(tabbed) if tabbed else [],
            "tab_selected": _send(_send(group, "selectedWindow"), "windowNumber", ctypes.c_long) if group else None,
            "parent": _send(parent, "windowNumber", ctypes.c_long) if parent else None,
        }
        if title or row["visible"] or row["tabbed_windows"] or row["parent"]:
            rows.append(row)
    return rows


class _CB(unohelper.Base, XCallback):
    def __init__(self, path):
        self.path = path

    def notify(self, data):
        try:
            result = {"windows": dump()}
        except Exception as error:  # noqa: BLE001
            result = {"error": repr(error)}
        with open(self.path, "w", encoding="utf-8") as f:
            json.dump(result, f, ensure_ascii=False, indent=1)


def nswindows(path):
    ctx = XSCRIPTCONTEXT.getComponentContext()  # noqa: F821 - provided by the script framework
    ctx.ServiceManager.createInstanceWithContext("com.sun.star.awt.AsyncCallback", ctx).addCallback(_CB(path), None)
