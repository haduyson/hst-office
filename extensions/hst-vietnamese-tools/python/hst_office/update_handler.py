# SPDX-License-Identifier: AGPL-3.0-only
"""The org.hst.office.update: command handler (menu "Kiểm tra cập nhật" and the infobar buttons).

The Start Center creates it and adds a status listener for each update menu item while the splash screen is still
up, so this module imports only the settings reader; the update check code (update_job, update_ui and the network
modules they import) is imported when a command runs.
"""
import uno
import unohelper
from com.sun.star.frame import XDispatch, XDispatchProvider
from com.sun.star.lang import XInitialization, XServiceInfo

from . import diag_log, update_config

HANDLER_NAME = "org.hst.office.vi.UpdateDispatchProvider"
PROTOCOL = "org.hst.office.update:"  # update_ui.PROTOCOL (tests/unit/test_component_lazy_registration.py)
COMMANDS = ("Check", "Download", "Install", "Notes", "Skip")


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
        return self if url.Protocol == PROTOCOL and url.Path in COMMANDS else None

    def queryDispatches(self, requests):
        return tuple(self.queryDispatch(r.FeatureURL, r.FrameName, r.SearchFlags) for r in requests)

    def dispatch(self, url, arguments):
        try:
            getattr(self, "_" + url.Path.lower())()
        except Exception:  # noqa: BLE001 - report instead of failing inside the UI thread
            diag_log.exception("update_handler")

    def _check(self):
        from . import update_install_id, update_result as result, update_ui as ui
        from .update_job import start_background
        frame = self.frame
        peer = frame.getContainerWindow() if frame else None
        try:
            if not ui.settings(self.ctx)["ManualCheck"]:  # locked off by the administrator: never contact the server
                return None
            info = update_install_id.add_to(self.ctx, ui.release_info_for(self.ctx))
        except Exception:  # noqa: BLE001 - no release stamp: report "could not check"
            diag_log.exception("update_handler")
            return result.show_result(self.ctx, peer, None, "", True)
        start_background(self.ctx, info, lambda release, failed: result.show_result(self.ctx, peer, release, info["release"], failed))

    def _download(self):
        from . import update_ui as ui
        if ui.STATE["release"]:
            ui.open_url(self.ctx, ui.release_download(ui.STATE["release"]))

    def _install(self):
        from .update_install import start  # imported on use: start-up never loads the installer flow
        frame = self.frame
        start(self.ctx, frame.getContainerWindow() if frame else None)

    def _notes(self):
        from . import update_ui as ui
        if ui.STATE["release"]:
            ui.open_url(self.ctx, ui.STATE["release"]["notes"])

    def _skip(self):
        from . import update_ui as ui
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
            event.FeatureURL, event.IsEnabled, event.Requery = url, bool(update_config.settings(self.ctx)["ManualCheck"]), False
            event.Source = self
            control.statusChanged(event)
        except Exception:  # noqa: BLE001 - the menu stays enabled; _check still refuses
            diag_log.exception("update_handler")

    def removeStatusListener(self, control, url):
        pass
