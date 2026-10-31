# SPDX-License-Identifier: AGPL-3.0-only
"""Check the standard keyboard shortcuts on a real HST Office build (GTK3, fresh profile).

Usage: python3 tests/runtime/check-shortcuts.py [--instdir upstream/libreoffice/instdir]
       [--out tests/output/shortcuts] [--display :97] [--lang vi|en|both]

Keys are sent with xdotool to this instance's own document window (X focus set explicitly:
the test display has no window manager) and the effect is read back over UNO:

  Writer  Ctrl+A select all, Ctrl+B/I/U bold/italic/underline, Ctrl+Z/Ctrl+Y undo/redo,
          Ctrl+X/Ctrl+V cut/paste, Ctrl+S save (no dialog for a stored .odt),
          Ctrl+F find toolbar, Ctrl+H/Ctrl+Shift+S/Ctrl+O/Ctrl+P/F7 open a dialog (Escape closes),
          F12 numbering, F1 opens the offline guide (logged by an xdg-open stub),
          Ctrl+N new document tab, Ctrl+Alt+, / Ctrl+Alt+. previous/next tab, Ctrl+W close tab
  Calc    Ctrl+B bold cell, Ctrl+1 Format Cells dialog, Ctrl+Z undo
  Impress F5 starts the slide show, Escape ends it
  all     Ctrl+Q quits (unmodified documents, no prompt)

Alt+F4 and the title-bar X are window-manager actions and are not covered here
(check-document-tabs.py sends the close request directly). Exit 1 when any check fails.
"""
import argparse
import os
import subprocess
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import hst_gui  # noqa: E402

ROOT = hst_gui.ROOT
PORT = 22950
RESULTS = []


def check(name, ok, detail=""):
    RESULTS.append((name, bool(ok)))
    print(f"{'PASS' if ok else 'FAIL'} {name}" + (f"  ({detail})" if detail and not ok else ""), flush=True)
    return ok


def wait(cond, timeout=10.0, step=0.3):
    end = time.time() + timeout
    while time.time() < end:
        try:
            if cond():
                return True
        except Exception:  # noqa: BLE001 - UNO objects may be in flux while a key takes effect
            pass
        time.sleep(step)
    return False


class Keys:
    """Key input and window bookkeeping for one Office instance."""

    def __init__(self, office):
        self.office = office
        self.env = dict(os.environ, DISPLAY=office.display)

    def windows(self):
        return hst_gui.toplevels(self.office.display, self.office.pid)

    def doc_window(self):
        for wid, name in self.windows():
            if name.endswith(("HST Writer", "HST Sheets", "HST Slides")):
                return wid
        return None

    def send(self, keys, wid=None):
        wid = wid or self.doc_window()
        if wid is None:
            return False
        subprocess.run(["xdotool", "windowfocus", "--sync", wid, "key", "--clearmodifiers", keys],
                       env=self.env, check=False, timeout=15)
        time.sleep(0.6)
        return True

    def dialog_after(self, keys, timeout=12):
        """Press keys; return the name of a new top-level window of this instance (or None)."""
        before = {w for w, _ in self.windows()}
        self.send(keys)
        found = []
        wait(lambda: found.extend((w, n) for w, n in self.windows() if w not in before) or found, timeout)
        return found[0] if found else None

    def close_dialog(self, wid):
        subprocess.run(["xdotool", "windowfocus", "--sync", wid, "key", "Escape"], env=self.env, check=False, timeout=15)
        if not wait(lambda: wid not in {w for w, _ in self.windows()}, 8):
            hst_gui.send_close_request(wid, self.office.display)
            return wait(lambda: wid not in {w for w, _ in self.windows()}, 8)
        return True


def xdg_stub(work):
    """A logging xdg-open first on PATH: F1 hands the guide URL to it instead of a browser."""
    bindir = os.path.join(work, "bin")
    os.makedirs(bindir, exist_ok=True)
    log = os.path.join(work, "xdg-open.log")
    open(log, "w").close()
    os.chmod(log, 0o666)
    stub = os.path.join(bindir, "xdg-open")
    with open(stub, "w", encoding="utf-8") as handle:
        handle.write(f'#!/bin/sh\necho "$@" >> "{log}"\n')
    os.chmod(stub, 0o755)
    return bindir, log


