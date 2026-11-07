#!/usr/bin/env python3
# SPDX-License-Identifier: AGPL-3.0-only
"""ND30 wizard: moving between fields and typing stay fast, and every one-line field is as high as the platform draws it.

Usage: python3 tests/runtime/check-nd30-field-switch.py --display :131 [--instdir upstream/libreoffice/instdir]
                                                        [--out DIR] [--port 2195] [--max-median-ms 100] [--max-ms 500]
The display must already run (1366x768); it is never started or stopped here. HST_VCLPLUGIN=gen checks the gen backend.

Timing: the wizard runs inside the office (HST menu command), for "Công văn", "Quyết định" and the Party "Thông tri".
Keys are posted inside VCL (XToolkitRobot), so the X server or a VM cannot drop them. Each Tab or digit is timed from the
post until the office is idle again (processEventsToIdle): VCL focus handling, the edit's change, the wizard's refresh()
of the preview and the repaints. Tabs through the empty and the
filled form (with a 40-paragraph body), digits typed in every field.

Type then Tab: a query typed in "Loại văn bản" and Tab take the highlighted type, close the list and move to the next
field (the open list used to cover the next seven fields, typing went nowhere and the type was silently lost).

Height: the wizard is built over the bridge; each one-line edit must be at least as high as its preferred height
(Edit::CalcMinimumSize: text height plus borders, or the native frame when higher; 29 px on macOS), or fill all the
room down to the control below it. A 12-unit edit was
lower than that on macOS (text pinned to the top border, descenders of g/y cut) and on gen (hook of Ủ cut).
Exit 1 on any failure.
"""
import argparse
import os
import statistics
import subprocess
import sys
import threading
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path[:0] = [HERE, os.path.join(os.path.dirname(os.path.dirname(HERE)), "extensions/hst-vietnamese-tools/python")]
import hst_gui  # noqa: E402

ROWS = []
TITLE = "Văn bản hành chính"
PARA = ("Thực hiện Nghị định số 30/2020/NĐ-CP ngày 05 tháng 3 năm 2020 của Chính phủ về công tác văn thư, Ủy ban nhân dân "
        "tỉnh đề nghị các sở, ban, ngành khẩn trương rà soát, báo cáo kết quả trước ngày quy định.")


def check(name, ok, detail=""):
    ROWS.append(bool(ok))
    print("%s  %s  %s" % ("PASS" if ok else "FAIL", name, str(detail)[:300]), flush=True)


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


def timing(office, args):
    robot = Robot(office)
    set_clipboard(office, "\n".join([PARA] * 40))
    for query in ("cong van", "quyet dinh", "thong tri"):
        doc, dialog, thread = open_wizard(office, robot)
        check("%s: the wizard opens" % query, dialog is not None)
        if dialog is None:
            continue
        # choose the type with real keys: a Return posted inside VCL bypasses the list's key handler and presses "Chèn"
        env = dict(os.environ, DISPLAY=args.display)
        subprocess.run(["xdotool", "type", "--delay", "40", query], env=env, check=False, timeout=30)
        time.sleep(0.8)
        subprocess.run(["xdotool", "key", "Return"], env=env, check=False, timeout=30)
        time.sleep(1)
        if wizard_window(robot.toolkit) is None:
            check("%s: the type was chosen in the open wizard" % query, False, "the wizard closed")
            close(doc)
            continue
        tabs = [robot.timed(dialog, "TAB") for _ in range(20)]
        for _ in range(20):
            robot.press(dialog, "TAB", modifiers=1)  # Shift+Tab back to the type field
        time.sleep(0.5)
        keys = []
        for field in range(15):  # Tab to the next stop, type two digits (the 7th stop is the date: keep it valid)
            tabs.append(robot.timed(dialog, "TAB"))
            if field == 9:  # "Nội dung": paste the 40-paragraph body
                keys.append(robot.timed(dialog, "V", "v", modifiers=2))
            elif field != 6:
                keys += [robot.timed(dialog, "NUM" + digit, digit) for digit in "12"]
        keys += [robot.timed(dialog, "NUM1", "1") for _ in range(10)]  # long preview
        for name, values in (("Tab", tabs), ("key", keys)):
            median, worst = statistics.median(values), max(values)
            check("%s: %s median under %d ms" % (query, name, args.max_median_ms), median < args.max_median_ms,
                  "median %.1f ms, max %.1f ms, n=%d" % (median, worst, len(values)))
            check("%s: every %s under %d ms" % (query, name, args.max_ms), worst < args.max_ms, "max %.1f ms" % worst)
        hst_gui.screenshot(os.path.join(args.out, "filled-%s.png" % query.replace(" ", "-")), args.display)
        focus_window(args.display)
        subprocess.run(["xdotool", "key", "Escape"], env=env, check=False, timeout=30)
        thread.join(10)
        if thread.is_alive():  # the list may have taken the first Esc
            subprocess.run(["xdotool", "key", "Escape"], env=env, check=False, timeout=30)
            thread.join(10)
        check("%s: Esc closes the wizard" % query, not thread.is_alive())
        if thread.is_alive():
            dialog.endExecute()
            thread.join(10)
        close(doc)


