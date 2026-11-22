#!/usr/bin/env python3
# SPDX-License-Identifier: LicenseRef-HST-Proprietary
# Copyright (C) 2026 HASON TECH
"""The first recovery copy of a new document comes about 30 s after its first change, also when the change comes
right after the document opened (before AutoRecovery registered it).

Usage: python3 tests/runtime/check-recovery-first-copy.py --instdir <instdir> [--out tests/output/recovery-first-copy]
           [--display :97] [--runs 4] [--interval 10]

Per run: a fresh profile with the AutoSave interval at --interval minutes (long, so a copy that waits for it is
plainly late), a new Writer document changed at once (as a macro, an extension or a fast first edit does), and the
first copy in the backup folder must be there within 45 s. The office answers the change either before or after
it registered the document, so several runs are needed to meet both orders. The X display must already run; as
root the check re-executes itself as the build user. Exit 1 when a run fails.
"""
import argparse
import os
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import hst_gui  # noqa: E402
import recovery_runtime as rr  # noqa: E402
from recovery_runtime import record  # noqa: E402

PORT = 22251
FIRST_COPY_S = 45  # 20 s to the copy, upstream's 10 s wait for a pause in typing, and the save itself


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--instdir", required=True)
    ap.add_argument("--out", default=os.path.join(hst_gui.ROOT, "tests", "output", "recovery-first-copy"))
    ap.add_argument("--display", default=":97")
    ap.add_argument("--runs", type=int, default=4)
    ap.add_argument("--interval", type=int, default=10)
    args = ap.parse_args()
    os.makedirs(args.out, exist_ok=True)
    if os.geteuid() == 0:
        subprocess.run(["chown", "-R", hst_gui.BUILD_USER, args.out], check=False)
        os.execvp("runuser", ["runuser", "-u", hst_gui.BUILD_USER, "--", sys.executable] + sys.argv)
    hst_gui.setup_uno(args.instdir)
    for run in range(args.runs):
        off = rr.office(args.instdir, os.path.join(args.out, f"run{run}"), PORT + run, args.display,
                        interval_minutes=args.interval)
        off.start()
        try:
            started = time.time()
            rr.new_document(off, "writer", "BAN-SAO-DAU-TIEN")
            copied = rr.wait(lambda: rr.copies(off), FIRST_COPY_S, 1)
            record(f"run {run}: the first copy within {FIRST_COPY_S} s of a change made as the document opened",
                   copied, f"none after {round(time.time() - started)} s: {rr.backups(off)}")
        finally:
            rr.finish(off)
    return rr.summary("recovery first copy")


if __name__ == "__main__":
    sys.exit(main())