def writer_checks(office, keys, work, tag):
    from com.sun.star.beans import PropertyValue
    doc = office.load("private:factory/swriter")
    frame = doc.getCurrentController().getFrame()
    text = doc.getText()
    text.setString("Xin chào HST Office")
    wait(lambda: keys.doc_window() is not None, 20)
    office.raise_windows()

    keys.send("ctrl+a")
    sel = lambda: doc.getCurrentController().getSelection().getByIndex(0)  # noqa: E731
    check(f"{tag} Writer Ctrl+A selects all", wait(lambda: sel().getString() == "Xin chào HST Office", 5),
          repr(sel().getString()))
    keys.send("ctrl+b")
    check(f"{tag} Writer Ctrl+B bold", wait(lambda: sel().CharWeight >= 150, 5), str(sel().CharWeight))
    keys.send("ctrl+i")
    check(f"{tag} Writer Ctrl+I italic", wait(lambda: sel().CharPosture.value != "NONE", 5), str(sel().CharPosture))
    keys.send("ctrl+u")
    check(f"{tag} Writer Ctrl+U underline", wait(lambda: sel().CharUnderline == 1, 5), str(sel().CharUnderline))
    keys.send("ctrl+z")
    check(f"{tag} Writer Ctrl+Z undo", wait(lambda: sel().CharUnderline == 0, 5), str(sel().CharUnderline))
    keys.send("ctrl+y")
    check(f"{tag} Writer Ctrl+Y redo", wait(lambda: sel().CharUnderline == 1, 5), str(sel().CharUnderline))
    if tag == "vi":
        keys.send("ctrl+a")
        keys.send("ctrl+x")
        check(f"{tag} Writer Ctrl+X cut", wait(lambda: text.getString() == "", 5), repr(text.getString()))
        keys.send("ctrl+v")
        check(f"{tag} Writer Ctrl+V paste", wait(lambda: text.getString() == "Xin chào HST Office", 8),
              repr(text.getString()))
        keys.send("F12")
        para = lambda: text.createEnumeration().nextElement()  # noqa: E731
        check(f"{tag} Writer F12 numbering on", wait(lambda: bool(para().NumberingRules) and para().NumberingIsNumber, 5))
        keys.send("ctrl+z")

    # Ctrl+S on a stored ODF document saves in place without any dialog.
    url = "file://" + os.path.join(work, f"shortcut-{tag}.odt")
    arg = PropertyValue()
    arg.Name, arg.Value = "FilterName", "writer8"
    doc.storeAsURL(url, (arg,))
    text.getEnd().setString(" — sửa")
    check(f"{tag} Writer document modified before Ctrl+S", doc.isModified())
    before = {w for w, _ in keys.windows()}
    keys.send("ctrl+s")
    saved = wait(lambda: not doc.isModified(), 10)
    extra = [n for w, n in keys.windows() if w not in before]
    check(f"{tag} Writer Ctrl+S saves without a dialog", saved and not extra, f"modified={doc.isModified()} new={extra}")

    keys.send("ctrl+f")
    layout = frame.LayoutManager
    check(f"{tag} Writer Ctrl+F shows the find toolbar",
          wait(lambda: layout.isElementVisible("private:resource/toolbar/findbar"), 5))
    keys.send("Escape")

    dialogs = [("ctrl+h", "Find & Replace"), ("ctrl+shift+s", "Save As"), ("ctrl+o", "Open"), ("ctrl+p", "Print")]
    if tag == "vi":
        dialogs.append(("F7", "Spelling"))
    for combo, what in dialogs:
        found = keys.dialog_after(combo)
        check(f"{tag} Writer {combo} opens {what}", found is not None)
        if found:
            print(f"      dialog title: {found[1]!r}")
            check(f"{tag} Writer {what} closes with Escape", keys.close_dialog(found[0]))
        office.raise_windows()
    return doc


def tab_checks(office, keys, doc, tag):
    desktop = office.desktop()
    count = lambda: desktop.getFrames().getCount()  # noqa: E731
    first = doc.getCurrentController().getFrame().getTitle()
    n = count()
    keys.send("ctrl+n")
    check(f"{tag} Ctrl+N opens a new document", wait(lambda: count() == n + 1, 15), f"{n} -> {count()}")
    time.sleep(2)
    current = lambda: desktop.getCurrentFrame().getTitle()  # noqa: E731
    new_title = current()
    keys.send("ctrl+alt+comma")
    check(f"{tag} Ctrl+Alt+, switches to the previous tab", wait(lambda: current() == first, 8), current())
    keys.send("ctrl+alt+period")
    check(f"{tag} Ctrl+Alt+. switches to the next tab", wait(lambda: current() == new_title, 8), current())
    keys.send("ctrl+w")
    check(f"{tag} Ctrl+W closes only the current tab", wait(lambda: count() == n, 10) and count() >= 1, str(count()))


