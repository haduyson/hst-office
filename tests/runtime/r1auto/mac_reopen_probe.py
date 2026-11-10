# SPDX-License-Identifier: AGPL-3.0-only
"""Throwaway probe: why Desktop.terminate() leaves the macOS office running with no window.

Runs with the bundle's own Python (launch.interpreter). One office (copy of the app, own profile, pipe), then:
  A main-thread terminate()            (the product's context: an AsyncCallback on the VCL thread, like run_later)
  B URP-thread terminate()             (same call, not from a main-thread callback)
  C main-thread terminate() with SuspendQuickstartVeto=True (the fix; what the office's own Quit does)
Each step records the return value, the frames left and whether soffice is still alive."""
import json
import subprocess
import sys
import threading
import time
from pathlib import Path

import uno
import unohelper
from com.sun.star.awt import XCallback

from office import Office


class Call(unohelper.Base, XCallback):
    def __init__(self, fn):
        self.fn, self.done, self.result = fn, threading.Event(), None

    def notify(self, data):
        try:
            self.result = {"value": self.fn(), "thread": threading.current_thread().name}
        except Exception as error:  # noqa: BLE001 - recorded
            self.result = {"error": repr(error)}
        self.done.set()


def pids(app):
    out = subprocess.run(["pgrep", "-f", str(app) + "/Contents/MacOS/soffice"], capture_output=True, text=True).stdout
    return [int(p) for p in out.split()]


def main():
    app, work, out = (Path(a) for a in sys.argv[1:4])
    office = Office(app, work).start()
    ctx = office.ctx
    smgr = ctx.ServiceManager
    desktop = smgr.createInstanceWithContext("com.sun.star.frame.Desktop", ctx)
    steps, log = [], out / "reopen-probe.json"

    def frames():
        try:
            return desktop.getFrames().getCount()
        except Exception as error:  # noqa: BLE001
            return repr(error)

    def main_thread(fn, timeout=120):
        call = Call(fn)
        smgr.createInstanceWithContext("com.sun.star.awt.AsyncCallback", ctx).addCallback(call, None)
        if not call.done.wait(timeout):
            return {"error": "no callback within %d s" % timeout}
        return call.result

    def record(name, result):
        time.sleep(5)
        alive = pids(app)
        entry = dict(step=name, result=result, frames_after=frames() if alive else None, soffice_pids=alive)
        steps.append(entry)
        log.write_text(json.dumps(steps, indent=1, ensure_ascii=False), encoding="utf-8")
        print(json.dumps(entry, ensure_ascii=False), flush=True)
        return alive

    steps.append(dict(step="start", frames=frames(), soffice_pids=pids(app),
                      suspend=desktop.getPropertyValue("SuspendQuickstartVeto")))
    if record("A main-thread terminate", main_thread(desktop.terminate)):
        if record("B urp-thread terminate", {"value": desktop.terminate()}):
            def fixed():
                desktop.setPropertyValue("SuspendQuickstartVeto", True)
                return desktop.terminate()
            alive = record("C main-thread terminate, SuspendQuickstartVeto", main_thread(fixed))
            end = time.monotonic() + 60
            while alive and time.monotonic() < end:
                time.sleep(1)
                alive = pids(app)
            steps.append(dict(step="C exit within 60 s", exited=not alive))
            log.write_text(json.dumps(steps, indent=1, ensure_ascii=False), encoding="utf-8")
    for pid in pids(app):  # only the copy this probe started
        subprocess.run(["kill", str(pid)])
    print(log.read_text(encoding="utf-8"))


if __name__ == "__main__":
    main()
