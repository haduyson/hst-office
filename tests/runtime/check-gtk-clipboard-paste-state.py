# SPDX-License-Identifier: AGPL-3.0-only
"""Paste and Paste Special follow the system clipboard when asked over UNO (Linux, gtk3, GUI build, X display).

Off the main thread (a UNO client) the gtk3 clipboard answers its targets from what the main thread last read
(hst-gtk-clipboard-main-thread.patch), refreshed at every owner change. This checks that the cache never lags:
in Writer and Sheets, after another application on the display copies a text (x11_clipboard_owner.py), after it
goes away (empty clipboard) and after a copy inside HST Office, the Paste and Paste Special states asked over
UNO are right at once and still right after a few seconds, and the paste puts the copied text in the document.
Usage: python3 tests/runtime/check-gtk-clipboard-paste-state.py [--instdir upstream/libreoffice/instdir]
[--out tests/output/gtk-clipboard-paste-state] [--display :97] [--settle 0.3]. Exit 1 on any failure.
"""
import argparse
import os
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import hst_gui  # noqa: E402

PORT = 22961  # deterministic per check (see hst_gui)


def make_status_listener():
    import unohelper
    from com.sun.star.frame import XStatusListener

    class Listener(unohelper.Base, XStatusListener):
        state = None

        def statusChanged(self, event):  # noqa: N802 - UNO interface
            self.state = event.IsEnabled

        def disposing(self, _event):
            pass
    return Listener


def enabled(office, frame, command):
    """The state of `command` in `frame`, as a toolbar asking now would get it."""
    from com.sun.star.util import URL
    url = URL()
    url.Complete = command
    _ok, url = office.service("com.sun.star.util.URLTransformer").parseStrict(url)
    dispatch = frame.queryDispatch(url, "", 0)
    if not dispatch:
        return False
    listener = make_status_listener()()
    dispatch.addStatusListener(listener, url)
    dispatch.removeStatusListener(listener, url)
    return bool(listener.state)


class Clipboard:
    """Another application owning the clipboard of the display"""

    def __init__(self, display):
        self.display, self.proc = display, None

    def copy(self, text):
        self.drop()
        self.proc = subprocess.Popen(["/usr/bin/python3", os.path.join(HERE, "x11_clipboard_owner.py"), self.display,
                                      text], stdout=subprocess.PIPE, text=True,
                                     env={k: v for k, v in os.environ.items() if not k.startswith("PYTHON")})
        if self.proc.stdout.readline().strip() != "owned":
            raise RuntimeError("the clipboard owner did not start")

    def drop(self):
        if self.proc:
            self.proc.terminate()
            self.proc.wait(10)
            self.proc = None


def judge(office, frame, want, settle, label, results):
    """Paste and Paste Special at once and after `settle` and 3 s, against `want`"""
    for delay in (0, settle, 3.0):
        time.sleep(delay)
        got = {cmd: enabled(office, frame, cmd) for cmd in (".uno:Paste", ".uno:PasteSpecial")}
        ok = all(value == want for value in got.values())
        results.append((ok, "%s +%.1fs: paste %s, paste special %s (want %s)" % (
            label, delay, got[".uno:Paste"], got[".uno:PasteSpecial"], want)))


def writer_case(office, clip, settle, results):
    doc = office.load("private:factory/swriter")
    frame = doc.CurrentController.Frame
    text = doc.Text
    clip.copy("HSTCLIP-EXT-W")
    judge(office, frame, True, settle, "writer: other app copied", results)
    office.dispatch(frame, ".uno:Paste")
    results.append(("HSTCLIP-EXT-W" in text.String, "writer: pasted other app's text: %r" % text.String[:60]))
    clip.drop()
    judge(office, frame, False, settle, "writer: clipboard emptied", results)
    text.setString("HSTCLIP-INT-W")
    doc.CurrentController.select(text)
    office.dispatch(frame, ".uno:Copy")
    judge(office, frame, True, settle, "writer: copied in HST", results)
    doc.CurrentController.getViewCursor().gotoEnd(False)
    office.dispatch(frame, ".uno:Paste")
    results.append((text.String.count("HSTCLIP-INT-W") == 2, "writer: pasted own copy: %r" % text.String[:60]))
    clip.copy("HSTCLIP-EXT-W2")
    judge(office, frame, True, settle, "writer: other app copied after HST", results)
    doc.CurrentController.getViewCursor().gotoEnd(False)
    office.dispatch(frame, ".uno:Paste")
    results.append(("HSTCLIP-EXT-W2" in text.String, "writer: pasted other app's second text"))
    doc.close(True)


def calc_case(office, clip, settle, results):
    doc = office.load("private:factory/scalc")
    frame = doc.CurrentController.Frame
    sheet = doc.Sheets.getByIndex(0)

    def go(cell):
        doc.CurrentController.select(sheet.getCellRangeByName(cell))
    clip.copy("HSTCLIP-EXT-C")
    judge(office, frame, True, settle, "sheets: other app copied", results)
    go("A1")
    office.dispatch(frame, ".uno:Paste")
    results.append((sheet.getCellRangeByName("A1").String == "HSTCLIP-EXT-C",
                    "sheets: pasted other app's text: %r" % sheet.getCellRangeByName("A1").String))
    clip.drop()
    judge(office, frame, False, settle, "sheets: clipboard emptied", results)
    sheet.getCellRangeByName("B1").String = "HSTCLIP-INT-C"
    go("B1")
    office.dispatch(frame, ".uno:Copy")
    judge(office, frame, True, settle, "sheets: copied in HST", results)
    go("C1")
    office.dispatch(frame, ".uno:Paste")
    results.append((sheet.getCellRangeByName("C1").String == "HSTCLIP-INT-C",
                    "sheets: pasted own copy: %r" % sheet.getCellRangeByName("C1").String))
    clip.copy("HSTCLIP-EXT-C2")
    judge(office, frame, True, settle, "sheets: other app copied after HST", results)
    go("D1")
    office.dispatch(frame, ".uno:Paste")
    results.append((sheet.getCellRangeByName("D1").String == "HSTCLIP-EXT-C2", "sheets: pasted other app's second text"))
    doc.close(True)


def main():
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--instdir", default=os.path.join(hst_gui.ROOT, "upstream/libreoffice/instdir"))
    parser.add_argument("--out", default=os.path.join(hst_gui.ROOT, "tests/output/gtk-clipboard-paste-state"))
    parser.add_argument("--display", default=":97")
    parser.add_argument("--settle", type=float, default=0.3)
    args = parser.parse_args()
    hst_gui.setup_uno(args.instdir)
    os.makedirs(args.out, exist_ok=True)
    office = hst_gui.Office(args.instdir, args.out, PORT, display=args.display, nodefault=True)
    clip = Clipboard(args.display)
    results = []
    office.start()
    try:
        writer_case(office, clip, args.settle, results)
        calc_case(office, clip, args.settle, results)
    finally:
        clip.drop()
        office.stop()
    for ok, line in results:
        print("%s  %s" % ("PASS" if ok else "FAIL", line))
    failed = sum(not ok for ok, _ in results)
    print("%d checks, %d failed" % (len(results), failed))
    return 1 if failed or not results else 0


if __name__ == "__main__":
    raise SystemExit(main())
