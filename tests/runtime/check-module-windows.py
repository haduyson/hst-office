# SPDX-License-Identifier: AGPL-3.0-only
"""Check the window rules of HST Office document tabs on a real GUI build (fresh profile, existing X display).

Usage: python3 tests/runtime/check-module-windows.py [--instdir upstream/libreoffice/instdir]
           [--out tests/output/module-windows] [--display :97]

A second soffice on the same profile stands for the launchers and the file manager (it hands its request to the
running office over the pipe, exactly like HST Writer, HST Sheets, a .desktop file or a double-click). Asserts:
  1. HST Office (Start Center): new documents of every module are tabs of its one window.
  2. "--writer" and "--calc" (HST Writer/HST Sheets launchers) each open a window of their own.
  3. In the HST Writer window a new text document is a tab; a new spreadsheet opens another window.
  4. A file opened from outside opens a window of its own.
  5. .uno:NextDocumentTab cycles within its window only; .uno:DetachDocumentTab moves the tab into a new window.
  6. A second "soffice" without arguments (HST Office launcher) shows the HST Office window, no new window.
  7. WM_CLASS: tabs of the HST Office window carry HST Office's class, module windows their module's.
Screenshots and evidence.json go to --out. Exit 1 when any check fails.
"""
import argparse
import json
import os
import subprocess
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import hst_gui  # noqa: E402

ROOT = hst_gui.ROOT
PORT = 21993  # deterministic per check (see hst_gui)


class Checker:
    def __init__(self, office, out):
        self.office, self.out, self.results = office, out, []

    def check(self, name, ok, detail=""):
        self.results.append({"check": name, "status": "PASS" if ok else "FAIL", "detail": detail})
        print(f"{'PASS' if ok else 'FAIL'}  {name}  {detail}")
        return ok

    def shot(self, name):
        time.sleep(1.5)
        return hst_gui.screenshot(os.path.join(self.out, name), self.office.display)

    def frames(self):
        access = self.office.desktop().getFrames()
        return [access.getByIndex(i) for i in range(access.getCount())]

    def windows(self):
        """Mapped top-levels of this office that are documents or the Start Center (one per tab window)."""
        return [(w, n) for w, n in hst_gui.toplevels(self.office.display, self.office.pid)
                if " — HST " in n or n.startswith("HST Office")]

    def wait(self, predicate, timeout=30):
        deadline = time.time() + timeout
        while time.time() < deadline:
            try:
                if predicate():
                    return True
            except Exception:  # noqa: BLE001 - frames come and go while windows change
                pass
            time.sleep(0.5)
        return False

    def second_office(self, *args):
        """soffice on the same profile: hands its arguments to the running office and exits."""
        profile = os.path.join(self.office.workdir, "profile")
        subprocess.run(hst_gui._as_user_prefix() + [os.path.join(self.office.program, "soffice"),
                       f"-env:UserInstallation=file://{profile}", *args], env=self.office._env(), timeout=120,
                       check=False)

    def dispatch(self, frame, url, target):
        helper = self.office.service("com.sun.star.frame.DispatchHelper")
        frame.activate()
        return helper.executeDispatch(frame, url, target, 0, ())

    def wm_class(self, wid):
        return subprocess.run(["xprop", "-display", self.office.display, "-id", wid, "WM_CLASS"],
                              capture_output=True, text=True).stdout


def module_of(office, frame):
    try:
        return office.service("com.sun.star.frame.ModuleManager").identify(frame).split(".")[-1]
    except Exception:  # noqa: BLE001 - the Start Center or a frame being closed
        return "?"


def visible(c):
    return [f for f in c.frames() if f.getContainerWindow().isVisible()]


