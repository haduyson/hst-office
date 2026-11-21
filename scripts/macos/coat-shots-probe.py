# SPDX-License-Identifier: AGPL-3.0-only
"""Screenshots of the HST coat on macOS, driven over UNO in the office started by coat-shots-probe.sh.

    coat-shots-probe.py <pid> <port> <out-dir> <look>     (look: before-light, after-dark, ...)

Per application (Writer, Sheets, Slides): the document window with the sidebar open, then the File tab; then sample
dialogs of the tier-3 list. Each dialog is shot while shown and ended with endExecute. Evidence only: a failed
shot is written to failures.txt, it never stops the run."""
import os
import subprocess
import sys
import time

import uno
from com.sun.star.beans import PropertyValue

pid, port, out, look = int(sys.argv[1]), int(sys.argv[2]), sys.argv[3], sys.argv[4]
os.makedirs(out, exist_ok=True)
failures = open(os.path.join(out, f"failures-{look}.txt"), "a", encoding="utf-8")

APPS = [("writer", "swriter"), ("sheets", "scalc"), ("slides", "simpress")]
DIALOGS = {
    "writer": [("paragraph", ".uno:ParagraphDialog"), ("page", ".uno:PageDialog"), ("find-replace", ".uno:SearchDialog"),
               ("insert-table", ".uno:InsertTable"), ("options", ".uno:OptionsTreeDialog"),
               ("customize", ".uno:ConfigureDialog")],
    "sheets": [("format-cells", ".uno:FormatCellDialog"), ("sort", ".uno:DataSort")],
    "slides": [("slide-show-settings", ".uno:PresentationDialog"), ("insert-table", ".uno:InsertTable")],
}


def front():
    script = f'tell application "System Events" to set frontmost of (first process whose unix id is {pid}) to true'
    subprocess.run(["perl", "-e", "alarm 20; exec @ARGV", "osascript", "-e", script],
                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False)


def shot(name):
    front()
    time.sleep(1)
    path = os.path.join(out, f"{name}-{look}.png")
    if subprocess.run(["screencapture", "-x", path], check=False, timeout=30).returncode:
        failures.write(f"{name}: screencapture failed\n")


def prop(name, value):
    p = PropertyValue()
    p.Name, p.Value = name, value
    return p


local = uno.getComponentContext()
resolver = local.ServiceManager.createInstanceWithContext("com.sun.star.bridge.UnoUrlResolver", local)
deadline = time.time() + 180
while True:
    try:
        ctx = resolver.resolve(f"uno:socket,host=127.0.0.1,port={port};urp;StarOffice.ComponentContext")
        break
    except Exception:  # noqa: BLE001 - not listening yet
        if time.time() > deadline:
            raise
        time.sleep(2)
smgr = ctx.ServiceManager
desktop = smgr.createInstanceWithContext("com.sun.star.frame.Desktop", ctx)
ui = smgr.createInstanceWithContext("com.sun.star.ui.test.UITest", ctx)
toolkit = smgr.createInstanceWithContext("com.sun.star.awt.Toolkit", ctx)
dialog_type = uno.getTypeByName("com.sun.star.awt.XDialog")


def activate(frame):
    frame.activate()
    desktop.setActiveFrame(frame)
    frame.getContainerWindow().setFocus()


def end_dialogs():
    """endExecute on every shown dialog; True when one was ended."""
    ended = False
    for i in range(toolkit.getTopWindowCount() - 1, -1, -1):
        try:
            window = toolkit.getTopWindow(i)
            dialog = window.queryInterface(dialog_type) if window.isVisible() else None
            if dialog:
                dialog.endExecute()
                ended = True
        except Exception:  # noqa: BLE001 - disposed while listed
            continue
    return ended


for app, factory in APPS:
    try:
        doc = desktop.loadComponentFromURL(f"private:factory/{factory}", "_blank", 0, (prop("OnMainThread", True),))
        time.sleep(4)
        frame = doc.getCurrentController().getFrame()
        if app == "writer":
            doc.getText().setString("Thử nghiệm khung HST: thanh công cụ, thanh bên và thanh trạng thái.")
        activate(frame)
        ui.executeCommand(".uno:SidebarDeck.PropertyDeck")
        time.sleep(3)
        shot(f"{app}-window")
        activate(frame)
        ui.executeCommand(".uno:HSTBackstage")
        time.sleep(3)
        shot(f"{app}-backstage")
        activate(frame)
        ui.executeCommand(".uno:HSTBackstage")
        time.sleep(2)
        for name, command in DIALOGS[app]:
            try:
                activate(frame)
                ui.executeDialog(command)
                time.sleep(4)
                shot(f"{app}-dialog-{name}")
            except Exception as error:  # noqa: BLE001 - one dialog must not stop the run
                failures.write(f"{app} {name}: {error!r}\n")
            finally:
                for _ in range(3):
                    if not end_dialogs():
                        break
                    time.sleep(1.5)
        doc.setModified(False)
        doc.close(True)
        time.sleep(2)
    except Exception as error:  # noqa: BLE001 - evidence only
        failures.write(f"{app}: {error!r}\n")
failures.close()
print("done", look)
