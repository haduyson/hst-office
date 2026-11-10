# SPDX-License-Identifier: AGPL-3.0-only
"""Which OS accessibility route reaches the office's windows (tooling Python; evidence, no checks).

macOS: the AX app element before and after AXManualAccessibility / AXEnhancedUserInterface, with error codes, and
the WindowServer's own window list for the process. Windows: every visible top-level window, the office's MSAA
objects (AccessibleObjectFromWindow) and its UI Automation children."""
import platform


def mac():
    import ApplicationServices as ax
    import Quartz as q
    from mac_access import applications
    out = []
    for app in applications():
        pid = app.processIdentifier()
        element = ax.AXUIElementCreateApplication(pid)
        row = dict(pid=pid, trusted=bool(ax.AXIsProcessTrusted()))
        def read(stage):
            for name in ("AXChildren", "AXWindows", "AXMainWindow", "AXFocusedWindow"):
                error, value = ax.AXUIElementCopyAttributeValue(element, name, None)
                count = len(value) if isinstance(value, (list, tuple)) or hasattr(value, "count") else (value is not None)
                row[f"{stage}:{name}"] = [int(error), count if not error else None]
        read("before")
        for name in ("AXManualAccessibility", "AXEnhancedUserInterface"):
            row["set:" + name] = int(ax.AXUIElementSetAttributeValue(element, name, True))
        import time
        time.sleep(2)
        read("after")
        windows = q.CGWindowListCopyWindowInfo(q.kCGWindowListOptionAll, q.kCGNullWindowID) or []
        row["windowserver"] = [dict(name=str(w.get("kCGWindowName", "")), layer=int(w.get("kCGWindowLayer", 0)),
                                    onscreen=bool(w.get("kCGWindowIsOnscreen", False)),
                                    bounds=dict(w.get("kCGWindowBounds", {})))
                               for w in windows if int(w.get("kCGWindowOwnerPID", -1)) == pid][:12]
        out.append(row)
    return out


def windows():
    import ctypes
    from ctypes import wintypes
    import psutil
    user32, found = ctypes.windll.user32, []
    def visit(hwnd, _):
        if user32.IsWindowVisible(hwnd):
            pid = wintypes.DWORD()
            user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
            title, kind = ctypes.create_unicode_buffer(256), ctypes.create_unicode_buffer(128)
            user32.GetWindowTextW(hwnd, title, 256)
            user32.GetClassNameW(hwnd, kind, 128)
            try:
                name = psutil.Process(pid.value).name()
            except Exception as error:
                name = type(error).__name__
            found.append(dict(hwnd=int(hwnd or 0), pid=pid.value, process=name, enabled=bool(user32.IsWindowEnabled(hwnd)),
                              title=title.value[:60], cls=kind.value))
        return True
    user32.EnumWindows(ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)(visit), 0)
    office = [w for w in found if w["process"].lower().startswith("soffice")]
    for w in office[:4]:
        try:
            import comtypes.client
            comtypes.client.GetModule("oleacc.dll")  # generates comtypes.gen.Accessibility
            from comtypes import POINTER
            from comtypes.gen.Accessibility import IAccessible
            pointer = POINTER(IAccessible)()
            result = ctypes.oledll.oleacc.AccessibleObjectFromWindow(w["hwnd"], -4, ctypes.byref(IAccessible._iid_),
                                                                      ctypes.byref(pointer))
            w["msaa"] = dict(result=result, children=pointer.accChildCount, name=str(pointer.accName(0)))
        except Exception as error:
            w["msaa"] = f"{type(error).__name__}: {error}"[:200]
        try:
            from pywinauto.uia_element_info import UIAElementInfo
            info = UIAElementInfo(handle=w["hwnd"])
            kids = info.children()
            w["uia"] = dict(children=len(kids), first=[(k.control_type, k.name[:40]) for k in kids[:12]],
                            descendants=len(info.descendants()))
        except Exception as error:
            w["uia"] = f"{type(error).__name__}: {error}"[:200]
    return dict(office=office, others=[w for w in found if w not in office][:15])


def diagnose():
    return mac() if platform.system() == "Darwin" else windows()
