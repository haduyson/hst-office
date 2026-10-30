# SPDX-License-Identifier: AGPL-3.0-only
"""Check HST Office document tabs on a real GUI build (fresh profile, existing X display).

Usage: python3 tests/runtime/check-document-tabs.py [--instdir upstream/libreoffice/instdir]
           [--out tests/output/document-tabs] [--shots tests/output/screenshots-tabs] [--display :97]

Drives soffice over UNO plus X tools (xwininfo/xdotool/import) and asserts:
  1. Start Center, then the first document replaces it (one window).
  2. Two Writer documents and one Calc sheet (new and opened from disk) form one tab group:
     exactly one mapped document window (one taskbar entry); the others are parked.
  3. Switching: .uno:PrevDocumentTab and the Ctrl+Alt+. / Ctrl+Alt+, keys show another tab.
  4. Closing a modified tab asks to save (dialog shown, cancelled: still open); closing an
     unmodified tab closes only that frame and the neighbour is shown (application alive).
  5. Options off (Office.Common/Misc/DocumentTabs=false): every document is its own window
     again, and a new document opens in a new window.
Screenshots of each step go to --shots. Exit 1 when any check fails.
"""
import argparse
import json
import os
import subprocess
import sys
import threading
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import hst_gui  # noqa: E402

ROOT = hst_gui.ROOT
PORT = 21991  # deterministic per check (see hst_gui)


def is_doc_window(name):
    return " — HST Office" in name or name.startswith("HST Office")


class Checker:
    def __init__(self, office, shots):
        self.office = office
        self.shots = shots
        self.results = []

    def check(self, name, ok, detail=""):
        self.results.append({"check": name, "status": "PASS" if ok else "FAIL", "detail": detail})
        print(f"{'PASS' if ok else 'FAIL'}  {name}  {detail}")
        return ok

    def shot(self, name):
        time.sleep(1.5)
        return self.office.screenshot(os.path.join(self.shots, name))

    def frames(self):
        access = self.office.desktop().getFrames()
        return [access.getByIndex(i) for i in range(access.getCount())]

    def visible_frames(self):
        return [f for f in self.frames() if f.getContainerWindow().isVisible()]

    def mapped(self):
        return hst_gui.mapped_toplevels(self.office.display, is_doc_window, pid=self.office.pid)

    def wait(self, predicate, timeout=20):
        deadline = time.time() + timeout
        while time.time() < deadline:
            try:
                if predicate():
                    return True
            except Exception:  # noqa: BLE001 - UNO objects can be in flux while windows change
                pass
            time.sleep(0.5)
        return False

    def key(self, keys):
        """Send keys to the visible document window (X focus set explicitly: no window manager)."""
        env = dict(os.environ, DISPLAY=self.office.display)
        for wid, name in hst_gui.toplevels(self.office.display, self.office.pid):
            if is_doc_window(name):
                subprocess.run(["xdotool", "windowfocus", "--sync", wid, "key", "--clearmodifiers", keys],
                               env=env, check=False, timeout=15)
                return True
        return False


def title(frame):
    try:
        return frame.Title
    except Exception:  # noqa: BLE001
        return "?"


