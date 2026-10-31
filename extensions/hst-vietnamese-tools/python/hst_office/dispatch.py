# SPDX-License-Identifier: AGPL-3.0-only
"""ProtocolHandler (Vietnamese in every UI language: product policy) for the org.hst.office.vi: command URLs used by the HST menu and toolbar."""
import os
import tempfile
import time
import traceback

import unohelper
from com.sun.star.frame import XDispatch, XDispatchProvider
from com.sun.star.lang import XInitialization, XServiceInfo

from . import ui_language
from .actions import COMMANDS, Host
from .data_files import load_locale

IMPLEMENTATION_NAME = "org.hst.office.vi.DispatchProvider"
PROTOCOL = "org.hst.office.vi:"
# command -> (service of the document it works in, URL of a new blank document of that kind)
NEW_DOCUMENT = {"Nd30Wizard": ("com.sun.star.text.TextDocument", "private:factory/swriter"),
                "ImportCsv": ("com.sun.star.sheet.SpreadsheetDocument", "private:factory/scalc")}
SHOW_SOLUTIONS = "ShowSolutions"  # needs no document, so it also works in the Start Center


def log_error(command):
    """Print the traceback and append it to hst-office-errors.log in the temp directory (the Windows office has no console)."""
    traceback.print_exc()
    try:
        with open(os.path.join(tempfile.gettempdir(), "hst-office-errors.log"), "a", encoding="utf-8") as handle:
            handle.write("%s %s\n%s\n" % (time.strftime("%Y-%m-%d %H:%M:%S"), command, traceback.format_exc()))
    except OSError:
        pass


class Handler(unohelper.Base, XServiceInfo, XInitialization, XDispatchProvider, XDispatch):
    def __init__(self, ctx):
        self.ctx, self.frame = ctx, None

    def initialize(self, args):
        if args:
            self.frame = args[0]

    def getImplementationName(self):
        return IMPLEMENTATION_NAME

    def supportsService(self, name):
        return name in self.getSupportedServiceNames()

    def getSupportedServiceNames(self):
        return ("com.sun.star.frame.ProtocolHandler",)

    def queryDispatch(self, url, target_frame_name, search_flags):
        return self if url.Protocol == PROTOCOL and (url.Path in COMMANDS or url.Path in ui_language.COMMANDS or url.Path == SHOW_SOLUTIONS) else None

    def queryDispatches(self, requests):
        return tuple(self.queryDispatch(r.FeatureURL, r.FrameName, r.SearchFlags) for r in requests)

    def dispatch(self, url, arguments):
        if url.Path == SHOW_SOLUTIONS:
            return self._show_solutions()
        if url.Path in ui_language.COMMANDS:
            try:
                ui_language.run(self.ctx, self.frame, url.Path)
            except Exception:  # noqa: BLE001 - never raise into the office UI thread
                log_error(url.Path)
            return
        frame = self.frame
        try:
            frame = self._frame_for(url.Path)
            COMMANDS[url.Path](Host(self.ctx, frame, load_locale("vi")))
        except Exception as exc:  # noqa: BLE001 - never fail silently inside the office UI thread
            log_error(url.Path)
            try:
                Host(self.ctx, frame, load_locale("vi")).say("%s: %s" % (type(exc).__name__, exc), error=True)
            except Exception:  # noqa: BLE001
                pass

    def _frame_for(self, command):
        """Frame of a document of the kind the command works on; opens a blank one from the Start Center or another module."""
        kind = NEW_DOCUMENT.get(command)
        controller = self.frame.getController() if self.frame else None
        model = controller.getModel() if controller else None
        if kind is None or (model is not None and model.supportsService(kind[0])):
            return self.frame
        desktop = self.ctx.ServiceManager.createInstanceWithContext("com.sun.star.frame.Desktop", self.ctx)
        document = desktop.loadComponentFromURL(kind[1], "_blank", 0, ())
        return document.getCurrentController().getFrame()

    def _show_solutions(self):
        try:
            from .welcome_job import show_welcome
            peer = self.frame.getContainerWindow() if self.frame else None
            show_welcome(self.ctx, "menu", peer)  # introductory content: always Vietnamese
        except Exception:  # noqa: BLE001 - report instead of failing silently inside the UI thread
            traceback.print_exc()

    def addStatusListener(self, control, url):
        if url.Protocol == PROTOCOL and url.Path in ui_language.COMMANDS:
            from com.sun.star.frame import FeatureStateEvent
            enabled, checked = ui_language.status(self.ctx, url.Path)
            control.statusChanged(FeatureStateEvent(FeatureURL=url, IsEnabled=enabled, State=bool(checked),
                                                    Requery=False, Source=self))

    def removeStatusListener(self, control, url):
        pass  # Status is a fresh snapshot on add; no listener is retained.
