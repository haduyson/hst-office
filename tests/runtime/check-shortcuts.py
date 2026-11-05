# SPDX-License-Identifier: AGPL-3.0-only
"""Check the standard keyboard shortcuts on a real HST Office build (GTK3, fresh profile).

Usage: python3 tests/runtime/check-shortcuts.py [--instdir upstream/libreoffice/instdir]
       [--out tests/output/shortcuts] [--display :97] [--lang vi|en|both]

Keys are sent with xdotool to this instance's own document window (X focus set explicitly:
the test display has no window manager) and the effect is read back over UNO:

  Writer  Ctrl+A select all, Ctrl+B/I/U bold/italic/underline, Ctrl+Z/Ctrl+Y undo/redo,
          Ctrl+X/Ctrl+V cut/paste, Ctrl+S save (no dialog for a stored .odt),
          Ctrl+F find toolbar, Ctrl+H/Ctrl+Shift+S/F12/Ctrl+O/Ctrl+P/F7 open a dialog (Escape closes),
          F1 opens the offline guide (logged by an xdg-open stub),
          Ctrl+N new document tab, Ctrl+Alt+, / Ctrl+Alt+. previous/next tab, Ctrl+W close tab
  Calc    Ctrl+B bold cell, Ctrl+1 Format Cells dialog, Ctrl+Z undo
  Impress F5 starts the slide show, Escape ends it
  Sheets  Ctrl+Q quits (unmodified documents, no prompt); in Writer it removes paragraph formatting

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
from shortcut_keys import RESULTS, Keys, check, wait, xdg_stub  # noqa: E402
from shortcuts_writer_checks import writer_checks  # noqa: E402

ROOT = hst_gui.ROOT
PORT = 22950


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
        # Ctrl+Q in Sheets with every document unmodified: no prompt, the process ends.
        office.load("private:factory/scalc")
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
