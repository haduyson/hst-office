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
  5. Title-bar X closes all tabs, asking to save each modified one; Cancel keeps that tab.
  6. Options off (Office.Common/Misc/DocumentTabs=false): every document is its own window
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


def is_document(name):
    """A document window (not the Start Center, not a tooltip or popup titled "HST Office")."""
    return " — HST Office" in name


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
        return hst_gui.mapped_toplevels(self.office.display, is_document, pid=self.office.pid)

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

    def queries(self):
        """Dialogs of our soffice (the save query), i.e. top-levels that are no document window."""
        return [(w, n) for w, n in hst_gui.toplevels(self.office.display, self.office.pid)
                if not is_doc_window(n) and n.startswith(("Lưu", "Save"))]

    def answer_query(self, dont_save, shot):
        """Wait for a save query, screenshot it, answer "Không lưu" (first button) or Cancel."""
        if not self.wait(lambda: bool(self.queries()), 20):
            return False
        time.sleep(1)
        self.shot(shot)
        wid, _name = self.queries()[0]
        env = dict(os.environ, DISPLAY=self.office.display)
        if dont_save:
            info = subprocess.run(["xwininfo", "-display", self.office.display, "-id", wid],
                                  capture_output=True, text=True).stdout
            width = int(info.split("Width: ")[1].split()[0])
            height = int(info.split("Height: ")[1].split()[0])
            subprocess.run(["xdotool", "mousemove", "--window", wid, str(width // 6), str(height - 18), "click", "1"],
                           env=env, check=False, timeout=10)
            # pointer away from the ribbon (no tooltip window afterwards)
            subprocess.run(["xdotool", "mousemove", "1599", "999"], env=env, check=False, timeout=10)
        else:
            subprocess.run(["xdotool", "windowfocus", wid], env=env, check=False, timeout=10)
            time.sleep(0.5)
            subprocess.run(["xdotool", "key", "Escape"], env=env, check=False, timeout=10)
        self.wait(lambda: wid not in [w for w, _n in self.queries()], 15)
        return True

    def close_window(self):
        """The title-bar X of the shown tab's window (WM_DELETE_WINDOW)."""
        shown = title(self.visible_frames()[0])
        wid = next(w for w, n in hst_gui.toplevels(self.office.display, self.office.pid) if n == shown)
        hst_gui.send_close_request(wid, self.office.display)

    def activate_module(self, module):
        for _ in range(4):
            visible = self.visible_frames()
            if visible and module_of(self.office, visible[0]) == module:
                return True
            self.office.dispatch(visible[0], ".uno:NextDocumentTab")
            self.wait(lambda: len(self.visible_frames()) == 1, 10)
            time.sleep(1)
        return False

    def ribbon_colour(self, shot):
        """Colour of the ribbon frame border (module colour: Writer blue, Calc green, Impress orange)."""
        from PIL import Image
        wid, _n = next((w, n) for w, n in hst_gui.toplevels(self.office.display, self.office.pid) if is_document(n))
        info = subprocess.run(["xwininfo", "-display", self.office.display, "-id", wid], capture_output=True, text=True).stdout
        left = max(int(info.split("Absolute upper-left X:")[1].split()[0]), 0)
        top = max(int(info.split("Absolute upper-left Y:")[1].split()[0]), 0)
        r, g, b = Image.open(shot).convert("RGB").getpixel((left + 3, top + 100))
        return "blue" if b > r and b > g else "green" if g > r and g > b else "orange" if r > b else "?"

    def key(self, keys):
        """Send keys to the visible document window (X focus set explicitly: no window manager)."""
        env = dict(os.environ, DISPLAY=self.office.display)
        for wid, name in hst_gui.toplevels(self.office.display, self.office.pid):
            if is_doc_window(name):
                subprocess.run(["xdotool", "windowfocus", "--sync", wid, "key", "--clearmodifiers", keys],
                               env=env, check=False, timeout=15)
                return True
        return False


def write_odt(path, text):
    """A minimal ODF text document (written directly: saving a hidden document first would add a
    load/close cycle that trips an unrelated GTK3 clipboard/menubar crash under Xvfb)."""
    import zipfile
    from xml.sax.saxutils import escape
    content = ('<?xml version="1.0" encoding="UTF-8"?>'
               '<office:document-content xmlns:office="urn:oasis:names:tc:opendocument:xmlns:office:1.0" '
               'xmlns:text="urn:oasis:names:tc:opendocument:xmlns:text:1.0" office:version="1.3">'
               f'<office:body><office:text><text:p>{escape(text)}</text:p></office:text></office:body>'
               '</office:document-content>')
    manifest = ('<?xml version="1.0" encoding="UTF-8"?>'
                '<manifest:manifest xmlns:manifest="urn:oasis:names:tc:opendocument:xmlns:manifest:1.0" manifest:version="1.3">'
                '<manifest:file-entry manifest:full-path="/" manifest:media-type="application/vnd.oasis.opendocument.text"/>'
                '<manifest:file-entry manifest:full-path="content.xml" manifest:media-type="text/xml"/>'
                '</manifest:manifest>')
    with zipfile.ZipFile(path, "w") as odt:
        odt.writestr(zipfile.ZipInfo("mimetype"), "application/vnd.oasis.opendocument.text")
        odt.writestr("content.xml", content, zipfile.ZIP_DEFLATED)
        odt.writestr("META-INF/manifest.xml", manifest, zipfile.ZIP_DEFLATED)
    return path


def module_of(office, frame):
    module = office.service("com.sun.star.frame.ModuleManager").identify(frame)
    return {"com.sun.star.text.TextDocument": "Writer", "com.sun.star.sheet.SpreadsheetDocument": "Calc",
            "com.sun.star.presentation.PresentationDocument": "Impress"}.get(module, module)


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
        c.wait(lambda: bool(hst_gui.mapped_toplevels(office.display, is_doc_window, pid=office.pid)), 60)
        c.shot("01-start-center.png")

        # 1. The first document replaces the Start Center (target _default reuses its frame).
        w1 = office.load("private:factory/swriter", "_default")
        w1.getText().setString("Văn bản thứ nhất — HST Office")
        c.check("first document replaces Start Center", c.wait(lambda: len(c.frames()) == 1),
                f"frames={len(c.frames())}")

        # A document on disk, opened like File > Open.
        fixture = write_odt(os.path.join(office.workdir, "tai-lieu-mo.odt"), "Tệp mở từ đĩa")
        subprocess.run(["chown", hst_gui.BUILD_USER, fixture], check=False)
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

        # 6. Title-bar X closes the whole group like a browser window: each modified document
        #    asks in turn; "Don't save" on the first, Cancel on the second keeps that tab.
        for frame in c.frames():
            if "Writer" in title(frame):
                frame.getController().getModel().getText().setString("Sửa để hỏi lưu khi đóng cửa sổ")
        c.close_window()
        c.check("window X: first save query", c.answer_query(dont_save=True, shot="07-window-x-first-query.png"))
        c.check("window X: second save query", c.answer_query(dont_save=False, shot="08-window-x-second-query.png"))
        c.check("window X + Cancel: the cancelled tab stays open and shown",
                c.wait(lambda: len(c.frames()) == 1 and len(c.visible_frames()) == 1 and not c.queries(), 20),
                ", ".join(title(f) for f in c.frames()))
        c.shot("09-window-x-cancelled.png")

        # 7. Mixed group in this order: Văn bản / Bảng tính / Trình chiếu. The remaining Writer
        #    tab is the first; new tabs open to the right of the active one.
        office.load("private:factory/scalc", "_blank")
        impress = office.load("private:factory/simpress", "_blank")
        c.wait(lambda: len(c.frames()) == 3 and len(c.visible_frames()) == 1)
        c.check("mixed group: three documents, one window", len(c.mapped()) == 1, repr(c.mapped()))
        c.activate_module("Writer")
        colours = {}
        for index, module in enumerate(("Writer", "Calc", "Impress")):
            if index:  # tab order: one step to the right reaches the next module
                office.dispatch(c.visible_frames()[0], ".uno:NextDocumentTab")
            c.wait(lambda: module_of(office, c.visible_frames()[0]) == module and len(c.mapped()) == 1, 15)
            time.sleep(2)  # ribbon of the shown window painted
            shot = c.shot(f"11-mixed-tab-{index + 1}-{module.lower()}.png")
            visible = c.visible_frames()
            colours[module] = c.ribbon_colour(shot)
            c.check(f"mixed group: {module} tab shows the {module} window and ribbon",
                    len(visible) == 1 and module_of(office, visible[0]) == module and len(c.mapped()) == 1,
                    f"{title(visible[0]) if visible else '-'} ribbon border {colours[module]}")
        c.check("ribbon follows the module (distinct ribbon colours)", len(set(colours.values())) == 3, repr(colours))

        # Impress in a tab: slideshow with F5, end with Esc, the group is intact.
        c.activate_module("Impress")
        # "Trình chiếu từ đầu" (F5 on a desktop; the command directly, keyboard focus under Xvfb is unreliable)
        threading.Thread(target=office.dispatch, args=(c.visible_frames()[0], ".uno:Presentation"), daemon=True).start()
        def show_windows():
            return [(w, n) for w, n in hst_gui.toplevels(office.display, office.pid) if not is_doc_window(n)]
        show = c.wait(lambda: bool(show_windows()), 20)
        time.sleep(2)
        c.shot("12-slideshow-running.png")
        running = [n for _w, n in show_windows()]
        c.check("Impress tab: slideshow starts (Trình chiếu từ đầu)", show and impress.getPresentation().isRunning(),
                repr(running))
        # Presenter console: needs a second display; with one screen only the show window opens.
        c.check("presenter console not opened on a single display",
                len(running) == 1 and running[0].startswith(("Trình bày:", "Presenting:")), repr(running))
        env = dict(os.environ, DISPLAY=office.display)
        for wid, _n in show_windows():
            subprocess.run(["xdotool", "windowfocus", wid], env=env, check=False, timeout=10)
        time.sleep(0.5)
        subprocess.run(["xdotool", "key", "Escape"], env=env, check=False, timeout=10)
        c.check("Esc ends the slideshow", c.wait(lambda: not impress.getPresentation().isRunning(), 20))
        c.check("after the slideshow: same group, Impress shown, other tabs intact",
                c.wait(lambda: len(c.frames()) == 3 and len(c.visible_frames()) == 1
                       and module_of(office, c.visible_frames()[0]) == "Impress" and len(c.mapped()) == 1, 20),
                f"{[title(f) for f in c.frames()]} mapped={c.mapped()}")
        c.shot("13-after-slideshow.png")

        # Title-bar X with all three modified: three save queries ("Don't save" each), all closed.
        for frame in c.frames():
            model = frame.getController().getModel()
            if hasattr(model, "getText"):
                model.getText().setString("Sửa")
            elif hasattr(model, "getSheets"):
                model.getSheets().getByIndex(0).getCellByPosition(0, 0).setString("Sửa")
            else:
                model.setModified(True)
        c.close_window()
        answered = [c.answer_query(dont_save=True, shot=f"14-window-x-query-{i + 1}.png") for i in range(3)]
        c.check("window X with three modified tabs: three save queries", all(answered), repr(answered))
        c.check("window X: every tab closed after \"Don't save\"", c.wait(lambda: len(c.frames()) == 0, 20),
                f"frames={len(c.frames())}")

        # 8. Option off: classic windows.
        office.set_config("/org.openoffice.Office.Common/Misc", "DocumentTabs", False)
        office.load("private:factory/swriter", "_blank")
        office.load("private:factory/scalc", "_blank")
        c.check("option off: every document opens its own window",
                c.wait(lambda: len(c.visible_frames()) == len(c.frames()) == 2 and len(c.mapped()) == 2),
                repr(c.mapped()))
        c.shot("10-option-off-classic-windows.png")
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
