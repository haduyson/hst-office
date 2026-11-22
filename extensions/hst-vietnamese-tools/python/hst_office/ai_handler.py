# SPDX-License-Identifier: LicenseRef-HST-Proprietary
# Copyright (C) 2026 HASON TECH
"""ProtocolHandler of the Trợ lý AI: org.hst.office.ai:<Command>.

Commands: FormulaWrite, FormulaExplain (HST Sheets), Writing (every app with text), Help (every app) and Options
(opens Tùy chọn ▸ HST Office ▸ Trợ lý AI). Everything but Options is greyed out while the assistant is off (the
default) or no provider is chosen; the options page re-broadcasts the state after OK. The ribbon's "AI" group of
the "Phần mở rộng" tab dispatches these same URLs.
"""
import weakref

import unohelper
from com.sun.star.frame import XDispatch, XDispatchProvider
from com.sun.star.lang import XInitialization, XServiceInfo

IMPLEMENTATION_NAME = "org.hst.office.vi.AiDispatchProvider"
PROTOCOL = "org.hst.office.ai:"
EXTENSION_ID = "vn.hasontech.hst.vietnamese-tools"
ACTION_COMMANDS = {"FormulaWrite": ("calc",), "FormulaExplain": ("calc",),
                   "Writing": ("writer", "calc", "impress", "draw"), "Help": ("writer", "calc", "impress", "draw")}
COMMANDS = frozenset(ACTION_COMMANDS) | {"Options"}
_HANDLERS = weakref.WeakSet()


def command_enabled(command, doc_kind, active):
    """Pure: Options always; an action only when the assistant is on with a provider, in an app it serves."""
    if command == "Options":
        return True
    return bool(active) and doc_kind in ACTION_COMMANDS.get(command, ())


def broadcast_all():
    """After the options changed: every handler sends its commands' state again."""
    for handler in list(_HANDLERS):
        handler.broadcast()


def open_options(ctx, frame):
    """Tools ▸ Options with the Trợ lý AI page selected. OptionsPageURL must equal the leaf's URL as the options
    dialog expands it (%origin% = the package URL, e.g. file:///…/program/../share/extensions/…, not normalized),
    so it is built from the package information provider rather than from this file's path."""
    from com.sun.star.beans import PropertyValue
    provider = ctx.getValueByName("/singletons/com.sun.star.deployment.PackageInformationProvider")
    page = provider.getPackageLocation(EXTENSION_ID) + "/dialogs/AI.xdl"
    helper = ctx.ServiceManager.createInstanceWithContext("com.sun.star.frame.DispatchHelper", ctx)
    helper.executeDispatch(frame, ".uno:OptionsTreeDialog", "", 0, (PropertyValue(Name="OptionsPageURL", Value=page),))


class AiHandler(unohelper.Base, XServiceInfo, XInitialization, XDispatchProvider, XDispatch):
    def __init__(self, ctx, *args):
        self.ctx, self.frame, self.listeners = ctx, None, []
        _HANDLERS.add(self)

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
        return self if url.Protocol == PROTOCOL and url.Path in COMMANDS else None

    def queryDispatches(self, requests):
        return tuple(self.queryDispatch(r.FeatureURL, r.FrameName, r.SearchFlags) for r in requests)

    def _kind(self):
        from .ai_document import kind
        controller = self.frame.getController() if self.frame else None
        return kind(controller.getModel() if controller else None)

    def dispatch(self, url, arguments):
        try:
            if url.Path == "Options":
                return open_options(self.ctx, self.frame)
            from . import ai_config
            active = ai_config.active_provider(self.ctx)
            if not command_enabled(url.Path, self._kind(), active):
                from .ai_texts import TEXT
                from .dialogs import message_box
                peer = self.frame.getContainerWindow() if self.frame else None
                if message_box(self.ctx, peer, TEXT["title"], TEXT["off"], ask=True,
                               buttons=(TEXT["open_options"], TEXT["close"])):
                    open_options(self.ctx, self.frame)
                return
            self._run(url.Path, *active)
        except Exception:  # noqa: BLE001 - never raise into the office UI thread
            from .diag_log import exception
            exception("ai " + url.Path)

    def _run(self, action, provider, model):
        from . import ai_dialog
        from .ai_keystore import Keystore
        from .office_proxy import proxy
        from .update_fetch import release_info
        key = Keystore(self.ctx).get(provider)
        ai_dialog.run(self.ctx, self.frame, action, provider, model, key, release_info()["release"], proxy(self.ctx))

    def _send(self, control, url):
        from com.sun.star.frame import FeatureStateEvent
        try:
            active = None
            if url.Path != "Options":
                from . import ai_config
                active = ai_config.active_provider(self.ctx)
            enabled = command_enabled(url.Path, self._kind(), active)
            control.statusChanged(FeatureStateEvent(FeatureURL=url, IsEnabled=enabled, Requery=False, Source=self))
        except Exception:  # noqa: BLE001 - a control that went away, or a closing document
            pass

    def broadcast(self):
        for control, url in list(self.listeners):
            self._send(control, url)

    def addStatusListener(self, control, url):
        self.listeners.append((control, url))
        self._send(control, url)

    def removeStatusListener(self, control, url):
        self.listeners = [(c, u) for c, u in self.listeners if not (c == control and u.Complete == url.Complete)]
