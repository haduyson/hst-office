#!/usr/bin/env python3
# SPDX-License-Identifier: AGPL-3.0-only
"""Linux: a session the system ended (SIGTERM, as systemd stops the session at log out or shut down) is not a crash.

Usage: python3 tests/runtime/check-session-end-linux.py --instdir <instdir> [--out tests/output/session-end]
           [--display :97]

  sigterm            a document changed after its first recovery copy; SIGTERM to every process of the office at once
                     (as systemd's KillMode=control-group does). The office stores the document and quits by itself;
                     the next start reopens it with both changes, still modified, without the recovery dialog and
                     without the crash report question (hst-session-end-store.patch; before it the office exited at
                     once, the next start offered the copy without the later change).
  sigterm-norestore  the same without AutoRecovery (--norestore): nothing can be stored, the office ends at once as
                     before, the next start asks no crash report question and its log says "session end"
                     (hst-session-end-note.patch).
  kill               a kill or a power cut (SIGKILL): the recovery dialog offers the copy and the crash report question
                     still appears ("not closed"). The office's stderr goes to a file, as on a
desktop start (no terminal, no pipe): the extension keeps it for the next start. The X display must already run.
Exit 1 when a check fails.
"""
import argparse
import importlib.util
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

PORT = 22237
_spec = importlib.util.spec_from_file_location("session_end_gnome", os.path.join(HERE, "check-session-end-gnome.py"))
gnome = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(gnome)


def start_with_stderr_file(off, fresh):
    """Start with fd 2 on a regular file (a desktop start's stderr is no terminal and no pipe)."""
    os.makedirs(off.workdir, exist_ok=True)
    saved = os.dup(2)
    log = os.open(os.path.join(off.workdir, "office-stderr.txt"), os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o644)
    os.dup2(log, 2)
    try:
        if not fresh:
            off.extra_args = [a for a in off.extra_args if a != "--nodefault"]  # a user's start: Start Center
        return off.start(fresh=fresh)
    finally:
        os.dup2(saved, 2)
        os.close(saved)
        os.close(log)


def crash_question(off):
    """The crash report question: a small top-level window titled "HST Office" (the Start Center is large)."""
    found = []
    for wid, name in hst_gui.toplevels(off.display, off.pid):
        if name != "HST Office":
            continue
        info = subprocess.run(["xwininfo", "-display", off.display, "-id", wid], capture_output=True, text=True).stdout
        width, height = (int(re.search(r"%s: (\d+)" % k, info).group(1)) for k in ("Width", "Height"))
        if width < 900 and height < 400:
            found.append(wid)
    return found


def log_lines(off):
    try:
        with open(os.path.join(rr.user_dir(off), "hst-office", "hst-office.log"), encoding="utf-8") as handle:
            return [line for line in handle.read().splitlines() if "previous session ended" in line]
    except OSError:
        return []


def end_office(off, name, sig, timeout=30):
    """A document changed before and after its first recovery copy, then the signal to every office process."""
    start_with_stderr_file(off, True)
    doc = rr.new_document(off, "writer", "PHIEN-%s-A" % name.upper())
    if off.restore:
        record("%s: a recovery copy within 120 s" % name, rr.wait(lambda: rr.copies(off), 120, 0.5), rr.backups(off))
    rr.append(doc, "PHIEN-%s-B" % name.upper())
    time.sleep(2)
    pattern = "UserInstallation=file://%s" % os.path.join(off.workdir, "profile")
    started = time.time()
    # the office's own processes (systemd signals every process of the session), not the su wrapper of the check,
    # which kills its children on SIGTERM
    for pid in subprocess.run(["pgrep", "-f", pattern], capture_output=True, text=True).stdout.split():
        try:
            with open("/proc/%s/comm" % pid, encoding="utf-8") as handle:
                if handle.read().strip() in ("soffice.bin", "oosplash"):
                    os.kill(int(pid), sig)
        except OSError:
            pass
    # the processes, not the windows: storing closes the document windows before the office ends
    ended = rr.wait(lambda: subprocess.run(["pgrep", "-f", pattern], capture_output=True).returncode == 1, timeout, 0.5)
    print("%s: office ended after %.1f s" % (name, time.time() - started) if ended else "%s: still running" % name)
    record("%s: the office ended" % name, ended)
    subprocess.run(["pkill", "-KILL", "-f", pattern], check=False)
    return len(log_lines(off))


