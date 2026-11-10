# SPDX-License-Identifier: AGPL-3.0-only
"""Event handler of the options page Tùy chọn ▸ HST Office ▸ Mở tài liệu (OptionsDialog.xcu, dialogs/DefaultApps.xdl).

The page stores nothing (OK/Cancel have nothing to save). "defaultApps" runs the same action as the HST menu item;
"appShortcuts" adds HST Writer, HST Sheets and HST Slides to the Dock (macOS) or the desktop (Linux), and the section
is labelled for this OS, or hidden, when the page opens (app_shortcuts_ui).
"""

import unohelper
from com.sun.star.awt import XContainerWindowEventHandler
from com.sun.star.lang import XServiceInfo
from . import diag_log

HANDLER_NAME = "org.hst.office.vi.OptionsPage"
METHODS = ("external_event", "defaultApps", "appShortcuts")


class OptionsPageHandler(unohelper.Base, XServiceInfo, XContainerWindowEventHandler):
    def __init__(self, ctx):
        self.ctx = ctx

    def getImplementationName(self):
        return HANDLER_NAME

    def supportsService(self, name):
        return name in self.getSupportedServiceNames()

    def getSupportedServiceNames(self):
        return (HANDLER_NAME,)

    def getSupportedMethodNames(self):
        return METHODS

    def callHandlerMethod(self, window, event, method):
        if method == "defaultApps":
            try:
                from .default_apps import run_from_menu
                run_from_menu(self.ctx, window.getPeer() if window is not None else None)
            except Exception:  # noqa: BLE001 - never raise into the options dialog
                diag_log.exception("options_page")
            return True
        if method == "appShortcuts":
            try:
                from .app_shortcuts_ui import run
                run(self.ctx, window.getPeer() if window is not None else None)
            except Exception:  # noqa: BLE001 - never raise into the options dialog
                diag_log.exception("options_page")
            return True
        if method == "external_event" and event == "initialize" and window is not None:
            try:
                from .app_shortcuts_ui import configure_page
                configure_page(window)
            except Exception:  # noqa: BLE001 - the page still opens with its default labels
                diag_log.exception("options_page")
        return method == "external_event"  # ok / back / initialize: nothing to load or save
