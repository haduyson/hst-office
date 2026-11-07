# SPDX-License-Identifier: AGPL-3.0-only
"""Helpers of check-nd30-field-switch.py: keys posted inside VCL and timed to idle, the wizard of the HST menu inside the
office, the X focus of its window and closing test documents."""
import os
import subprocess
import threading
import time

TITLE = "Văn bản hành chính"
PARA = ("Thực hiện Nghị định số 30/2020/NĐ-CP ngày 05 tháng 3 năm 2020 của Chính phủ về công tác văn thư, Ủy ban nhân dân "
        "tỉnh đề nghị các sở, ban, ngành khẩn trương rà soát, báo cáo kết quả trước ngày quy định.")


class Robot:
    """Posts keys inside VCL (XToolkitRobot) and times them until the office has handled every pending event and idle
    task (XToolkitExperimental.processEventsToIdle): focus change, the edit's modify, the wizard's refresh, repaints."""

    def __init__(self, office):
        self.toolkit = office.service("com.sun.star.awt.Toolkit")

    @staticmethod
    def code(name):
        import uno
        return uno.getConstantByName("com.sun.star.awt.Key." + name)

    def press(self, target, name, char="", modifiers=0):
        from com.sun.star.awt import KeyEvent
        event = KeyEvent()
        event.Source, event.KeyCode, event.Modifiers = target, self.code(name), modifiers
        if char:
            event.KeyChar = char
        self.toolkit.keyPress(event)
        self.toolkit.keyRelease(event)

    def timed(self, target, name, char="", modifiers=0):
        self.toolkit.processEventsToIdle()
        start = time.perf_counter()
        self.press(target, name, char, modifiers)
        self.toolkit.processEventsToIdle()
        return (time.perf_counter() - start) * 1000


def set_clipboard(office, text):
    import uno
    import unohelper
    from com.sun.star.datatransfer import DataFlavor, XTransferable

    class Text(unohelper.Base, XTransferable):
        def _flavor(self):
            flavor = DataFlavor()
            flavor.MimeType, flavor.HumanPresentableName = "text/plain;charset=utf-16", "Unicode"
            flavor.DataType = uno.getTypeByName("string")
            return flavor

        def getTransferData(self, flavor):
            return text

        def getTransferDataFlavors(self):
            return (self._flavor(),)

        def isDataFlavorSupported(self, flavor):
            return flavor.MimeType.startswith("text/plain")

    office.service("com.sun.star.datatransfer.clipboard.SystemClipboard").setContents(Text(), None)


def close(doc):
    """Close a test document; right after a modal dialog the controller may still veto for a moment."""
    from com.sun.star.util import CloseVetoException
    doc.setModified(False)
    for _ in range(10):
        try:
            doc.close(True)
            return
        except CloseVetoException:
            time.sleep(1)
    print("document close vetoed; the office is stopped at the end anyway")


def focus_window(display):
    """Give the wizard's frame the X input focus (no window manager on the test display): posted keys go to the
    focused control of a focused frame only."""
    env = dict(os.environ, DISPLAY=display)
    found = subprocess.run(["xdotool", "search", "--onlyvisible", "--name", TITLE], env=env, capture_output=True,
                           text=True, check=False).stdout.split()
    if found:
        subprocess.run(["xdotool", "windowfocus", "--sync", found[-1]], env=env, check=False, timeout=30)
        time.sleep(0.5)


def open_wizard(office, robot):
    """(document, dialog peer, thread) with the wizard of the HST menu running inside the office."""
    doc = office.desktop().loadComponentFromURL("private:factory/swriter", "_blank", 0, ())
    time.sleep(2)
    frame = doc.getCurrentController().getFrame()
    thread = threading.Thread(target=lambda: office.dispatch(frame, "org.hst.office.vi:Nd30Wizard"), daemon=True)
    thread.start()
    for _ in range(150):
        time.sleep(0.2)
        top = wizard_window(robot.toolkit)
        if top is not None:
            time.sleep(1.5)
            focus_window(office.display)
            return doc, top, thread
    return doc, None, thread


def wizard_window(toolkit):
    """The wizard's top window, or None (gen without a window manager has no active top window: look at all of them)."""
    tops = [toolkit.getActiveTopWindow()] + [toolkit.getTopWindow(i) for i in range(toolkit.getTopWindowCount())]
    return next((top for top in tops if top is not None and getattr(top, "Title", "") == TITLE), None)
