# SPDX-License-Identifier: AGPL-3.0-only
"""Wait, on a worker thread, until the office's UI thread has gone quiet.

Background work that starts processes or burns CPU (the banner feed helpers) must not compete with the start-up:
the first window maps while the UI thread still builds the ribbon and the document view for some seconds. A ping is
posted to the UI thread's event loop (com.sun.star.awt.AsyncCallback); while that thread is busy the ping waits.
The UI counts as idle once every ping of a quiet window is answered quickly. Never call wait() on the UI thread.
"""
import threading
import time

import unohelper
from com.sun.star.awt import XCallback

PING_GAP = 0.1  # seconds between pings
FAST = 0.05  # a ping answered within this is a quiet moment
QUIET = 2.0  # seconds of consecutive quiet pings
LIMIT = 60.0  # give up waiting (a UI kept busy for a minute): run anyway


class _Ping(unohelper.Base, XCallback):
    def __init__(self):
        self.done = threading.Event()

    def notify(self, data):
        self.done.set()


def wait(ctx, clock=time.monotonic, sleep=time.sleep):
    """True once the UI thread was quiet for QUIET seconds; False after LIMIT seconds or without the service."""
    try:
        callback = ctx.ServiceManager.createInstanceWithContext("com.sun.star.awt.AsyncCallback", ctx)
    except Exception:  # noqa: BLE001 - no toolkit (headless tools): nothing to wait for
        callback = None
    if callback is None:
        return False
    started = clock()
    quiet_since = None
    while clock() - started < LIMIT:
        ping = _Ping()
        sent = clock()
        try:
            callback.addCallback(ping, None)
        except Exception:  # noqa: BLE001 - the office is shutting down
            return False
        if not ping.done.wait(max(0.0, LIMIT - (sent - started))):
            return False
        now = clock()
        if now - sent > FAST:
            quiet_since = None
        elif quiet_since is None:
            quiet_since = sent
        elif now - quiet_since >= QUIET:
            return True
        sleep(PING_GAP)
    return False