def run(args):
    hst_gui.setup_uno(args.instdir)
    office = hst_gui.Office(args.instdir, args.out, PORT, display=args.display, nodefault=False)
    office.start()
    c = Checker(office, args.out)
    try:
        c.wait(lambda: len(c.windows()) == 1, 60)
        start = c.frames()[0]
        # 1. HST Office: the Start Center turns into a document, "+" (from that window) adds tabs of any module.
        c.dispatch(start, "private:factory/swriter", "_default")
        c.wait(lambda: module_of(office, c.frames()[0]) == "TextDocument")
        office_writer = c.frames()[0]
        c.dispatch(office_writer, "private:factory/scalc", "_blank")
        c.check("HST Office window: Writer and Sheets are tabs of one window",
                c.wait(lambda: len(c.frames()) == 2 and len(c.windows()) == 1), repr(c.windows()))
        c.shot("01-office-window-two-tabs.png")

        # 2. Launchers: own windows.
        c.second_office("--writer")
        c.check("HST Writer launcher: a window of its own", c.wait(lambda: len(c.frames()) == 3 and len(c.windows()) == 2),
                repr(c.windows()))
        module_writer = next(f for f in c.frames() if f not in (start, office_writer) and module_of(office, f) == "TextDocument")
        c.second_office("--calc")
        c.check("HST Sheets launcher: another window", c.wait(lambda: len(c.frames()) == 4 and len(c.windows()) == 3),
                repr(c.windows()))
        c.shot("02-launcher-windows.png")

        # 3. Inside the HST Writer window.
        c.dispatch(module_writer, "private:factory/swriter", "_blank")
        c.check("HST Writer window: a new text document is a tab",
                c.wait(lambda: len(c.frames()) == 5) and c.wait(lambda: len(c.windows()) == 3), repr(c.windows()))
        writer_tabs = [f for f in c.frames() if module_of(office, f) == "TextDocument" and f != office_writer]
        c.dispatch(writer_tabs[-1], "private:factory/scalc", "_blank")
        c.check("HST Writer window: a new spreadsheet opens a window of HST Sheets",
                c.wait(lambda: len(c.frames()) == 6 and len(c.windows()) == 4), repr(c.windows()))
        c.shot("03-writer-window-rules.png")

        # 4. A file from outside (file manager double-click).
        fixture = os.path.join(office.workdir, "tep-ngoai.csv")
        with open(fixture, "w", encoding="utf-8") as handle:
            handle.write("Họ tên,Điểm\nAn,9\n")
        subprocess.run(["chown", hst_gui.BUILD_USER, fixture], check=False)
        c.second_office("--calc", "--infilter=Text - txt - csv (StarCalc):44,34,76", fixture)
        c.check("file from outside: a window of its own", c.wait(lambda: len(c.frames()) == 7 and len(c.windows()) == 5),
                repr(c.windows()))

        # 5. Tab commands act on their window.
        before = {w for w, _n in c.windows()}
        shown = [f for f in writer_tabs if f.getContainerWindow().isVisible()]
        office.dispatch(shown[0], ".uno:NextDocumentTab")
        c.check("NextDocumentTab: the other tab of the HST Writer window is shown, windows unchanged",
                c.wait(lambda: [f for f in writer_tabs if f.getContainerWindow().isVisible()] not in ([], shown)
                       and len(c.windows()) == 5), repr(c.windows()))
        office_tabs = [f for f in (office_writer,) + tuple(f for f in c.frames() if f not in writer_tabs
                       and module_of(office, f) == "SpreadsheetDocument")][:2]
        shown_office = next(f for f in office_tabs if f.getContainerWindow().isVisible())
        office.dispatch(shown_office, ".uno:DetachDocumentTab")
        c.check("DetachDocumentTab: the tab moves into a new window",
                c.wait(lambda: len(c.windows()) == 6 and all(f.getContainerWindow().isVisible() for f in office_tabs)),
                repr(c.windows()))
        c.shot("04-detached.png")

        # 6. HST Office launcher again: no new window.
        c.second_office()
        time.sleep(4)
        c.check("HST Office launcher again: no new window", len(c.windows()) == 6, repr(c.windows()))

        # 7. Taskbar identity.
        classes = {n: c.wm_class(w) for w, n in c.windows() if w not in before or True}
        module_window = next(w for w, _n in c.windows()
                             if module_writer.getContainerWindow().isVisible() and module_writer.Title in _n)
        c.check("WM_CLASS: HST Writer window is a Writer window", "-writer" in c.wm_class(module_window),
                c.wm_class(module_window))
        office_window = next((w for w, n in c.windows() if office_writer.Title in n), None)
        c.check("WM_CLASS: a tab of the HST Office window belongs to HST Office",
                office_window is not None and "startcenter" in c.wm_class(office_window), repr(classes))
    finally:
        try:
            for doc in office.desktop().getComponents():
                doc.setModified(False)
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
    parser.add_argument("--out", default=os.path.join(ROOT, "tests/output/module-windows"))
    parser.add_argument("--display", default=":97")
    args = parser.parse_args()
    args.out = os.path.abspath(args.out)
    return run(args)


if __name__ == "__main__":
    sys.exit(main())
