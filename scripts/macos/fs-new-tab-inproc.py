# SPDX-License-Identifier: LicenseRef-HST-Proprietary
# Copyright (C) 2026 HASON TECH
"""In-process probe script (profile Scripts/python). Every function runs its work on the main thread
(AsyncCallback) and writes JSON to `path`: NSWindows (Space, full screen, native tabs, parent, key), the
office frames (title, visible, enabled, active), a main-thread document load / new-tab dispatch, and
switching the macOS full screen dialog adopter (hst_office.mac_full_screen_dialogs) off. Evidence only."""
import ctypes
import json
import sys

import unohelper
from com.sun.star.awt import XCallback
from com.sun.star.beans import PropertyValue

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


def _num(w):
    return _send(w, "windowNumber", ctypes.c_long) if w else None


def _numbers(array):
    n = _send(array, "count", ctypes.c_ulong) or 0
    return [_num(_send(array, "objectAtIndex:", ctypes.c_void_p, (ctypes.c_ulong,), i)) for i in range(n)]


def nswindows_rows():
    app = _send(_objc.objc_getClass(b"NSApplication"), "sharedApplication")
    windows = _send(app, "windows")
    rows = []
    for i in range(_send(windows, "count", ctypes.c_ulong) or 0):
        w = _send(windows, "objectAtIndex:", ctypes.c_void_p, (ctypes.c_ulong,), i)
        group = _send(w, "tabGroup")
        tabbed = _send(w, "tabbedWindows")
        cls = _text(_send(_send(w, "className"), "description")) if w else ""
        row = {
            "n": _num(w), "class": cls, "title": _text(_send(w, "title")),
            "visible": bool(_send(w, "isVisible", ctypes.c_bool)),
            "key": bool(_send(w, "isKeyWindow", ctypes.c_bool)),
            "main": bool(_send(w, "isMainWindow", ctypes.c_bool)),
            "active_space": bool(_send(w, "isOnActiveSpace", ctypes.c_bool)),
            "mask": _send(w, "styleMask", ctypes.c_ulong),
            "fullscreen": bool((_send(w, "styleMask", ctypes.c_ulong) or 0) & (1 << 14)),
            "level": _send(w, "level", ctypes.c_long),
            "tabbed": _numbers(tabbed) if tabbed else [],
            "tab_selected": _num(_send(group, "selectedWindow")) if group else None,
            "tabbar": bool(_send(group, "isTabBarVisible", ctypes.c_bool)) if group else None,
            "parent": _num(_send(w, "parentWindow")),
            "children": _numbers(_send(w, "childWindows")) if _send(w, "childWindows") else [],
        }
        rows.append(row)
    app_info = {"key": _num(_send(app, "keyWindow")), "main": _num(_send(app, "mainWindow")),
                "modal": _num(_send(app, "modalWindow")), "active": bool(_send(app, "isActive", ctypes.c_bool))}
    return {"app": app_info, "windows": rows}


def frames_rows(ctx):
    desktop = ctx.ServiceManager.createInstanceWithContext("com.sun.star.frame.Desktop", ctx)
    frames = desktop.getFrames()
    out = []
    for i in range(frames.getCount()):
        f = frames.getByIndex(i)
        w = f.getContainerWindow()
        text = None
        try:
            model = f.getController().getModel()
            if model.supportsService("com.sun.star.text.TextDocument"):
                text = model.getText().getString()[-40:]
            elif model.supportsService("com.sun.star.sheet.SpreadsheetDocument"):
                sel = f.getController().getSelection()
                text = "cell:" + (sel.getString() if hasattr(sel, "getString") else "?")
        except Exception:  # noqa: BLE001
            pass
        out.append({"title": f.getTitle(), "visible": w.isVisible(), "enabled": w.isEnabled(),
                    "active": f.isActive(), "text": text})
    return out


def _adopter():
    for name, mod in list(sys.modules.items()):
        if name.endswith("mac_full_screen_dialogs") and hasattr(mod, "_STATE"):
            return mod
    return None


class _CB(unohelper.Base, XCallback):
    def __init__(self, ctx, path, work):
        self.ctx, self.path, self.work = ctx, path, work

    def notify(self, data):
        try:
            result = self.work(self.ctx)
        except Exception as error:  # noqa: BLE001
            result = {"error": repr(error)}
        with open(self.path, "w", encoding="utf-8") as f:
            json.dump(result, f, ensure_ascii=False, indent=1)


def _post(path, work):
    ctx = XSCRIPTCONTEXT.getComponentContext()  # noqa: F821 - provided by the script framework
    ctx.ServiceManager.createInstanceWithContext("com.sun.star.awt.AsyncCallback", ctx).addCallback(
        _CB(ctx, path, work), None)


def state(path):
    _post(path, lambda ctx: {"ns": nswindows_rows(), "frames": frames_rows(ctx),
                             "adopter": None if _adopter() is None else repr(_adopter()._STATE.get("listener"))})


def load(path, url):
    def work(ctx):
        desktop = ctx.ServiceManager.createInstanceWithContext("com.sun.star.frame.Desktop", ctx)
        desktop.loadComponentFromURL(url, "_blank", 0, ())
        return {"loaded": url}
    _post(path, work)


def new_tab(path, title_part):
    """What the tab strip "+" ends in (DocumentTabGroup::DispatchHdl): the factory URL into _blank from the frame."""
    def work(ctx):
        desktop = ctx.ServiceManager.createInstanceWithContext("com.sun.star.frame.Desktop", ctx)
        frames = desktop.getFrames()
        for i in range(frames.getCount()):
            f = frames.getByIndex(i)
            if title_part in f.getTitle() and f.getContainerWindow().isVisible():
                model = f.getController().getModel()
                url = "private:factory/scalc" if model.supportsService(
                    "com.sun.star.sheet.SpreadsheetDocument") else "private:factory/swriter"
                helper = ctx.ServiceManager.createInstanceWithContext("com.sun.star.frame.DispatchHelper", ctx)
                helper.executeDispatch(f, url, "_blank", 0, ())
                return {"dispatched": url, "from": f.getTitle()}
        return {"error": "no frame " + title_part}
    _post(path, work)


def to_front(path, title_part):
    def work(ctx):
        desktop = ctx.ServiceManager.createInstanceWithContext("com.sun.star.frame.Desktop", ctx)
        frames = desktop.getFrames()
        for i in range(frames.getCount()):
            f = frames.getByIndex(i)
            if title_part in f.getTitle() and f.getContainerWindow().isVisible():
                f.getContainerWindow().toFront()
                f.activate()
                return {"front": f.getTitle()}
        return {"error": "no frame " + title_part}
    _post(path, work)


def disable_adopter(path):
    def work(ctx):
        mod = _adopter()
        if mod is None:
            return {"adopter": "not loaded (1.0.3 has none)"}
        listener = mod._STATE.get("listener")
        if listener is not None:
            ctx.getValueByName("/singletons/com.sun.star.frame.theGlobalEventBroadcaster") \
                .removeDocumentEventListener(listener)
        mod._STATE["listener"] = object()  # start() must not add it again
        return {"adopter": "removed" if listener is not None else "was not listening"}
    _post(path, work)
