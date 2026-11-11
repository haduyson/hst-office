# SPDX-License-Identifier: AGPL-3.0-only
"""Update check: the start-up job (Jobs.xcu, onFirstVisibleTask) and the check the org.hst.office.update: command
handler starts (update_handler.py: menu "Kiểm tra cập nhật" and the infobar buttons).

Start-up: only when AutoCheck is on and the last successful check is 24 h old. A daemon thread fetches and verifies
the manifest (update_fetch), so start-up is never blocked or slowed. A failure is logged (stderr), shows nothing and
is retried twice (RETRY_DELAYS), then waits for the next start; the check time is stored on success only, so a machine
that was offline at start-up is not skipped for a whole day. Results reach the UI through the main thread only.
Both entry points add the anonymous install ID (update_install_id) to the request, unless SendInstallId is off; the
"Cập nhật ngay" flow (update_prepare) fetches the manifest again without it.
"""
import threading
import time

import unohelper
from com.sun.star.lang import XServiceInfo
from com.sun.star.task import XJob

from . import update_install_id
from . import update_logic as logic
from . import update_outcome
from . import update_ui as ui
from .update_fetch import UpdateError, fetch_channels
from . import diag_log

JOB_NAME = "org.hst.office.vi.UpdateCheckJob"
RETRY_DELAYS = (120, 600)  # seconds before each new automatic attempt, e.g. the network comes up after login
_automatic_thread = None  # a retrying check must not be doubled by a second start-up event of the same process


def _log(message):
    print("HST update check: %s" % message, flush=True)
    diag_log.warning("update", "check failed: %s" % message)


def _fetch_update(info, proxy):
    """(release|None, failed) after fetching, verifying and selecting on the calling (worker) thread."""
    try:
        channels = fetch_channels(info, proxy)
        return logic.select_update(channels, info["release"], info["channel"]), False
    except UpdateError as exc:
        _log(exc)
    except Exception:  # noqa: BLE001 - never crash the office from the worker thread
        diag_log.exception("update_job")
    return None, True


def check(ctx, info, proxy, on_done):
    """One attempt on the calling (worker) thread; on_done(release|None, failed) on the main thread."""
    release, failed = _fetch_update(info, proxy)
    ui.on_main_thread(ctx, lambda: on_done(release, failed))


def _check_with_retries(ctx, info, proxy, on_done):
    release, failed = _fetch_update(info, proxy)
    for delay in RETRY_DELAYS:
        if not failed:
            break
        time.sleep(delay)
        release, failed = _fetch_update(info, proxy)
    ui.on_main_thread(ctx, lambda: on_done(release, failed))


def start_background(ctx, info, on_done):
    proxy = ui.proxy(ctx)  # read on the main thread; the worker only does network and pure logic
    thread = threading.Thread(target=check, args=(ctx, info, proxy, on_done), name="hst-update-check", daemon=True)
    thread.start()
    return thread


def automatic_check(ctx, now=None):
    """The start-up path; returns the worker thread or None when nothing is due."""
    global _automatic_thread
    if _automatic_thread is not None and _automatic_thread.is_alive():
        return None
    prefs = ui.settings(ctx)
    now = int(time.time() if now is None else now)
    if not prefs["AutoCheck"] or not logic.check_due(now, prefs["LastCheck"], prefs["CheckIntervalHours"] * 3600):
        return None
    info = update_install_id.add_to(ctx, ui.release_info_for(ctx))
    started = time.monotonic()

    def done(release, failed):
        if failed:
            return
        ui.save(ctx, "LastCheck", now + int(time.monotonic() - started))  # when it succeeded, retries included
        if logic.should_notify(release, ui.settings(ctx)["SkippedVersion"]):
            ui.notify(ctx, release, info["release"])
    proxy = ui.proxy(ctx)  # read on the main thread; the worker only does network and pure logic
    _automatic_thread = threading.Thread(target=_check_with_retries, args=(ctx, info, proxy, done),
                                         name="hst-update-check", daemon=True)
    _automatic_thread.start()
    return _automatic_thread


class UpdateCheckJob(unohelper.Base, XServiceInfo, XJob):
    def __init__(self, ctx):
        self.ctx = ctx

    def getImplementationName(self):
        return JOB_NAME

    def supportsService(self, name):
        return name in self.getSupportedServiceNames()

    def getSupportedServiceNames(self):
        return ("com.sun.star.task.Job",)

    def execute(self, arguments):
        try:
            update_outcome.show_pending(self.ctx)
            automatic_check(self.ctx)
        except Exception:  # noqa: BLE001 - never block or break start-up
            diag_log.exception("update_job")
        return None


# The command handler lives in its own small module (the Start Center creates it while the splash screen is up).
from .update_handler import COMMANDS, HANDLER_NAME, UpdateHandler  # noqa: E402,F401 - names of this module before
