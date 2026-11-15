# SPDX-License-Identifier: AGPL-3.0-only
"""Hang watchdog for GUI runtime checks: when a check makes no progress for `idle` seconds, record why and fail fast
instead of sitting until the runner's timeout (a batch5 smoke sat 40 minutes after 39 PASS with no evidence).

On a hang it writes into `out`: hang-python.txt (every harness thread) and hang-gdb.txt (every soffice.bin thread,
when gdb can attach), prints one FAIL line naming a known product deadlock when the stacks match it, stops this
check's own office (same profile only) and ends the process with exit code 3.

Known signature: the gtk3 clipboard deadlock. A UNO request thread builds a Paste control (document load, mode
switch), SwBaseShell::StateClpbrd asks the system clipboard and gtk_clipboard_wait_* runs a nested loop of the
default main context on that thread while the main thread waits for the context in g_main_context_iteration.
"""
import faulthandler
import os
import re
import subprocess
import sys
import threading
import time

GTK_CLIPBOARD = "gtk3 clipboard deadlock (clipboard query off the main thread)"


def classify(gdb_text):
    """Name of a known deadlock in an all-thread gdb dump, or None."""
    threads = re.split(r"\n(?=Thread \d+ )", gdb_text)
    main = [t for t in threads if re.match(r"Thread 1 ", t)]
    others = [t for t in threads if not re.match(r"Thread 1 ", t)]
    off_main_query = any("gtk_clipboard_wait_for" in t for t in others)
    main_waits = bool(main) and "g_main_context_iteration" in main[0] and "g_cond_wait" in main[0]
    return GTK_CLIPBOARD if off_main_query and main_waits else None


def gdb_dump(pid, timeout=180):
    """All-thread backtraces of `pid`, or a line saying why there are none."""
    try:
        run = subprocess.run(["gdb", "-p", str(pid), "-batch", "-ex", "set pagination off",
                              "-ex", "thread apply all bt 40"], capture_output=True, text=True, timeout=timeout)
        return run.stdout + run.stderr
    except (OSError, subprocess.TimeoutExpired) as error:
        return f"no gdb dump: {error!r}\n"


class HangWatch:
    """Call beat() after every step of the check; start() arms the watchdog, stop() disarms it."""

    def __init__(self, office, out, idle=300, exit_code=3):
        self.office, self.out, self.idle, self.exit_code = office, out, idle, exit_code
        self.last = time.time()
        self.what = "start"
        self._stop = threading.Event()

    def beat(self, what=""):
        self.last, self.what = time.time(), what or self.what

    def start(self):
        threading.Thread(target=self._watch, daemon=True).start()
        return self

    def stop(self):
        self._stop.set()

    def _watch(self):
        while not self._stop.wait(5):
            if time.time() - self.last > self.idle:
                self._report()
                os._exit(self.exit_code)

    def _report(self):
        os.makedirs(self.out, exist_ok=True)
        with open(os.path.join(self.out, "hang-python.txt"), "w", encoding="utf-8") as log:
            faulthandler.dump_traceback(log, all_threads=True)
        pid = self.office.pid
        text = gdb_dump(pid) if pid else "no soffice.bin of this profile\n"
        with open(os.path.join(self.out, "hang-gdb.txt"), "w", encoding="utf-8") as log:
            log.write(text)
        known = classify(text)
        print("FAIL  no progress for %d s after: %s; office %s%s; stacks in %s" % (
            self.idle, self.what, pid, ": " + known if known else " (unknown hang)", self.out), flush=True)
        self._kill_office()
        print("FAIL", flush=True)
        sys.stdout.flush()

    def _kill_office(self):
        """Hung offices never answer terminate(): end this profile's processes only."""
        profile = os.path.join(self.office.workdir, "profile")
        subprocess.run(["pkill", "-KILL", "-f", f"UserInstallation=file://{profile}"], check=False)
        proc = getattr(self.office, "proc", None)
        if proc is not None and proc.poll() is None:
            proc.kill()
