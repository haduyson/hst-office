# SPDX-License-Identifier: AGPL-3.0-only
"""Office side of the update check: settings, proxy, main-thread hand-off, infobar and result dialog.

Settings: /org.openoffice.Office.HSTUpdate in the core configuration (AutoCheck, ManualCheck, CheckIntervalHours,
AllowInstall, Channel, LastCheck, SkippedVersion), read through update_config with every administrator lock applied
(docs/UPDATE_ADMIN.md).
Texts follow the UI language (Vietnamese or English); the other HST commands are always Vietnamese.
"""
import platform
import traceback

import uno
import unohelper
from com.sun.star.awt import XCallback
from com.sun.star.document import XDocumentEventListener

from . import update_config
from . import update_installer as installer
from . import update_logic as logic
from .update_fetch import release_info
from .update_texts import texts

PROTOCOL = "org.hst.office.update:"
INFOBAR_ID = "hst-update-available"
STATE = {"release": None, "pending": None, "listener": None}  # last release found (used by the infobar buttons)


def _node(ctx, path, writable=False):
    provider = ctx.ServiceManager.createInstanceWithContext("com.sun.star.configuration.ConfigurationProvider", ctx)
    arg = uno.createUnoStruct("com.sun.star.beans.PropertyValue")
    arg.Name, arg.Value = "nodepath", path
    kind = "ConfigurationUpdateAccess" if writable else "ConfigurationAccess"
    return provider.createInstanceWithArguments("com.sun.star.configuration." + kind, (arg,))


def settings(ctx):
    """All settings with the administrator locks applied (update_config: core schema, old settings, macOS profile)."""
    return update_config.settings(ctx)


def save(ctx, name, value):
    """Write one per-user setting; False when an administrator locked it or the write failed."""
    return update_config.save(ctx, name, value)


def release_info_for(ctx):
    """release_info() with the release channel the administrator may have set (Channel)."""
    info = release_info()
    return dict(info, channel=logic.effective_channel(info["channel"], settings(ctx)["Channel"]))


def proxy(ctx):
    """Proxy from Tools > Options > Internet > Proxy: None = system/environment, {} = none, else manual HTTPS proxy."""
    try:
        node = _node(ctx, "/org.openoffice.Inet/Settings")
        kind = node.getPropertyValue("ooInetProxyType")
        if kind == 0:
            return {}
        host, port = node.getPropertyValue("ooInetHTTPSProxyName"), node.getPropertyValue("ooInetHTTPSProxyPort")
        if kind == 1 and host:
            return {"https": "%s:%s" % (host, port or 8080)}  # urllib reads host:port as an HTTP proxy
    except Exception:  # noqa: BLE001 - missing keys: fall back to urllib's defaults
        pass
    return None


class _Callback(unohelper.Base, XCallback):
    def __init__(self, fn):
        self.fn = fn

    def notify(self, data):
        try:
            self.fn()
        except Exception:  # noqa: BLE001 - UI on the main thread must never raise into the office
            traceback.print_exc()


def on_main_thread(ctx, fn):
    """Run fn() on the office's main (VCL) thread; worker threads must not touch the UI directly."""
    async_cb = ctx.ServiceManager.createInstanceWithContext("com.sun.star.awt.AsyncCallback", ctx)
    async_cb.addCallback(_Callback(fn), None)


def open_url(ctx, url):
    """Open a validated https link in the system browser; nothing is downloaded by the office itself."""
    if logic.is_safe_link(url):
        shell = ctx.ServiceManager.createInstanceWithContext("com.sun.star.system.SystemShellExecute", ctx)
        shell.execute(url, "", 0)


def release_download(release):
    return logic.download_url(release, logic.platform_key(platform.system(), platform.machine()))


def can_install(ctx, release):
    """"Cập nhật ngay" is offered when the administrator allows it and the signed manifest has an installer for this OS."""
    try:
        return bool(update_config.settings(ctx)["AllowInstall"] and installer.choose_installer(release, logic.platform_key(platform.system(), platform.machine())))
    except Exception:  # noqa: BLE001 - unreadable settings: manual download only
        return False


def show_infobar(frame, release, installed):
    """Infobar on a Writer/Calc/Impress view; False when the frame has none (e.g. the Start Center)."""
    try:
        TEXT = texts()
        controller = frame.getController() if frame else None
        if controller is None or not hasattr(controller, "appendInfobar"):
            return False
        if controller.hasInfobar(INFOBAR_ID):
            controller.removeInfobar(INFOBAR_ID)
        buttons = []
        actions = (("install", "Install"),) if can_install(uno.getComponentContext(), release) else ()
        for key, cmd in actions + (("download", "Download"), ("notes", "Notes"), ("skip", "Skip")):
            pair = uno.createUnoStruct("com.sun.star.beans.StringPair")
            pair.First, pair.Second = TEXT[key], PROTOCOL + cmd
            buttons.append(pair)
        controller.appendInfobar(INFOBAR_ID, TEXT["new"] % release["version"], TEXT["current"] % installed,
                                 0, tuple(buttons), True)  # 0 = InfobarType.INFO
        return True
    except Exception:  # noqa: BLE001 - controllers without infobar support
        traceback.print_exc()
        return False


def remove_infobar(frame):
    try:
        controller = frame.getController()
        if controller.hasInfobar(INFOBAR_ID):
            controller.removeInfobar(INFOBAR_ID)
    except Exception:  # noqa: BLE001 - already closed by the user
        pass


class _FirstView(unohelper.Base, XDocumentEventListener):
    """Shows a pending notification on the first document view opened after a Start Center-only start."""

    def __init__(self, ctx):
        self.ctx = ctx

    def documentEventOccured(self, event):
        if event.EventName != "OnViewCreated" or STATE["pending"] is None:
            return
        try:
            frame = event.Source.getCurrentController().getFrame()
            release, installed = STATE["pending"]
            if show_infobar(frame, release, installed):
                STATE["pending"] = None
                _broadcaster(self.ctx).removeDocumentEventListener(self)
        except Exception:  # noqa: BLE001
            traceback.print_exc()

    def disposing(self, event):
        pass


def _broadcaster(ctx):
    return ctx.getValueByName("/singletons/com.sun.star.frame.theGlobalEventBroadcaster")


def notify(ctx, release, installed):
    """Automatic check: infobar on the current document, else on the next document view that opens."""
    STATE["release"] = release
    frame = ctx.ServiceManager.createInstanceWithContext("com.sun.star.frame.Desktop", ctx).getCurrentFrame()
    if show_infobar(frame, release, installed):
        return
    STATE["pending"] = (release, installed)
    if STATE["listener"] is None:
        STATE["listener"] = _FirstView(ctx)
        _broadcaster(ctx).addDocumentEventListener(STATE["listener"])
