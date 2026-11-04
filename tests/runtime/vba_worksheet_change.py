# SPDX-License-Identifier: AGPL-3.0-only
"""Part of check-vba-editor.py: Worksheet_Change follows edits made by the user, not UNO calls."""
import os
import subprocess
import time

import hst_gui


def check_worksheet_change(office, out, check, wait, window):
    """Worksheet_Change of an Excel file runs when the user types into a cell."""
    import shutil
    import uno
    from com.sun.star.beans import PropertyValue
    path = os.path.join(out, "change.xlsm")
    shutil.copyfile(os.path.join(hst_gui.ROOT, "upstream/libreoffice/sc/qa/extras/testdocuments/SimpleCopyPaste.xlsm"), path)
    subprocess.run(["chown", hst_gui.BUILD_USER, path], check=False)
    mode = PropertyValue()
    mode.Name, mode.Value = "MacroExecutionMode", 4  # the test's own file; the prompt is checked separately
    doc = office.desktop().loadComponentFromURL(uno.systemPathToFileUrl(path), "_blank", 0, (mode,))
    lib = doc.BasicLibraries.getByName(doc.BasicLibraries.ProjectName)
    lib.replaceByName("Sheet1", lib.getByName("Sheet1") + '\nPrivate Sub Worksheet_Change(ByVal Target As Range)\n'
                      '  If Target.Address = "$A$5" Then Range("H2").Value = Target.Value * 2\nEnd Sub\n')
    sheet = doc.Sheets.getByIndex(0)
    found = wait(lambda: window(office, r"HST Sheets$") is not None, 10)
    if found:
        env = dict(os.environ, DISPLAY=office.display)
        wid = window(office, r"HST Sheets$")[0]
        # a click in the sheet area gives the grid keyboard focus; then select A5 and type
        subprocess.run(["xdotool", "mousemove", "--window", wid, "700", "600", "click", "1"], env=env, check=False, timeout=15)
        time.sleep(1)
        doc.getCurrentController().select(sheet.getCellRangeByName("A5"))
        time.sleep(0.5)
        subprocess.run(["xdotool", "windowfocus", "--sync", wid, "type", "--delay", "80", "21"], env=env, check=False, timeout=15)
        subprocess.run(["xdotool", "windowfocus", "--sync", wid, "key", "Return"], env=env, check=False, timeout=15)
        time.sleep(1)
    if sheet.getCellRangeByName("A5").Value != 21:
        office.screenshot(os.path.join(out, "worksheet-change-failed.png"))
        print("windows:", hst_gui.toplevels(office.display, office.pid))
    check("calc: Worksheet_Change runs when the user types into a cell",
          wait(lambda: sheet.getCellRangeByName("H2").Value == 42, 10), f"A5={sheet.getCellRangeByName('A5').Value} H2={sheet.getCellRangeByName('H2').Value}")
    doc.close(True)
