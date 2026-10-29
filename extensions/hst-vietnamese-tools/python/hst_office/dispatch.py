# SPDX-License-Identifier: AGPL-3.0-only
"""ProtocolHandler for the org.hst.office.vi: command URLs used by the HST menu and toolbar."""
import traceback

import unohelper
from com.sun.star.frame import XDispatch, XDispatchProvider
from com.sun.star.lang import XInitialization, XServiceInfo

from .actions import COMMANDS, Host
from .data_files import load_locale

IMPLEMENTATION_NAME = "org.hst.office.vi.DispatchProvider"
PROTOCOL = "org.hst.office.vi:"
SHOW_SOLUTIONS = "ShowSolutions"  # needs no document, so it also works in the Start Center


def ui_language(ctx):
    """UI language code from the office configuration (falls back to English)."""
    try:
        provider = ctx.ServiceManager.createInstanceWithContext("com.sun.star.configuration.ConfigurationProvider", ctx)
        import uno
        arg = uno.createUnoStruct("com.sun.star.beans.PropertyValue")
        arg.Name, arg.Value = "nodepath", "/org.openoffice.Setup/L10N"
        node = provider.createInstanceWithArguments("com.sun.star.configuration.ConfigurationAccess", (arg,))
        return node.getByName("ooLocale")
    except Exception:  # noqa: BLE001 - language is cosmetic; English is a safe default
        return "en"


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
        return self if url.Protocol == PROTOCOL and (url.Path in COMMANDS or url.Path == SHOW_SOLUTIONS) else None

    def queryDispatches(self, requests):
        return tuple(self.queryDispatch(r.FeatureURL, r.FrameName, r.SearchFlags) for r in requests)

    def dispatch(self, url, arguments):
        if url.Path == SHOW_SOLUTIONS:
            return self._show_solutions()
        try:
            COMMANDS[url.Path](Host(self.ctx, self.frame, load_locale(ui_language(self.ctx))))
        except Exception as exc:  # noqa: BLE001 - never fail silently inside the office UI thread
            traceback.print_exc()
            try:
                Host(self.ctx, self.frame, load_locale("en")).say("%s: %s" % (type(exc).__name__, exc), error=True)
            except Exception:  # noqa: BLE001
                pass

    def _show_solutions(self):
        try:
            from .welcome_job import show_welcome
            peer = self.frame.getContainerWindow() if self.frame else None
            show_welcome(self.ctx, "menu", peer, load_locale(ui_language(self.ctx)))
        except Exception:  # noqa: BLE001 - report instead of failing silently inside the UI thread
            traceback.print_exc()

    def addStatusListener(self, control, url):
        pass

    def removeStatusListener(self, control, url):
        pass