def heights(office, args):
    from hst_office import data_files, wizard_nd30
    from com.sun.star.awt import Size
    from com.sun.star.util.MeasureUnit import APPFONT
    doc = office.desktop().loadComponentFromURL("private:factory/swriter", "_blank", 0, ())
    wizard = wizard_nd30.Nd30Wizard(office.ctx, data_files.load_locale("vi"))
    thread = threading.Thread(target=lambda: wizard.run(doc.getCurrentController().getFrame().getContainerWindow()), daemon=True)
    thread.start()
    for _ in range(60):
        time.sleep(0.5)
        if wizard.picker.handler and wizard.d.dialog.getPeer():
            break
    time.sleep(1.5)
    d = wizard.d
    peer = d.dialog.getPeer()
    low = []
    for name in d._single_lines:
        control = d.dialog.getControl(name)
        want, have = control.getPreferredSize().Height, control.getPeer().getPosSize().Height
        if have < want and d.model.getByName(name).Height < d._room_below(name):
            low.append("%s %d<%d px" % (name, have, want))
    check("every one-line field has its preferred height or all the room below it", not low, low or len(d._single_lines))
    model = d.model
    field, rows = model.getByName("type"), model.getByName("typeList")
    check("the type list hangs under the type field", rows.PositionY >= field.PositionY + field.Height,
          (field.PositionY, field.Height, rows.PositionY))
    overlaps = []
    names = [n for n in model.ElementNames if n not in d._overlays and model.getByName(n).EnableVisible]
    for name in d._single_lines:
        a = model.getByName(name)
        for other in names:
            b = model.getByName(other)
            if other != name and (a.PositionX < b.PositionX + b.Width and b.PositionX < a.PositionX + a.Width
                                  and a.PositionY < b.PositionY + b.Height and b.PositionY < a.PositionY + a.Height):
                overlaps.append("%s/%s" % (name, other))
    check("grown fields overlap no other control", not overlaps, overlaps)
    # Type a query in "Loại văn bản" and leave with Tab: the highlighted type is taken, the list closes and the focus
    # and the next typing land in "Cơ quan chủ quản" (an open list used to cover it and the type was silently lost).
    env = dict(os.environ, DISPLAY=args.display)
    focus_window(args.display)
    d.dialog.getControl("type").setFocus()
    time.sleep(0.5)
    subprocess.run(["xdotool", "type", "--delay", "50", "quyet"], env=env, check=False, timeout=30)
    time.sleep(0.8)
    opened = wizard.picker.open
    subprocess.run(["xdotool", "key", "Tab"], env=env, check=False, timeout=30)
    time.sleep(0.8)
    subprocess.run(["xdotool", "type", "--delay", "50", "UBND"], env=env, check=False, timeout=30)
    time.sleep(0.8)
    hst_gui.screenshot(os.path.join(args.out, "type-then-tab.png"), args.display)
    check("a typed query opens the list", opened)
    check("Tab takes the highlighted type and closes the list", wizard.picker.current == "quyet-dinh" and not wizard.picker.open,
          (wizard.picker.current, wizard.picker.open))
    check("after Tab the next typing lands in Cơ quan chủ quản", model.getByName("parentAgency").Text == "UBND",
          repr(model.getByName("parentAgency").Text))
    one = peer.convertSizeToPixel(Size(0, 1), APPFONT).Height
    print("one AppFont unit: %s px; heights: %s" % (one, {n: model.getByName(n).Height for n in d._single_lines}))
    hst_gui.screenshot(os.path.join(args.out, "heights.png"), args.display)
    d.dialog.endExecute()
    thread.join(10)
    close(doc)


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--display", required=True)
    parser.add_argument("--instdir", default=os.path.join(hst_gui.ROOT, "upstream/libreoffice/instdir"))
    parser.add_argument("--out", default=os.path.join(hst_gui.ROOT, "tests/output/nd30-field-switch"))
    parser.add_argument("--port", type=int, default=2195)
    parser.add_argument("--max-median-ms", type=int, default=100)
    parser.add_argument("--max-ms", type=int, default=500)
    parser.add_argument("--skip-heights", action="store_true", help="timing only (an office without this checkout's dialogs.py)")
    args = parser.parse_args()
    args.out = os.path.abspath(args.out)
    os.makedirs(args.out, exist_ok=True)
    hst_gui.setup_uno(args.instdir)
    office = hst_gui.Office(args.instdir, os.path.join(args.out, "office"), args.port, display=args.display).start()
    try:
        time.sleep(5)  # let the start-up dialogs settle (the welcome watcher closes them)
        timing(office, args)
        if not args.skip_heights:
            heights(office, args)
    finally:
        office.stop()
    print("PASS" if all(ROWS) else "FAIL", flush=True)
    return 0 if all(ROWS) else 1


if __name__ == "__main__":
    sys.exit(main())
