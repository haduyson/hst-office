#!/usr/bin/env python3
# SPDX-License-Identifier: AGPL-3.0-only
"""A crash while the configuration lock is held must not freeze the emergency save (owner report: the recovery dialog
stayed on screen after OK and only the Task Manager ended the office).

Usage: python3 tests/runtime/check-close-crash-handler-linux.py --instdir <instdir> [--out tests/output/close-crash]
           [--display :97] [--runs 3]

Every run: the owner's save settings (autosave every minute + "always autosave the document instead", backup copy in
the document's folder, .docx default); a saved .docx changed and autosaved in place, changed again; the UNO bridge is
dropped, gdb (fault-in-config-commit.gdb) stops the office in the next configuration commit, lets it take the
configuration lock and makes that thread fault; the Writer window is closed. The emergency save dialog must show;
after OK the office must end and restart within 30 s (before the fix the dialog froze: the save waited for
configmgr's writer thread, which waited for the lock of the faulted thread) and offer the document for recovery.
Needs gdb and permission to attach (ptrace) to the office. The X display must already run. Exit 1 when a check fails.
"""
import argparse
import os
import re
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path[:0] = [HERE]
import hst_gui  # noqa: E402
import recovery_runtime as rr  # noqa: E402
from recovery_runtime import record  # noqa: E402

FACTORY = "/org.openoffice.Setup/Office/Factories/org.openoffice.Setup:Factory['com.sun.star.text.TextDocument']"
OWNER_SETTINGS = [("/org.openoffice.Office.Recovery/AutoSave", "UserAutoSaveEnabled", "true"),
                  ("/org.openoffice.Office.Common/Save/Document", "CreateBackup", "true"),
                  ("/org.openoffice.Office.Common/Save/Document", "BackupIntoDocumentFolder", "true"),
                  ("/org.openoffice.Office.Common/Save/Document", "EditProperty", "true"),
                  ("/org.openoffice.Office.Common/Save/Document", "WarnAlienFormat", "false"),
                  (FACTORY, "ooSetupFactoryDefaultFilter", "MS Word 2007 XML")]


def drop_bridge():
    import uno
    local = uno.getComponentContext()
    for bridge in local.ServiceManager.createInstanceWithContext(
            "com.sun.star.bridge.BridgeFactory", local).getExistingBridges():
        bridge.dispose()
    time.sleep(2)


def run(args, index):
    import uno
    from com.sun.star.beans import PropertyValue
    work = os.path.join(args.out, "run-%d" % index)
    off = rr.office(args.instdir, work, hst_gui.free_port(), args.display, interval_minutes=1)
    off.config += [(n, p, v) for n, p, v in OWNER_SETTINGS]
    off.start()
    docs = os.path.join(work, "docs")
    os.makedirs(docs, exist_ok=True)
    subprocess.run(["chown", hst_gui.BUILD_USER, docs], check=False)
    doc = rr.new_document(off, "writer", "synthetic")
    arg = PropertyValue()
    arg.Name, arg.Value = "FilterName", "MS Word 2007 XML"
    doc.storeAsURL(uno.systemPathToFileUrl(os.path.join(docs, "t.docx")), (arg,))
    rr.append(doc, "changed")
    autosaved = rr.wait(lambda: not doc.isModified(), 120, 2)
    record("run %d: the autosave stored the .docx in place" % index, autosaved)
    rr.append(doc, "after-autosave")
    pid = off.pid
    writer = [w for w in hst_gui.toplevels(args.display, pid) if "Writer" in w[1]]
    doc = None
    drop_bridge()
    gdb_log = open(os.path.join(work, "gdb-fault.txt"), "w")
    gdb = subprocess.Popen(["gdb", "-p", str(pid), "-batch", "-x", os.path.join(HERE, "fault-in-config-commit.gdb")],
                           stdout=gdb_log, stderr=subprocess.STDOUT)
    time.sleep(20)  # attached, breakpoint set
    hst_gui.send_close_request(writer[0][0], args.display)
    shown = rr.wait(lambda: [w for w in hst_gui.toplevels(args.display, pid) if re.search(rr.RECOVERY_TITLE, w[1])],
                    60, 1)
    record("run %d: the emergency save dialog shows" % index, shown, open(gdb_log.name).read()[-300:])
    if shown:
        time.sleep(3)
        rr.answer(off, rr.RECOVERY_TITLE, corner=rr.EMERGENCY_OK, timeout=10)
        ended = rr.wait(lambda: off.pid != pid, 30, 1)
        hst_gui.screenshot(os.path.join(work, "after-ok.png"), args.display)
        record("run %d: after OK the office ends and restarts within 30 s" % index, ended)
        if ended:
            offered = rr.wait(lambda: [w for w in hst_gui.toplevels(args.display, off.pid)
                                       if re.search(rr.RECOVERY_TITLE, w[1])], 90, 2)
            record("run %d: the restarted office offers the document for recovery" % index, offered)
    if gdb.poll() is None:
        gdb.kill()
    subprocess.run(["pkill", "-9", "-f", "UserInstallation=file://" + os.path.join(work, "profile")], check=False)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--instdir", required=True)
    parser.add_argument("--out", default="tests/output/close-crash")
    parser.add_argument("--display", default=":97")
    parser.add_argument("--runs", type=int, default=3)
    args = parser.parse_args()
    args.out = os.path.abspath(args.out)
    hst_gui.setup_uno(args.instdir)
    for index in range(args.runs):
        run(args, index)
    return rr.summary("check-close-crash-handler-linux")


if __name__ == "__main__":
    sys.exit(main())
