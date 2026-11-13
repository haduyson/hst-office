# SPDX-License-Identifier: AGPL-3.0-only
"""Check the Microsoft Office keyboard shortcuts of HST Writer, HST Sheets and HST Slides on a real
build (GTK3, fresh profile, vi UI) - docs/SHORTCUTS-MSOFFICE.md.

Usage: python3 tests/runtime/check-msoffice-shortcuts.py [--instdir upstream/libreoffice/instdir]
       [--out tests/output/msoffice-shortcuts] [--display :97]

Keys are sent with xdotool to the document window and the effect is read back over UNO:

  Writer  Ctrl+2/5/1 line spacing, Ctrl+E, Ctrl+Alt+1/2/3 headings, Ctrl+Shift+N Normal, F4 repeat,
          Ctrl+M / Ctrl+Shift+M indent, Ctrl+T hanging indent, Ctrl+Shift+L bullets,
          Ctrl+Shift+> / < font size, Ctrl+= / Ctrl+Shift+= sub/superscript, Ctrl+Space clears
          character formatting, Ctrl+Shift+D double underline, Alt+Shift+D date field,
          Ctrl+Shift+V paste text only, Ctrl+Alt+C / Ctrl+Alt+V copy and paste formatting, Ctrl+Q removes
          paragraph formatting and does not quit, Ctrl+Alt+M comment, Ctrl+Alt+Shift+V Paste Special,
          Ctrl+D Font dialog, F12 Save As dialog
  Sheets  Alt+= AutoSum, Ctrl+R fill right, Ctrl+Shift+! $ % # @ ^ ~ number formats, Alt+Enter new
          line in the cell, Ctrl+Enter fills the selection, Shift+F11 new sheet, Ctrl+T table dialog
  Slides  Ctrl+M new slide, Ctrl+D / Ctrl+Shift+D duplicate slide, Ctrl+G group, Ctrl+Shift+G
          ungroup, F12 Save As dialog
Exit 1 when any check fails. The default save format check is check-msoffice-save-format.py.
"""
import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import hst_gui  # noqa: E402
from msoffice_keys_sheets_slides import calc_checks, impress_checks  # noqa: E402
from msoffice_keys_writer import writer_checks  # noqa: E402
from shortcut_keys import RESULTS, Keys, check  # noqa: E402

PORT = 22952


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--instdir", default=os.path.join(hst_gui.ROOT, "upstream/libreoffice/instdir"))
    parser.add_argument("--out", default=os.path.join(hst_gui.ROOT, "tests/output/msoffice-shortcuts"))
    parser.add_argument("--display", default=":97")
    args = parser.parse_args()
    hst_gui.setup_uno(args.instdir)
    work = os.path.abspath(args.out)
    os.makedirs(work, exist_ok=True)
    office = hst_gui.Office(args.instdir, work, PORT, display=args.display, lang="vi_VN.UTF-8",
                            config=[("/org.openoffice.Office.Impress/Misc/NewDoc", "AutoPilot", "false"),
                                    ("/org.hasontech.hstoffice.UpdateCheck", "AutoCheck", "false")])
    try:
        office.start()
        keys = Keys(office)
        for step in (writer_checks, calc_checks, impress_checks):
            try:
                step(office, keys)
            except Exception as error:  # noqa: BLE001 - report and go on with the next module
                check(f"{step.__name__} completed", False, repr(error))
        office.screenshot(os.path.join(work, "final.png"))
        for comp in office.desktop().getComponents():  # no "save?" question on terminate
            comp.setModified(False)
    finally:
        office.stop()
    failed = [name for name, ok in RESULTS if not ok]
    print(f"\n{len(RESULTS) - len(failed)}/{len(RESULTS)} PASS")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
