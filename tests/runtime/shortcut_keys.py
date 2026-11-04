# SPDX-License-Identifier: AGPL-3.0-only
"""Key input helpers of the keyboard shortcut runtime checks: results, waiting, one Office instance's keys."""
import os
import subprocess
import time

import hst_gui

RESULTS = []


def check(name, ok, detail=""):
    RESULTS.append((name, bool(ok)))
    print(f"{'PASS' if ok else 'FAIL'} {name}" + (f"  ({detail})" if detail and not ok else ""), flush=True)
    return ok


def wait(cond, timeout=10.0, step=0.3):
    end = time.time() + timeout
    while time.time() < end:
        try:
            if cond():
                return True
        except Exception:  # noqa: BLE001 - UNO objects may be in flux while a key takes effect
            pass
        time.sleep(step)
    return False


class Keys:
    """Key input and window bookkeeping for one Office instance."""

    def __init__(self, office):
        self.office = office
        self.env = dict(os.environ, DISPLAY=office.display)

    def windows(self):
        return hst_gui.toplevels(self.office.display, self.office.pid)

    def doc_window(self):
        for wid, name in self.windows():
            if name.endswith(("HST Writer", "HST Sheets", "HST Slides")):
                return wid
        return None

    def send(self, keys, wid=None):
        wid = wid or self.doc_window()
        if wid is None:
            return False
        subprocess.run(["xdotool", "windowfocus", "--sync", wid, "key", "--clearmodifiers", keys],
                       env=self.env, check=False, timeout=15)
        time.sleep(0.6)
        return True

    def dialog_after(self, keys, timeout=12):
        """Press keys; return the name of a new top-level window of this instance (or None)."""
        before = {w for w, _ in self.windows()}
        self.send(keys)
        found = []
        wait(lambda: found.extend((w, n) for w, n in self.windows() if w not in before) or found, timeout)
        return found[0] if found else None

    def close_dialog(self, wid):
        subprocess.run(["xdotool", "windowfocus", "--sync", wid, "key", "Escape"], env=self.env, check=False, timeout=15)
        if not wait(lambda: wid not in {w for w, _ in self.windows()}, 8):
            hst_gui.send_close_request(wid, self.office.display)
            return wait(lambda: wid not in {w for w, _ in self.windows()}, 8)
        return True


def xdg_stub(work):
    """A logging xdg-open first on PATH: F1 hands the guide URL to it instead of a browser."""
    bindir = os.path.join(work, "bin")
    os.makedirs(bindir, exist_ok=True)
    log = os.path.join(work, "xdg-open.log")
    open(log, "w").close()
    os.chmod(log, 0o666)
    stub = os.path.join(bindir, "xdg-open")
    with open(stub, "w", encoding="utf-8") as handle:
        handle.write(f'#!/bin/sh\necho "$@" >> "{log}"\n')
    os.chmod(stub, 0o755)
    return bindir, log
