# SPDX-License-Identifier: AGPL-3.0-only
"""ProtocolHandler (Vietnamese in every UI language: product policy) for the org.hst.office.vi: command URLs used by the HST menu and toolbar."""
import os
import tempfile
import time
import traceback

import unohelper
from com.sun.star.frame import XDispatch, XDispatchProvider
from com.sun.star.lang import XInitialization, XServiceInfo

from . import ui_language, usb_token
from .actions import COMMANDS, Host
from .data_files import load_locale

IMPLEMENTATION_NAME = "org.hst.office.vi.DispatchProvider"
PROTOCOL = "org.hst.office.vi:"
# command -> (service of the document it works in, URL of a new blank document of that kind)
NEW_DOCUMENT = {"Nd30Wizard": ("com.sun.star.text.TextDocument", "private:factory/swriter"),
                "ImportCsv": ("com.sun.star.sheet.SpreadsheetDocument", "private:factory/scalc")}
SHOW_SOLUTIONS = "ShowSolutions"  # needs no document, so it also works in the Start Center
USB_TOKEN = "SetupUsbToken"
REPORT_ERROR = "ReportError"  # Trợ giúp ▸ Báo lỗi cho HASON TECH; needs no document either
DEFAULT_APPS = "DefaultApps"  # HST ▸ Dùng HST Office để mở tài liệu văn phòng; needs no document
DUPLEX = "ToggleDuplex"  # HST ▸ In hai mặt: a check item showing the document's choice


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
        self._duplex_listeners = []  # (control, url): the "In hai mặt" check mark follows each toggle

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
        return self if url.Protocol == PROTOCOL and (url.Path in COMMANDS or url.Path in ui_language.COMMANDS
                                                    or url.Path in (SHOW_SOLUTIONS, USB_TOKEN, REPORT_ERROR, DEFAULT_APPS)) else None

    def queryDispatches(self, requests):
        return tuple(self.queryDispatch(r.FeatureURL, r.FrameName, r.SearchFlags) for r in requests)

    def dispatch(self, url, arguments):
        if url.Path == USB_TOKEN:
            return usb_token.run(self.ctx, self.frame)
        if url.Path == SHOW_SOLUTIONS:
            return self._show_solutions()
        if url.Path == REPORT_ERROR:
            try:
                from .error_report_dialog import run  # imported on use: start-up never loads the report code
                run(self.ctx, self.frame)
            except Exception:  # noqa: BLE001 - never raise into the office UI thread
                log_error(url.Path)
            return
        if url.Path == DEFAULT_APPS:
            try:
                from .default_apps import run_from_menu
                run_from_menu(self.ctx, self.frame.getContainerWindow() if self.frame else None)
            except Exception:  # noqa: BLE001 - never raise into the office UI thread
                log_error(url.Path)
            return
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
            if url.Path == DUPLEX:
                self._send_duplex_state()
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

    def _duplex_state(self):
        from .nd30_duplex import read_choice
        model = self.frame.getController().getModel() if self.frame and self.frame.getController() else None
        if model is None or not model.supportsService("com.sun.star.text.TextDocument"):
            return False, False
        return True, read_choice(model, model.getCurrentController().getViewCursor())[0]  # the page the user is on

    def _send_duplex_state(self, listeners=None):
        from com.sun.star.frame import FeatureStateEvent
        try:
            enabled, checked = self._duplex_state()
        except Exception:  # noqa: BLE001 - unknown state: the item stays usable and unchecked
            log_error(DUPLEX)
            enabled, checked = True, False
        for control, url in listeners or self._duplex_listeners:
            try:
                control.statusChanged(FeatureStateEvent(FeatureURL=url, IsEnabled=enabled, State=bool(checked),
                                                        Requery=False, Source=self))
            except Exception:  # noqa: BLE001 - a menu that went away
                pass

    def addStatusListener(self, control, url):
        if url.Protocol == PROTOCOL and url.Path == DUPLEX:
            self._duplex_listeners.append((control, url))
            self._send_duplex_state([(control, url)])
            return
        if url.Protocol == PROTOCOL and url.Path in ui_language.COMMANDS:
            from com.sun.star.frame import FeatureStateEvent
            enabled, checked = ui_language.status(self.ctx, url.Path)
            control.statusChanged(FeatureStateEvent(FeatureURL=url, IsEnabled=enabled, State=bool(checked),
                                                    Requery=False, Source=self))

    def removeStatusListener(self, control, url):
        """Only the "In hai mặt" listeners are kept; every other status is a fresh snapshot on add."""
        self._duplex_listeners = [(c, u) for c, u in self._duplex_listeners if c != control]
