# SPDX-License-Identifier: AGPL-3.0-only
"""Event handler of the options page Tùy chọn ▸ HST Office ▸ Mở tài liệu (OptionsDialog.xcu, dialogs/DefaultApps.xdl).

The page stores nothing (OK/Cancel have nothing to save); its one button runs the same action as the HST menu item.
"""
import traceback

import unohelper
from com.sun.star.awt import XContainerWindowEventHandler
from com.sun.star.lang import XServiceInfo

HANDLER_NAME = "org.hst.office.vi.OptionsPage"
METHODS = ("external_event", "defaultApps")


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
                traceback.print_exc()
            return True
        return method == "external_event"  # ok / back / initialize: nothing to load or save
