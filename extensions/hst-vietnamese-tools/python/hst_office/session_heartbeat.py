# SPDX-License-Identifier: AGPL-3.0-only
"""Session heartbeat: what was open, and when the office last answered, kept in the session marker while it runs.

A crash report written at the next start used to know only the office's recovery list, which names modified documents
only: a session that ended while its documents were just opened or unchanged reported "Documents open at exit: 0" and
app "unknown", and a frozen office ended by the user looked exactly like a kill. Every BEAT seconds a timer thread
posts one callback to the office's main thread (never more than one waiting); the callback reads the open documents'
apps, the active one and how many are modified, and stores them with the time in the marker (diag_crash.update_marker):
at once when they changed, otherwise every REFRESH seconds. A frozen main thread runs no callback, so the stored time
is the last moment the office answered. No document names, titles or locations are stored, only app keys and counts.
"""
import threading
import time

import unohelper
from com.sun.star.awt import XCallback

from . import diag_crash, diag_log
from .error_report_info import app_of_module

BEAT = 10
REFRESH = 30
STATE = {"stop": None, "waiting": False, "seen": None, "written": 0.0}


def snapshot(ctx):
    """{"apps": sorted app keys of the open documents (one per document), "active": app key of the current one,
    "modified": count, "loading": documents still being imported}."""
    smgr = ctx.ServiceManager
    desktop = smgr.createInstanceWithContext("com.sun.star.frame.Desktop", ctx)
    modules = smgr.createInstanceWithContext("com.sun.star.frame.ModuleManager", ctx)

    def app(frame):
        try:
            return app_of_module(modules.identify(frame))
        except Exception:  # noqa: BLE001 - a frame without a component (being loaded or closed)
            return "unknown"

    apps, modified, loading = [], 0, 0
    frames = desktop.getFrames()
    for index in range(frames.getCount()):
        frame = frames.getByIndex(index)
        controller = frame.getController()
        model = controller.getModel() if controller is not None else None
        if controller is None:
            loading += 1
            continue
        if model is None:  # Start Center, help: no document
            continue
        apps.append(app(frame))
        try:
            modified += 1 if model.isModified() else 0
        except Exception:  # noqa: BLE001 - not every model is modifiable
            pass
    current = desktop.getCurrentFrame()
    active = app(current) if current is not None else ""
    return {"apps": sorted(apps), "active": active, "modified": modified, "loading": loading}


def beat(ctx, now=None, take=snapshot, store=diag_crash.update_marker):
    """One heartbeat on the main thread: store the snapshot and the time when it changed or REFRESH has passed."""
    now = time.time() if now is None else now
    seen = take(ctx)
    if seen != STATE["seen"] or now - STATE["written"] >= REFRESH:
        if store(dict(seen, beat=now)):
            STATE["seen"], STATE["written"] = seen, now


class _Beat(unohelper.Base, XCallback):
    def __init__(self, ctx):
        self.ctx = ctx

    def notify(self, data):
        STATE["waiting"] = False
        try:
            if not STATE["stop"].is_set():
                beat(self.ctx)
        except Exception:  # noqa: BLE001 - never raise into the office's event loop
            diag_log.exception("session_heartbeat", print_too=False)


def _run(ctx, stop):
    callback = _Beat(ctx)
    post = ctx.ServiceManager.createInstanceWithContext("com.sun.star.awt.AsyncCallback", ctx)
    while not stop.wait(BEAT):
        if STATE["waiting"]:
            continue  # the main thread has not run the last one: frozen or busy; do not pile up callbacks
        STATE["waiting"] = True
        try:
            post.addCallback(callback, None)
        except Exception:  # noqa: BLE001 - office shutting down
            return


def start(ctx):
    """OnStartApp: start beating (once per process)."""
    if STATE["stop"] is not None:
        return
    STATE["stop"] = threading.Event()
    threading.Thread(target=_run, args=(ctx, STATE["stop"]), name="hst-session-heartbeat", daemon=True).start()


def stop():
    """OnCloseApp: no beat may rewrite the marker after it is removed."""
    if STATE["stop"] is not None:
        STATE["stop"].set()