def run(args):
    hst_gui.setup_uno(args.instdir)
    os.makedirs(args.shots, exist_ok=True)
    # Without --nodefault the Start Center is the first window.
    office = hst_gui.Office(args.instdir, args.out, PORT, display=args.display, nodefault=False)
    office.start()
    c = Checker(office, args.shots)
    try:
        c.wait(lambda: len(c.mapped()) == 1, 60)
        c.shot("01-start-center.png")

        # 1. The first document replaces the Start Center (target _default reuses its frame).
        w1 = office.load("private:factory/swriter", "_default")
        w1.getText().setString("Văn bản thứ nhất — HST Office")
        c.check("first document replaces Start Center", c.wait(lambda: len(c.frames()) == 1),
                f"frames={len(c.frames())}")

        # A document on disk, opened like File > Open.
        fixture = os.path.join(office.workdir, "tai-lieu-mo.odt")
        tmp = office.load("private:factory/swriter", "_blank", hidden=True)
        tmp.getText().setString("Tệp mở từ đĩa")
        tmp.storeToURL("file://" + fixture, ())
        tmp.close(True)

        w2 = office.load("file://" + fixture, "_blank")
        calc = office.load("private:factory/scalc", "_blank")
        calc.getSheets().getByIndex(0).getCellByPosition(0, 0).setString("Bảng tính")
        calc.setModified(False)
        w1.setModified(False)
        c.wait(lambda: len(c.visible_frames()) == 1)
        frames = c.frames()
        c.check("three documents open", len(frames) == 3, ", ".join(title(f) for f in frames))
        c.check("one visible window (others parked)", len(c.visible_frames()) == 1,
                ", ".join(title(f) for f in c.visible_frames()))
        mapped = c.mapped()
        c.check("one taskbar entry (one mapped top-level)", len(mapped) == 1, repr(mapped))
        c.check("new/opened document is the shown tab", "Calc" in (mapped or [""])[0] or "Bảng" in (mapped or [""])[0]
                or "HST Office Calc" in " ".join(mapped), repr(mapped))
        c.shot("02-three-tabs-calc.png")

        # 2. Switching by command and by keyboard.
        visible = c.visible_frames()[0]
        office.dispatch(visible, ".uno:PrevDocumentTab")
        c.check("PrevDocumentTab shows another tab",
                c.wait(lambda: len(c.visible_frames()) == 1 and title(c.visible_frames()[0]) != title(visible)),
                title(c.visible_frames()[0]))
        c.shot("03-switched-to-writer.png")
        before = title(c.visible_frames()[0])
        c.key("ctrl+alt+period")
        c.check("Ctrl+Alt+. switches to the next tab",
                c.wait(lambda: len(c.visible_frames()) == 1 and title(c.visible_frames()[0]) != before),
                f"{before} -> {title(c.visible_frames()[0])}")
        c.check("still one mapped window after switching", len(c.mapped()) == 1, repr(c.mapped()))

        # 3. Close a modified tab: the save query appears; cancel keeps it open.
        target = None
        for frame in c.frames():
            if frame.getController() and frame.getController().getModel() == w2:
                target = frame
        w2.getText().setString("Đã sửa — cần hỏi lưu")
        # DispatchHelper waits for the close to finish, i.e. for the save query: use a thread.
        closer = threading.Thread(target=office.dispatch, args=(target, ".uno:CloseWin"), daemon=True)
        closer.start()
        asked = c.wait(lambda: len(hst_gui.mapped_toplevels(office.display, pid=office.pid)) >= 2, 20)
        names = hst_gui.mapped_toplevels(office.display, pid=office.pid)
        c.check("closing a modified tab asks to save", asked, repr(names))
        c.shot("04-close-modified-asks-save.png")
        env = dict(os.environ, DISPLAY=office.display)
        for wid, name in hst_gui.toplevels(office.display, office.pid):
            if not is_doc_window(name) or name == "HST Office":  # the query box
                subprocess.run(["xdotool", "windowfocus", wid], env=env, check=False, timeout=10)
                time.sleep(0.5)
                subprocess.run(["xdotool", "key", "Escape"], env=env, check=False, timeout=10)
        c.wait(lambda: len(hst_gui.mapped_toplevels(office.display, pid=office.pid)) == 1, 15)
        closer.join(20)
        c.check("cancel keeps the document open", len(c.frames()) == 3, f"frames={len(c.frames())}")

        # 4. Close an unmodified tab (the shown one): only that frame closes, a neighbour shows.
        w2.setModified(False)
        shown = c.visible_frames()[0]
        shown_title = title(shown)
        office.dispatch(shown, ".uno:CloseWin")
        c.check("closing a tab closes only that document",
                c.wait(lambda: len(c.frames()) == 2), f"frames={len(c.frames())}")
        c.check("a neighbour tab is shown after closing",
                c.wait(lambda: len(c.visible_frames()) == 1 and title(c.visible_frames()[0]) != shown_title),
                ", ".join(title(f) for f in c.visible_frames()))
        c.check("application alive, one mapped window", len(c.mapped()) == 1, repr(c.mapped()))
        c.shot("05-after-close.png")

        # 5. New tab through the same dispatch the "+" button uses.
        helper = office.service("com.sun.star.frame.DispatchHelper")
        helper.executeDispatch(c.visible_frames()[0], "private:factory/swriter", "_blank", 0, ())
        c.check("new document from a tab lands in a tab",
                c.wait(lambda: len(c.frames()) == 3 and len(c.visible_frames()) == 1),
                f"frames={len(c.frames())} visible={len(c.visible_frames())}")
        c.shot("06-new-tab.png")

        # 6. Option off: classic windows.
        office.set_config("/org.openoffice.Office.Common/Misc", "DocumentTabs", False)
        c.check("option off: every document is a window again",
                c.wait(lambda: len(c.visible_frames()) == len(c.frames()) == 3), f"visible={len(c.visible_frames())}")
        office.load("private:factory/swriter", "_blank")
        c.check("option off: new document opens a new window",
                c.wait(lambda: len(c.mapped()) == 4), repr(c.mapped()))
        c.shot("07-option-off-classic-windows.png")
    finally:
        try:
            for doc in office.desktop().getComponents():
                try:
                    doc.setModified(False)
                except Exception:  # noqa: BLE001
                    pass
        except Exception:  # noqa: BLE001
            pass
        office.stop()
    failed = sum(r["status"] == "FAIL" for r in c.results)
    with open(os.path.join(args.out, "evidence.json"), "w", encoding="utf-8") as handle:
        json.dump({"failed": failed, "checks": c.results}, handle, indent=2, ensure_ascii=False)
    return 1 if failed else 0


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--instdir", default=os.path.join(ROOT, "upstream/libreoffice/instdir"))
    parser.add_argument("--out", default=os.path.join(ROOT, "tests/output/document-tabs"))
    parser.add_argument("--shots", default=os.path.join(ROOT, "tests/output/screenshots-tabs"))
    parser.add_argument("--display", default=":97")
    args = parser.parse_args()
    args.out = os.path.abspath(args.out)
    return run(args)


if __name__ == "__main__":
    sys.exit(main())
