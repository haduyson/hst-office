#!/usr/bin/env python3
# SPDX-License-Identifier: LicenseRef-HST-Proprietary
# Copyright (C) 2026 HASON TECH
"""Linux: a GNOME/Cinnamon log out keeps the open documents and their changes (hst-gnome-end-session-save.patch).

Usage: python3 tests/runtime/check-session-end-gnome.py --instdir <instdir> [--out tests/output/session-end-gnome]
           [--display :97]

A new Writer document is changed, recovery-copied, changed again; a session manager on a private bus
(fake_gnome_session.py) plays a log out: QueryEndSession (the office holds it: unsaved document), then EndSession.
The office must quit with the session marked (RecoveryInfo/SessionData), and the next start must reopen the document
with both changes, still modified, without the recovery dialog and without the crash report question. Before the
patch the office cleared the modified flags and quit: the changes were lost and nothing was offered.
Needs dbus-daemon and the host's python3 with Gio. The X display must already run. Exit 1 when a check fails.
"""
import argparse
import os
import re
import shutil
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path[:0] = [HERE]
import hst_gui  # noqa: E402
import recovery_runtime as rr  # noqa: E402
from recovery_runtime import record  # noqa: E402

PORT = 22239
CLEAN_ENV = ["env", "-u", "PYTHONHOME", "-u", "PYTHONPATH", "-u", "URE_BOOTSTRAP"]


def session_bus(ctl):
    """dbus-daemon and the fake session manager, as the build user; returns (processes, bus address)."""
    shutil.copy(os.path.join(HERE, "fake_gnome_session.py"), ctl)
    if os.geteuid() == 0:
        subprocess.run(["chown", "-R", hst_gui.BUILD_USER, ctl], check=False)
    bus = subprocess.Popen(hst_gui._as_user_prefix() + ["dbus-daemon", "--session", "--nofork", "--print-address",
                           "--address=unix:path=%s/bus" % ctl], stdout=subprocess.PIPE, text=True)
    address = bus.stdout.readline().strip()
    manager = subprocess.Popen(hst_gui._as_user_prefix() + CLEAN_ENV + ["DBUS_SESSION_BUS_ADDRESS=" + address,
                               "/usr/bin/python3", os.path.join(ctl, "fake_gnome_session.py"), ctl])
    time.sleep(1)
    return [manager, bus], address


def session_data(off):
    try:
        with open(os.path.join(rr.user_dir(off), "registrymodifications.xcu"), encoding="utf-8") as handle:
            text = handle.read()
    except OSError:
        return None
    found = re.findall(r'RecoveryInfo"><prop oor:name="SessionData"[^>]*><value>(\w+)</value>', text)
    return found[-1] == "true" if found else None


def small_hst_dialogs(off):
    """The recovery dialog or the crash report question (the Start Center and documents are large)."""
    found = []
    for wid, name in hst_gui.toplevels(off.display, off.pid):
        info = subprocess.run(["xwininfo", "-display", off.display, "-id", wid], capture_output=True, text=True).stdout
        width = int(re.search(r"Width: (\d+)", info).group(1))
        if re.search(rr.RECOVERY_TITLE, name) or (name == "HST Office" and width < 900):
            found.append(name)
    return found


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--instdir", required=True)
    ap.add_argument("--out", default=os.path.join(hst_gui.ROOT, "tests", "output", "session-end-gnome"))
    ap.add_argument("--display", default=":97")
    args = ap.parse_args()
    hst_gui.setup_uno(args.instdir)
    work = os.path.join(args.out, "gnome")
    shutil.rmtree(work, ignore_errors=True)
    ctl = os.path.join(work, "ctl")
    os.makedirs(ctl)
    helpers, address = session_bus(ctl)
    os.environ["DBUS_SESSION_BUS_ADDRESS"] = address
    off = rr.office(args.instdir, work, PORT, args.display, 1)
    try:
        off.start()
        doc = rr.new_document(off, "writer", "GNOME-A")
        record("a recovery copy within 120 s", rr.wait(lambda: rr.copies(off), 120, 0.5), rr.backups(off))
        rr.append(doc, "GNOME-B")
        time.sleep(2)
        open(os.path.join(ctl, "query"), "w").close()
        time.sleep(4)
        with open(os.path.join(ctl, "inhibitors"), encoding="utf-8") as handle:
            record("the office holds the log out (unsaved document)", handle.read().strip() == "1")
        open(os.path.join(ctl, "end"), "w").close()
        record("the office quits on EndSession", rr.wait(lambda: off.pid is None, 60, 0.5))
        record("the session is marked for restore (SessionData)", session_data(off), session_data(off))
        record("the recovery list keeps the document", rr.recovery_list(off), rr.recovery_list(off))
        off.extra_args = [a for a in off.extra_args if a != "--nodefault"]  # a user's start
        off.start(fresh=False)
        texts = rr.wait(lambda: [t for t in (rr.text_of(d) for d in rr.documents(off)) if t.strip()] or None, 60, 1) or []
        record("the next start reopens the document with both changes",
               any("GNOME-A" in t and "GNOME-B" in t for t in texts), texts)
        record("the reopened document is still marked modified", any(d.isModified() for d in rr.documents(off)))
        time.sleep(20)  # the crash question would come after the first visible window
        dialogs = small_hst_dialogs(off)
        record("no recovery dialog and no crash report question", not dialogs, dialogs)
    except Exception as exc:  # noqa: BLE001
        record("ran without error", False, repr(exc))
    finally:
        rr.finish(off)
        for helper in helpers:
            helper.terminate()
    return rr.summary("gnome session end runtime")


if __name__ == "__main__":
    sys.exit(main())