def f1_check(keys, log, tag):
    keys.send("F1")
    ok = wait(lambda: "hst-vietnamese-tools/help/index.html" in open(log, encoding="utf-8").read(), 15)
    check(f"{tag} F1 opens the offline guide", ok, open(log, encoding="utf-8").read().strip())


def calc_checks(office, keys, tag):
    doc = office.load("private:factory/scalc")
    wait(lambda: "Sheets" in office.desktop().getCurrentFrame().getTitle(), 20)
    office.raise_windows()
    cell = doc.getSheets().getByIndex(0).getCellByPosition(0, 0)
    cell.setString("Số liệu")
    doc.getCurrentController().select(cell)
    keys.send("ctrl+b")
    check(f"{tag} Calc Ctrl+B bold cell", wait(lambda: cell.CharWeight >= 150, 5), str(cell.CharWeight))
    keys.send("ctrl+z")
    check(f"{tag} Calc Ctrl+Z undo", wait(lambda: cell.CharWeight < 150, 5), str(cell.CharWeight))
    found = keys.dialog_after("ctrl+1")
    check(f"{tag} Calc Ctrl+1 opens Format Cells", found is not None)
    if found:
        print(f"      dialog title: {found[1]!r}")
        keys.close_dialog(found[0])
    office.raise_windows()


def impress_checks(office, keys, tag):
    doc = office.load("private:factory/simpress")
    wait(lambda: "Slides" in office.desktop().getCurrentFrame().getTitle(), 20)
    office.raise_windows()
    show = doc.getPresentation()
    keys.send("F5")
    check(f"{tag} Impress F5 starts the slide show", wait(show.isRunning, 15))
    time.sleep(2)
    # the show window is a separate full-screen top level of this instance
    for wid, _name in keys.windows():
        subprocess.run(["xdotool", "windowfocus", "--sync", wid, "key", "Escape"], env=keys.env, check=False, timeout=15)
        if wait(lambda: not show.isRunning(), 3):
            break
    check(f"{tag} Impress Escape ends the slide show", wait(lambda: not show.isRunning(), 10))


def run(args, lang):
    tag = "vi" if lang.startswith("vi") else "en"
    work = os.path.join(os.path.abspath(args.out), tag)
    os.makedirs(work, exist_ok=True)
    bindir, log = xdg_stub(work)
    office = hst_gui.Office(args.instdir, work, PORT, display=args.display, lang=lang,
                            config=[("/org.openoffice.Office.Impress/Misc", "StartWithTemplate", "false"),
                                    ("/org.hasontech.hstoffice.UpdateCheck", "AutoCheck", "false")],
                            env={"PATH": bindir + ":/usr/local/bin:/usr/bin:/bin"})
    try:
        office.start()
        keys = Keys(office)
        doc = writer_checks(office, keys, work, tag)
        tab_checks(office, keys, doc, tag)
        if tag == "vi":
            f1_check(keys, log, tag)
            calc_checks(office, keys, tag)
            impress_checks(office, keys, tag)
        office.screenshot(os.path.join(os.path.abspath(args.out), f"{tag}-final.png"))
        # Ctrl+Q with every document unmodified: no prompt, the process ends.
        for comp in office.desktop().getComponents():
            try:
                comp.setModified(False)
            except Exception:  # noqa: BLE001
                pass
        keys.send("ctrl+q")
        check(f"{tag} Ctrl+Q quits", wait(lambda: office.proc.poll() is not None and office.pid is None, 30))
    except Exception as error:  # noqa: BLE001
        check(f"{tag} run completed", False, repr(error))
    finally:
        office.stop()


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--instdir", default=os.path.join(ROOT, "upstream/libreoffice/instdir"))
    parser.add_argument("--out", default=os.path.join(ROOT, "tests/output/shortcuts"))
    parser.add_argument("--display", default=":97")
    parser.add_argument("--lang", choices=("vi", "en", "both"), default="both")
    args = parser.parse_args()
    hst_gui.setup_uno(args.instdir)
    langs = {"vi": ["vi_VN.UTF-8"], "en": ["en_US.UTF-8"], "both": ["vi_VN.UTF-8", "en_US.UTF-8"]}[args.lang]
    for lang in langs:
        run(args, lang)
    failed = [name for name, ok in RESULTS if not ok]
    print(f"\n{len(RESULTS) - len(failed)}/{len(RESULTS)} PASS")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
