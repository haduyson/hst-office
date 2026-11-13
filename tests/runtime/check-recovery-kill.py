#!/usr/bin/env python3
# SPDX-License-Identifier: AGPL-3.0-only
"""Recovery after a crash on Linux: kill -9 and a real crash signal (SIGSEGV, the emergency save).

Usage: python3 tests/runtime/check-recovery-kill.py --instdir <instdir> [--out tests/output/recovery-kill]
           [--display :97] [--scenario first|after|emergency|all] [--runs 5]

  first      a new document is killed 40 s after its first change: its first recovery copy (30 s) is offered and
             holds the text;
  after      kill -9 right after a later recovery copy replaced the previous one (the window in which the old
             configuration still named the deleted copy): the entry on disk names an existing copy and the recovery
             brings the latest text;
  emergency  --runs times: a Writer and a Sheets document in tabs, changed after their last copy, then SIGSEGV; the
             emergency save dialog is confirmed, the office restarts, offers both documents with the latest text and
             the tab layout file is still there.
The X display must already run. Exit 1 when a check fails.
"""
import argparse
import os
import signal
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path[:0] = [HERE]
import hst_gui  # noqa: E402
import recovery_runtime as rr  # noqa: E402
from recovery_runtime import record  # noqa: E402

PORT = 22231


def recovered_texts(off, count=1):
    """Texts of the open documents once `count` of them have loaded (the recovery opens them one by one)."""
    def texts():
        found = [t for t in (rr.text_of(d) for d in rr.documents(off)) if t.strip()]
        return found if len(found) >= count else None
    return rr.wait(texts, 90, 1) or [rr.text_of(d) for d in rr.documents(off)]


def scenario_first(off):
    off.start()
    rr.new_document(off, "writer", "MOT-CHUA-LUU")
    began = time.time()
    copy = rr.wait(lambda: rr.copies(off), 60, 0.2)
    print("first: first recovery copy after %.1f s" % (time.time() - began), flush=True)
    record("first: a recovery copy within 60 s of the first change (due at 30 s, then 10 s without input)", copy, rr.backups(off))
    pid = rr.kill(off)
    rr.gone(off, pid)
    record("first: the recovery dialog offers the document", rr.restart_and_recover(off))
    texts = recovered_texts(off)
    record("first: the recovered document holds the text", any("MOT-CHUA-LUU" in t for t in texts), texts)
    rr.finish(off)


def scenario_after(off):
    off.start()
    doc = rr.new_document(off, "writer", "HAI-BAN-DAU")
    first = rr.wait(lambda: rr.copies(off), 45, 0.5) or {}
    rr.append(doc, "HAI-BAN-SAU")
    # a later copy replaces the first one (interval 1 minute in this profile); kill the moment it appears
    newer = rr.wait(lambda: set(rr.copies(off)) - set(first), 200, 0.02)
    pid = rr.kill(off)
    rr.gone(off, pid)
    record("after: a second copy replaced the first", newer, rr.backups(off))
    names = [u.rsplit("/", 1)[-1] for u in rr.recovery_list(off) or []]
    present = set(rr.backups(off))
    record("after: the configuration on disk names an existing copy", names and all(n in present for n in names if n),
           (names, sorted(present)))
    record("after: the recovery index names an existing copy",
           any(e[4].rsplit("/", 1)[-1] in present for e in rr.index_entries(off) if len(e) > 4), rr.index_entries(off))
    record("after: the recovery dialog offers the document", rr.restart_and_recover(off))
    texts = recovered_texts(off)
    record("after: the recovery brings the latest text", any("HAI-BAN-SAU" in t for t in texts), texts)
    rr.finish(off)


def scenario_emergency(off, run):
    off.start()
    writer = rr.new_document(off, "writer", "KHAN-%d-A" % run)
    calc = rr.new_document(off, "calc", "KHAN-%d-A" % run)
    rr.wait(lambda: len(rr.copies(off)) >= 2, 60, 1)
    rr.append(writer, "KHAN-%d-B" % run)
    rr.append(calc, "KHAN-%d-B" % run)
    time.sleep(3)  # the tab layout is written 1.5 s after a change
    had_tabs = rr.tabs_file(off)
    pid = rr.kill(off, signal.SIGSEGV)
    shown = rr.answer(off, rr.RECOVERY_TITLE, corner=rr.EMERGENCY_OK, timeout=60)  # "... phải đóng. Các tài liệu đang mở sẽ được lưu lại"
    record("emergency %d: the emergency save dialog appears" % run, shown)
    rr.gone(off, pid, 90)
    record("emergency %d: the tab layout survives the emergency save" % run, had_tabs and rr.tabs_file(off))
    record("emergency %d: the restarted office offers the documents" % run, rr.reconnect_after_recovery(off))
    texts = recovered_texts(off, 2)
    record("emergency %d: both documents hold the text typed after the last copy" % run,
           sum(1 for t in texts if "KHAN-%d-B" % run in t) >= 2, texts)
    rr.finish(off)


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--instdir", required=True)
    ap.add_argument("--out", default=os.path.join(hst_gui.ROOT, "tests", "output", "recovery-kill"))
    ap.add_argument("--display", default=":97")
    ap.add_argument("--scenario", default="all", choices=("first", "after", "emergency", "all"))
    ap.add_argument("--runs", type=int, default=5)
    args = ap.parse_args()
    os.makedirs(args.out, exist_ok=True)
    hst_gui.setup_uno(args.instdir)
    work = lambda name, minutes=3: rr.office(args.instdir, os.path.join(args.out, name), PORT, args.display, minutes)
    if args.scenario in ("first", "all"):
        scenario_first(work("first"))
    if args.scenario in ("after", "all"):
        scenario_after(work("after", 1))
    if args.scenario in ("emergency", "all"):
        for run in range(1, args.runs + 1):
            scenario_emergency(work("emergency-%d" % run), run)
    return rr.summary("recovery kill runtime")


if __name__ == "__main__":
    sys.exit(main())