def stored(off, name):
    end_office(off, name, 15, 40)
    record("%s: the session is marked for restore (SessionData)" % name, gnome.session_data(off))
    start_with_stderr_file(off, False)
    texts = rr.wait(lambda: [t for t in (rr.text_of(d) for d in rr.documents(off)) if t.strip()] or None, 60, 1) or []
    marks = ("PHIEN-%s-A" % name.upper(), "PHIEN-%s-B" % name.upper())
    record("%s: the next start reopens the document with both changes" % name,
           any(all(m in t for m in marks) for t in texts), texts)
    record("%s: the reopened document is still marked modified" % name, any(d.isModified() for d in rr.documents(off)))
    time.sleep(20)  # the crash question would come after the first visible window
    dialogs = gnome.small_hst_dialogs(off)
    record("%s: no recovery dialog and no crash report question" % name, not dialogs, dialogs)
    rr.finish(off)


def fallback(off, name):
    off.restore = False
    before = end_office(off, name, 15)
    start_with_stderr_file(off, False)
    question = rr.wait(lambda: crash_question(off), 30, 1)
    record("%s: crash report question not asked" % name, not question, question)
    lines = log_lines(off)[before:]
    record("%s: the log says 'session end'" % name, any("previous session ended: session end" in x for x in lines), lines)
    rr.finish(off)


def scenario(off, name, sig, expect_question):
    before = end_office(off, name, sig)
    start_with_stderr_file(off, False)
    record("%s: the recovery dialog offers the document" % name, rr.reconnect_after_recovery(off))
    texts = rr.wait(lambda: [t for t in (rr.text_of(d) for d in rr.documents(off)) if t.strip()] or None, 60, 1) or []
    record("%s: the recovered document holds the text of the copy" % name,
           any("PHIEN-%s-A" % name.upper() in t for t in texts), texts)
    question = rr.wait(lambda: crash_question(off), 30, 1)
    record("%s: crash report question %s" % (name, "asked" if expect_question else "not asked"),
           bool(question) == expect_question, question)
    lines = log_lines(off)[before:]
    want = "previous session ended: %s" % ("not closed" if expect_question else "session end")
    record("%s: the log says '%s'" % (name, want), any(want in line for line in lines), lines)
    if question:
        env = dict(os.environ, DISPLAY=off.display)
        for args in (("windowfocus", "--sync", question[0]), ("key", "Escape")):
            subprocess.run(["xdotool", *args], env=env, check=False, timeout=10)
    rr.finish(off)


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--instdir", required=True)
    ap.add_argument("--out", default=os.path.join(hst_gui.ROOT, "tests", "output", "session-end"))
    ap.add_argument("--display", default=":97")
    args = ap.parse_args()
    os.makedirs(args.out, exist_ok=True)
    hst_gui.setup_uno(args.instdir)
    runs = {"sigterm": stored, "sigterm-norestore": fallback, "kill": lambda o, n: scenario(o, n, 9, True)}
    for name, run in runs.items():
        off = rr.office(args.instdir, os.path.join(args.out, name), PORT, args.display, 1)
        try:
            run(off, name)
        except Exception as exc:  # noqa: BLE001 - one broken scenario must not hide the other
            record("%s: ran without error" % name, False, repr(exc))
            off.stop()
    return rr.summary("session end runtime")


if __name__ == "__main__":
    sys.exit(main())
