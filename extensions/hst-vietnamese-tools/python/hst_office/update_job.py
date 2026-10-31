# SPDX-License-Identifier: AGPL-3.0-only
"""Update check entry points: the start-up job (Jobs.xcu, onFirstVisibleTask) and the org.hst.office.update:
command handler (menu "Kiểm tra cập nhật…" and the infobar buttons).

Start-up: only when AutoCheck is on and the last attempt is 24 h old; the attempt time is stored first, then a
daemon thread fetches and verifies the manifest (update_fetch), so start-up is never blocked or slowed.
Any failure is logged (stderr) and nothing is shown. Results reach the UI through the main thread only.
"""
import threading
import time
import traceback

import uno
import unohelper
from com.sun.star.frame import XDispatch, XDispatchProvider
from com.sun.star.lang import XInitialization, XServiceInfo
from com.sun.star.task import XJob

from . import update_logic as logic
from . import update_result as result
from . import update_ui as ui
from .update_fetch import UpdateError, fetch_channels

JOB_NAME = "org.hst.office.vi.UpdateCheckJob"
HANDLER_NAME = "org.hst.office.vi.UpdateDispatchProvider"
COMMANDS = ("Check", "Download", "Install", "Notes", "Skip")


def _log(message):
    print("HST update check: %s" % message, flush=True)


def check(ctx, info, proxy, on_done):
    """Fetch, verify and select on the calling (worker) thread; on_done(release|None, failed) on the main thread."""
    try:
        channels = fetch_channels(info, proxy)
        release, failed = logic.select_update(channels, info["release"], info["channel"]), False
    except UpdateError as exc:
        _log(exc)
        release, failed = None, True
    except Exception:  # noqa: BLE001 - never crash the office from the worker thread
        traceback.print_exc()
        release, failed = None, True
    ui.on_main_thread(ctx, lambda: on_done(release, failed))


def start_background(ctx, info, on_done):
    proxy = ui.proxy(ctx)  # read on the main thread; the worker only does network and pure logic
    thread = threading.Thread(target=check, args=(ctx, info, proxy, on_done), name="hst-update-check", daemon=True)
    thread.start()
    return thread


def automatic_check(ctx, now=None):
    """The start-up path; returns the worker thread or None when nothing is due."""
    prefs = ui.settings(ctx)
    now = int(time.time() if now is None else now)
    if not prefs["AutoCheck"] or not logic.check_due(now, prefs["LastCheck"], prefs["CheckIntervalHours"] * 3600):
        return None
    ui.save(ctx, "LastCheck", now)
    info = ui.release_info_for(ctx)

    def done(release, failed):
        if not failed and logic.should_notify(release, ui.settings(ctx)["SkippedVersion"]):
            ui.notify(ctx, release, info["release"])
    return start_background(ctx, info, done)


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
            automatic_check(self.ctx)
        except Exception:  # noqa: BLE001 - never block or break start-up
            traceback.print_exc()
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
            traceback.print_exc()

    def _check(self):
        frame = self.frame
        peer = frame.getContainerWindow() if frame else None
        try:
            if not ui.settings(self.ctx)["ManualCheck"]:  # locked off by the administrator: never contact the server
                return None
            info = ui.release_info_for(self.ctx)
        except Exception:  # noqa: BLE001 - no release stamp: report "could not check"
            traceback.print_exc()
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
            traceback.print_exc()

    def removeStatusListener(self, control, url):
        pass
