# SPDX-License-Identifier: AGPL-3.0-only
"""Helpers of check-backstage.py: AT-SPI access to the File panel, a recording dispatch interceptor, test documents."""
import importlib.util
import os
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import hst_gui  # noqa: E402

_spec = importlib.util.spec_from_file_location("nd30_entry", os.path.join(HERE, "check-nd30-entry.py"))
nd30 = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(nd30)

ROWS = []
COMMAND = ".uno:HSTBackstage"
ALL_ITEMS = ["Trang chủ", "Mới", "Mở", "Thông tin", "Lưu", "Lưu thành", "In", "Xuất PDF", "Ký số", "Đóng",
             "Giới thiệu HST Office", "Tùy chọn"]


def record(name, ok, detail=""):
    ROWS.append((name, ok))
    print("%s  %s  %s" % ("PASS" if ok else "FAIL", name, str(detail)[:300]), flush=True)


def xdo(display, *args):
    subprocess.run(["xdotool", *args], env=dict(os.environ, DISPLAY=display), check=False, timeout=20)


def walk(node, out, depth=0):
    """(role, name, node) of the widgets; document content (a sheet exposes every cell) is skipped."""
    try:
        role = node.getRoleName()
        out.append((role, node.name, node))
        if role.startswith("document") or node.childCount > 500:
            return out
        for index in range(node.childCount):
            walk(node.getChildAtIndex(index), out, depth + 1)
    except Exception:  # noqa: BLE001 - a widget may vanish while walking
        pass
    return out


def showing(found):
    import pyatspi
    return [(role, name, node) for role, name, node in found if node.getState().contains(pyatspi.STATE_SHOWING)]


def view_items():
    """Showing push buttons by name without a trailing ellipsis; the panel is open when the whole left column shows."""
    found = showing(walk(nd30.office_app(), []))
    return {name.rstrip("…."): node for role, name, node in found if role == "push button" and name}


def is_open():
    items = view_items()
    return all(name in items for name in ALL_ITEMS)


def wait_state(want, timeout=8):
    deadline = time.time() + timeout
    while time.time() < deadline:
        if is_open() == want:
            return True
        time.sleep(0.2)
    return False


def press(node):
    action = node.queryAction()
    for index in range(action.nActions):
        if action.getName(index) in ("click", "press", "activate"):
            action.doAction(index)
            return True
    return False


def focused_name():
    import pyatspi
    for _role, name, node in walk(nd30.office_app(), []):
        if node.getState().contains(pyatspi.STATE_FOCUSED):
            return name
    return None


def make_interceptor(stubbed):
    import unohelper
    from com.sun.star.frame import XDispatch, XDispatchProviderInterceptor

    class Interceptor(unohelper.Base, XDispatchProviderInterceptor, XDispatch):
        """Records the commands of the panel and swallows them, so no dialog opens and no document closes."""

        def __init__(self):
            self.calls = []
            self.slave = self.master = None
            self.stubbed = set(stubbed)

        def queryDispatch(self, url, target, flags):
            if url.Complete in self.stubbed:
                return self
            return self.slave.queryDispatch(url, target, flags)

        def queryDispatches(self, requests):
            return tuple(self.queryDispatch(r.FeatureURL, r.FrameName, r.SearchFlags) for r in requests)

        def getSlaveDispatchProvider(self):
            return self.slave

        def setSlaveDispatchProvider(self, provider):
            self.slave = provider

        def getMasterDispatchProvider(self):
            return self.master

        def setMasterDispatchProvider(self, provider):
            self.master = provider

        def dispatch(self, url, _args):
            self.calls.append(url.Complete)

        def addStatusListener(self, _listener, _url):
            pass

        def removeStatusListener(self, _listener, _url):
            pass

    return Interceptor()


def expect_call(interceptor, command, timeout=5):
    deadline = time.time() + timeout
    while time.time() < deadline:
        if command in interceptor.calls:
            return True
        time.sleep(0.1)
    return False


def open_ms(office, frame):
    """Milliseconds of one .uno:HSTBackstage dispatch that opens the panel (includes the UNO round trip)."""
    start = time.perf_counter()
    office.dispatch(frame, COMMAND)
    return (time.perf_counter() - start) * 1000


def seed_recent(office, directory, factory, extension, filter_name):
    """Save a document through the Save As command so that it enters the recent list; returns the file name."""
    from com.sun.star.beans import PropertyValue
    name = "tep-gan-day-%s%s" % (factory, extension)
    path = os.path.join(directory, name)
    document = office.load("private:factory/" + factory)
    frame = document.CurrentController.Frame
    url, flt = PropertyValue(), PropertyValue()
    url.Name, url.Value = "URL", "file://" + path
    flt.Name, flt.Value = "FilterName", filter_name
    office.dispatch(frame, ".uno:SaveAs", (url, flt))
    close_document(document)
    return name


def close_document(document, timeout=30):
    """Close, waiting while a just dispatched command still vetoes it."""
    deadline = time.time() + timeout
    while True:
        time.sleep(1)
        try:
            document.close(True)
            time.sleep(1)
            return
        except Exception:  # noqa: BLE001 - com.sun.star.util.CloseVetoException
            if time.time() > deadline:
                raise


def dark_shot(args, path):
    """The approval screenshot in the dark theme, from its own office instance."""
    office = hst_gui.Office(args.instdir, os.path.join(args.out, "work-dark"), args.port + 1, display=args.display,
                            env={"GTK_THEME": "Adwaita:dark"})
    office.start()
    try:
        document = office.load("private:factory/swriter")
        time.sleep(3)
        office.dispatch(document.CurrentController.Frame, COMMAND)
        time.sleep(2)
        hst_gui.screenshot(path, args.display)
        office.dispatch(document.CurrentController.Frame, COMMAND)
        close_document(document)
    finally:
        office.stop()


def reopen(office, frame):
    if not is_open():
        office.dispatch(frame, COMMAND)
        wait_state(True)
    time.sleep(0.5)
