# SPDX-License-Identifier: LicenseRef-HST-Proprietary
"""In-process part of the full screen dialog probe (copied to the profile's Scripts/python as hstfsprobe.py).

Every function posts its work to the main thread (AsyncCallback) and writes a JSON result file, so the remote driver
never blocks on a modal loop. Evidence only:
- trigger(url): dispatch a command on the current frame (a modal dialog then runs inside that callback);
- entry_edit(): the citation source form for an existing source (its on_ready fills every field);
- set_field / read_field: a control model value of the innermost open HST dialog (what the user typed);
- nswindows(path): the office's NSWindows (full screen, tab group, parent, Space);
- reparent(path): candidate rescue for a native office dialog left behind in a full screen Space: the visible titled
  child windows of a window that is not on the active Space become child windows of the key window.
"""
import ctypes
import json
import traceback

import uno
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


def _windows():
    app = _send(_objc.objc_getClass(b"NSApplication"), "sharedApplication")
    array = _send(app, "windows")
    return [_send(array, "objectAtIndex:", ctypes.c_void_p, (ctypes.c_ulong,), i)
            for i in range(_send(array, "count", ctypes.c_ulong) or 0)]


def _number(w):
    return _send(w, "windowNumber", ctypes.c_long) if w else None


def _row(w):
    group = _send(w, "tabGroup")
    tabbed = _send(w, "tabbedWindows")
    parent = _send(w, "parentWindow")
    count = _send(tabbed, "count", ctypes.c_ulong) or 0 if tabbed else 0
    return {
        "number": _number(w), "title": _text(_send(w, "title")),
        "visible": bool(_send(w, "isVisible", ctypes.c_bool)),
        "key": bool(_send(w, "isKeyWindow", ctypes.c_bool)),
        "on_active_space": bool(_send(w, "isOnActiveSpace", ctypes.c_bool)),
        "fullscreen": bool((_send(w, "styleMask", ctypes.c_ulong) or 0) & (1 << 14)),
        "titled": bool((_send(w, "styleMask", ctypes.c_ulong) or 0) & 1),
        "level": _send(w, "level", ctypes.c_long),
        "tabbed_windows": [_number(_send(tabbed, "objectAtIndex:", ctypes.c_void_p, (ctypes.c_ulong,), i))
                           for i in range(count)],
        "tab_selected": _number(_send(group, "selectedWindow")) if group else None,
        "parent": _number(parent) if parent else None,
    }


def dump():
    return [r for r in (_row(w) for w in _windows()) if r["title"] or r["visible"] or r["parent"]]


def _write(path, data):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=1)


class _Main(unohelper.Base, XCallback):
    def __init__(self, fn, path=None):
        self.fn, self.path = fn, path

    def notify(self, data):
        try:
            result = self.fn()
        except Exception:  # noqa: BLE001 - evidence: keep the traceback
            result = {"error": traceback.format_exc()}
        if self.path:
            _write(self.path, result if isinstance(result, dict) else {"result": result})


def _ctx():
    return XSCRIPTCONTEXT.getComponentContext()  # noqa: F821 - provided by the script framework


def _post(fn, path=None):
    ctx = _ctx()
    ctx.ServiceManager.createInstanceWithContext("com.sun.star.awt.AsyncCallback", ctx).addCallback(_Main(fn, path), None)


def trigger(url):
    def run():
        ctx = _ctx()
        smgr = ctx.ServiceManager
        frame = smgr.createInstanceWithContext("com.sun.star.frame.Desktop", ctx).getCurrentFrame()
        u = uno.createUnoStruct("com.sun.star.util.URL")
        u.Complete = url
        _, u = smgr.createInstanceWithContext("com.sun.star.util.URLTransformer", ctx).parseStrict(u)
        frame.queryDispatch(u, "_self", 0).dispatch(u, ())
    _post(run)


def entry_edit():
    def run():
        from hst_office import citation_entry_dialog, citation_refresh, citation_settings, citation_texts
        from hst_office.citation_library import Library
        ctx = _ctx()
        frame = ctx.ServiceManager.createInstanceWithContext("com.sun.star.frame.Desktop", ctx).getCurrentFrame()
        texts = citation_texts.load(ctx)
        settings = citation_settings.default_settings(texts["language"])
        style = citation_refresh.engine().load_style(settings["style"], settings["opts"], settings.get("preset"))
        item = {"id": "probe-1", "type": "book", "title": "Old title", "author": [{"family": "Nguyen", "given": "An"}],
                "publisher": "Old publisher", "issued": {"date-parts": [[2020]]}}
        citation_entry_dialog.run(ctx, frame.getContainerWindow(), texts, item, Library("/dev/null/none"), style,
                                  save_default=False, language=texts["language"])
    _post(run)


def _innermost():
    from hst_office import dialog_registry
    return dialog_registry.OPEN[-1] if dialog_registry.OPEN else None


def set_field(name, text, path):
    def run():
        d = _innermost()
        if d is None:
            return {"open": 0}
        d.getModel().getByName(name).Text = text
        return {"title": d.getModel().Title, "value": d.getModel().getByName(name).Text}
    _post(run, path)


def read_field(name, path):
    def run():
        from hst_office import dialog_registry
        d = _innermost()
        if d is None:
            return {"open": 0}
        return {"open": len(dialog_registry.OPEN), "title": d.getModel().Title,
                "value": d.getModel().getByName(name).Text}
    _post(run, path)


def nswindows(path):
    _post(lambda: {"windows": dump()}, path)


def reparent(path):
    """Titled visible child windows whose parent is not on the active Space move under the key window."""
    def run():
        app = _send(_objc.objc_getClass(b"NSApplication"), "sharedApplication")
        key = _send(app, "keyWindow") or _send(app, "mainWindow")
        moved = []
        for w in _windows():
            parent = _send(w, "parentWindow")
            if not parent or not key or parent == key:
                continue
            row = _row(w)
            if not row["visible"] or not row["titled"]:
                continue
            if bool(_send(parent, "isOnActiveSpace", ctypes.c_bool)):
                continue
            _send(parent, "removeChildWindow:", None, (ctypes.c_void_p,), w)
            _send(key, "addChildWindow:ordered:", None, (ctypes.c_void_p, ctypes.c_long), w, 1)
            _send(w, "makeKeyAndOrderFront:", None, (ctypes.c_void_p,), None)
            moved.append({"window": row, "from": _number(parent), "to": _number(key)})
        return {"key": _number(key), "moved": moved, "windows": dump()}
    _post(run, path)


def watcher(path):
    def run():
        from hst_office import mac_full_screen_dialogs
        return {"watching": mac_full_screen_dialogs._STATE.get("listener") is not None}
    _post(run, path)
