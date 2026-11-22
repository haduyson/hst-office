# SPDX-License-Identifier: LicenseRef-HST-Proprietary
# Copyright (C) 2026 HASON TECH
"""Wait, on a worker thread, until the office has finished its start-up work.

Background work that starts processes or burns CPU (the banner feed helpers) must not compete with the start-up:
the first window maps while the UI thread still builds the ribbon and the document view for some seconds. The
office's own CPU time (os.times(), every platform) tells when that work is over, without involving the UI thread:
a probe answered by the UI thread runs Python there, which then waits for the interpreter lock held by other start-up
jobs and slowed the start-up it was meant to protect (first right-click on 2 vCPU: 1.9 s -> 3.2 s median).
"""
import os
import time

SAMPLE = 0.25  # seconds between CPU readings
BUSY = 0.25  # share of one core above which the office is still working
QUIET = 2.0  # seconds below BUSY in a row
FIRST = 3.0  # never earlier than this after the call (the first window has only just appeared)
LIMIT = 60.0  # give up waiting (an office kept busy for a minute): run anyway


def _cpu():
    times = os.times()
    return times.user + times.system


def wait(ctx=None, clock=time.monotonic, sleep=time.sleep, cpu=_cpu):
    """True once the office used less than BUSY of a core for QUIET seconds (not before FIRST); False after LIMIT."""
    started = clock()
    sleep(FIRST)
    quiet_since = None
    last_time, last_cpu = clock(), cpu()
    while clock() - started < LIMIT:
        sleep(SAMPLE)
        now, used = clock(), cpu()
        share = (used - last_cpu) / max(now - last_time, 1e-3)
        last_time, last_cpu = now, used
        if share > BUSY:
            quiet_since = None
        elif quiet_since is None:
            quiet_since = now
        elif now - quiet_since >= QUIET:
            return True
    return False
