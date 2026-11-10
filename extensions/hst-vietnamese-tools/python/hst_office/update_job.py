# SPDX-License-Identifier: AGPL-3.0-only
"""Update check entry points: the start-up job (Jobs.xcu, onFirstVisibleTask) and the org.hst.office.update:
command handler (menu "Kiểm tra cập nhật" and the infobar buttons).

Start-up: only when AutoCheck is on and the last successful check is 24 h old. A daemon thread fetches and verifies
the manifest (update_fetch), so start-up is never blocked or slowed. A failure is logged (stderr), shows nothing and
is retried twice (RETRY_DELAYS), then waits for the next start; the check time is stored on success only, so a machine
that was offline at start-up is not skipped for a whole day. Results reach the UI through the main thread only.
"""
import threading
import time

import uno
import unohelper
from com.sun.star.frame import XDispatch, XDispatchProvider
from com.sun.star.lang import XInitialization, XServiceInfo
from com.sun.star.task import XJob

from . import update_logic as logic
from . import update_outcome
from . import update_result as result
from . import update_ui as ui
from .update_fetch import UpdateError, fetch_channels
from . import diag_log

JOB_NAME = "org.hst.office.vi.UpdateCheckJob"
HANDLER_NAME = "org.hst.office.vi.UpdateDispatchProvider"
COMMANDS = ("Check", "Download", "Install", "Notes", "Skip")
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
    info = ui.release_info_for(ctx)
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


class UpdateHandler(unohelper.Base, XServiceInfo, XInitialization, XDispatchProvider, XDispatch):
    """org.hst.office.update:Check | Download | Install | Notes | Skip."""

    def __init__(self, ctx):
        self.ctx, self.frame = ctx, None

    def initialize(self, args):
        if args:
            self.frame = args[0]

    def getImplementationName(self):
        return HANDLER_NAME

    def supportsService(self, name):
        return name in self.getSupportedServiceNames()

    def getSupportedServiceNames(self):
        return ("com.sun.star.frame.ProtocolHandler",)

    def queryDispatch(self, url, target_frame_name, search_flags):
        return self if url.Protocol == ui.PROTOCOL and url.Path in COMMANDS else None

    def queryDispatches(self, requests):
        return tuple(self.queryDispatch(r.FeatureURL, r.FrameName, r.SearchFlags) for r in requests)

    def dispatch(self, url, arguments):
        try:
            getattr(self, "_" + url.Path.lower())()
        except Exception:  # noqa: BLE001 - report instead of failing inside the UI thread
            diag_log.exception("update_job")

    def _check(self):
        frame = self.frame
        peer = frame.getContainerWindow() if frame else None
        try:
            if not ui.settings(self.ctx)["ManualCheck"]:  # locked off by the administrator: never contact the server
                return None
            info = ui.release_info_for(self.ctx)
        except Exception:  # noqa: BLE001 - no release stamp: report "could not check"
            diag_log.exception("update_job")
            return result.show_result(self.ctx, peer, None, "", True)
        start_background(self.ctx, info, lambda release, failed: result.show_result(self.ctx, peer, release, info["release"], failed))

    def _download(self):
        if ui.STATE["release"]:
            ui.open_url(self.ctx, ui.release_download(ui.STATE["release"]))

    def _install(self):
        from .update_install import start  # imported on use: start-up never loads the installer flow
        frame = self.frame
        start(self.ctx, frame.getContainerWindow() if frame else None)

    def _notes(self):
        if ui.STATE["release"]:
            ui.open_url(self.ctx, ui.STATE["release"]["notes"])

    def _skip(self):
        if ui.STATE["release"]:
            ui.save(self.ctx, "SkippedVersion", ui.STATE["release"]["version"])
        if self.frame is not None:
            ui.remove_infobar(self.frame)

    def addStatusListener(self, control, url):
        """Menu entries of :Check are disabled when the administrator set ManualCheck = false."""
        if url.Path != "Check":
            return
        try:
            event = uno.createUnoStruct("com.sun.star.frame.FeatureStateEvent")
            event.FeatureURL, event.IsEnabled, event.Requery = url, bool(ui.settings(self.ctx)["ManualCheck"]), False
            event.Source = self
            control.statusChanged(event)
        except Exception:  # noqa: BLE001 - the menu stays enabled; _check still refuses
            diag_log.exception("update_job")

    def removeStatusListener(self, control, url):
        pass
