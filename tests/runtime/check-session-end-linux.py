#!/usr/bin/env python3
# SPDX-License-Identifier: AGPL-3.0-only
"""Linux: a session the system ended (SIGTERM, as systemd stops the session at log out or shut down) is not a crash.

Usage: python3 tests/runtime/check-session-end-linux.py --instdir <instdir> [--out tests/output/session-end]
           [--display :97]

  sigterm  a document changed after its first recovery copy; SIGTERM to every process of the office at once (as
           systemd's KillMode=control-group does). The next start offers the copy (recovery dialog) and the recovered
           document holds the text, but no crash report question appears and the log says "session end".
  kill     the same with SIGKILL (a kill or a power cut): the crash report question still appears ("not closed").
Before hst-session-end-note.patch the sigterm scenario asked the question too. The office's stderr goes to a file, as on a
desktop start (no terminal, no pipe): the extension keeps it for the next start. The X display must already run.
Exit 1 when a check fails.
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

PORT = 22237


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


def scenario(off, name, sig, expect_question):
    start_with_stderr_file(off, True)
    doc = rr.new_document(off, "writer", "PHIEN-%s-A" % name.upper())
    record("%s: a recovery copy within 60 s" % name, rr.wait(lambda: rr.copies(off), 60, 0.5), rr.backups(off))
    rr.append(doc, "PHIEN-%s-B" % name.upper())
    time.sleep(2)
    pattern = "UserInstallation=file://%s" % os.path.join(off.workdir, "profile")
    subprocess.run(["pkill", "-%d" % sig, "-f", pattern], check=False)
    record("%s: the office ended" % name, rr.wait(lambda: off.pid is None, 30, 0.5))
    subprocess.run(["pkill", "-KILL", "-f", pattern], check=False)
    before = len(log_lines(off))
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
    for name, sig, expect in (("sigterm", 15, False), ("kill", 9, True)):
        off = rr.office(args.instdir, os.path.join(args.out, name), PORT, args.display, 1)
        try:
            scenario(off, name, sig, expect)
        except Exception as exc:  # noqa: BLE001 - one broken scenario must not hide the other
            record("%s: ran without error" % name, False, repr(exc))
            off.stop()
    return rr.summary("session end runtime")


if __name__ == "__main__":
    sys.exit(main())
