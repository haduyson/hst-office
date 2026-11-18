# SPDX-License-Identifier: AGPL-3.0-only
"""Office commands of scripts/macos/app-launchers-probe.py (bundled python with pyuno; the office's UNO pipe comes
from the probe profile): frame titles, top windows, the options buttons of the app icons, quit diagnostics, Impress's
template dialog and the File ▸ New check."""
import importlib.util
import json
import sys
import time
from pathlib import Path

_probe = None


def _main_module():
    """app-launchers-probe.py (its file name is not an identifier): connect(), context() and kinds_of()."""
    global _probe
    if _probe is None:
        spec = importlib.util.spec_from_file_location("app_launchers_probe",
                                                      Path(__file__).resolve().parent / "app-launchers-probe.py")
        _probe = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(_probe)
    return _probe


def connect(timeout):
    return _main_module().connect(timeout)


def context(timeout):
    return _main_module().context(timeout)


def kinds_of(components):
    return _main_module().kinds_of(components)


def until(check, timeout, what):
    """Poll check() -> (done, detail) once a second; prints the outcome as JSON, 0 when done."""
    started, detail = time.time(), None
    while time.time() - started < timeout:
        try:
            done, detail = check()
        except Exception as exc:  # noqa: BLE001 - the office may be busy starting; try again
            done, detail = False, str(exc)
        if done:
            print(json.dumps({"ok": True, what: detail, "seconds": round(time.time() - started, 1)}, ensure_ascii=False))
            return 0
        time.sleep(1)
    print(json.dumps({"ok": False, what: detail}, ensure_ascii=False))
    return 1


def title(text, timeout):
    desktop = connect(timeout)

    def check():
        titles = [desktop.Frames.getByIndex(i).Title for i in range(desktop.Frames.getCount())]
        return any(text in t for t in titles), titles
    return until(check, timeout, "frames")


def window(name, timeout):
    ctx = context(timeout)
    toolkit = ctx.ServiceManager.createInstanceWithContext("com.sun.star.awt.Toolkit", ctx)

    def check():
        shown = [getattr(toolkit.getTopWindow(i), "Title", "") for i in range(toolkit.getTopWindowCount())
                 if toolkit.getTopWindow(i).isVisible()]
        return name in shown, shown
    return until(check, timeout, "windows")


def icons(action, python_dir):
    """The options buttons' own code (hst_office.mac_app_launchers_ui) over the office's context."""
    sys.path.insert(0, python_dir)
    from hst_office import mac_app_launchers_ui as ui
    ctx = context(30)
    run = ui.add_from_options if action == "add" else ui.remove_from_options
    shown = []
    run(ctx, lambda text, ask=False, button=None: shown.append(text) or True)
    print(json.dumps({"action": action, "messages": shown}, ensure_ascii=False))
    expected = ui.OPTIONS["removed"] if action == "remove" else ui.OPTIONS["added"].split("%s")[0]
    return 0 if shown and shown[-1].startswith(expected) else 1


def trace(seconds):
    """Every change of the desktop's frames and their controllers for `seconds` (what startup_activity compares)."""
    desktop = connect(120)
    started, before = time.time(), []
    while time.time() - started < seconds:
        try:
            now = [(f, f.getController()) for f in (desktop.Frames.getByIndex(i) for i in range(desktop.Frames.getCount()))]
        except Exception as exc:  # noqa: BLE001 - a frame closed while it was read
            print(json.dumps({"t": round(time.time() - started, 1), "error": str(exc)}))
            continue
        for frame, controller in now:
            old = next((c for f, c in before if f == frame), False)
            if old is False or not ((old is None and controller is None) or (old is not None and old == controller)):
                print(json.dumps({"t": round(time.time() - started, 1), "event": "new frame" if old is False else
                                  "controller changed", "title": frame.Title, "visible":
                                  bool(frame.getContainerWindow().isVisible()), "controller": controller is not None},
                                 ensure_ascii=False), flush=True)
        for frame, _c in before:
            if not any(frame == f for f, _x in now):
                print(json.dumps({"t": round(time.time() - started, 1), "event": "frame gone"}), flush=True)
        before = now
        time.sleep(0.2)
    return 0


def frames():
    """Diagnostic: title and document kind of each frame of the desktop (what a quit has to close)."""
    desktop = connect(20)
    rows = []
    for index in range(desktop.Frames.getCount()):
        frame = desktop.Frames.getByIndex(index)
        controller = frame.getController()
        model = controller.getModel() if controller is not None else None
        kind = kinds_of([model]) if model is not None else {}
        rows.append({"title": frame.Title, "kind": next(iter(kind), "none"),
                     "modified": bool(model.isModified()) if model is not None and hasattr(model, "isModified")
                     else None})
    ctx = context(20)
    toolkit = ctx.ServiceManager.createInstanceWithContext("com.sun.star.awt.Toolkit", ctx)
    windows = []
    for index in range(toolkit.getTopWindowCount()):
        window = toolkit.getTopWindow(index)
        accessible = window.getAccessibleContext() if hasattr(window, "getAccessibleContext") else None
        title = getattr(window, "Title", None) or (accessible.getAccessibleName() if accessible else "")
        windows.append({"title": title, "visible": bool(window.isVisible()) if hasattr(window, "isVisible") else None,
                        "role": accessible.getAccessibleRole() if accessible else None})
    print(json.dumps({"frames": rows, "top_windows": windows}, ensure_ascii=False))
    return 0


def template(enabled):
    """Impress's template dialog with every new presentation (Options ▸ Impress ▸ General), read when Impress loads."""
    import uno
    ctx = context(30)
    arg = uno.createUnoStruct("com.sun.star.beans.PropertyValue")
    arg.Name, arg.Value = "nodepath", "/org.openoffice.Office.Impress/Misc/NewDoc"
    node = ctx.ServiceManager.createInstanceWithContext("com.sun.star.configuration.ConfigurationProvider", ctx)\
        .createInstanceWithArguments("com.sun.star.configuration.ConfigurationUpdateAccess", (arg,))
    node.setPropertyValue("AutoPilot", enabled)
    node.commitChanges()
    return 0


def window_gone(title):
    """0 when no visible top window of the office has this title."""
    ctx = context(30)
    toolkit = ctx.ServiceManager.createInstanceWithContext("com.sun.star.awt.Toolkit", ctx)
    for index in range(toolkit.getTopWindowCount()):
        window = toolkit.getTopWindow(index)
        if getattr(window, "Title", "") == title and window.isVisible():
            return 1
    return 0


def no_base_menu():
    import uno
    ctx = context(30)
    arg = uno.createUnoStruct("com.sun.star.beans.PropertyValue")
    arg.Name, arg.Value = "nodepath", "/org.openoffice.Office.Common/Menus/New"
    node = ctx.ServiceManager.createInstanceWithContext("com.sun.star.configuration.ConfigurationProvider", ctx)\
        .createInstanceWithArguments("com.sun.star.configuration.ConfigurationAccess", (arg,))
    urls = [node.getByName(name).getPropertyValue("URL") for name in node.getElementNames()]
    print(json.dumps(urls))
    return 1 if any("sdatabase" in url for url in urls) or not any("swriter" in url for url in urls) else 0


