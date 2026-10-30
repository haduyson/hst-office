# SPDX-License-Identifier: AGPL-3.0-only
"""Office side of the update check: settings, proxy, main-thread hand-off, infobar and result dialog.

Settings (schema update.xcs, per user, each property finalizable by an administrator's config layer):
  /org.hasontech.hstoffice.UpdateCheck/AutoCheck       boolean, default true: check at start-up (max. once / 24 h)
  /org.hasontech.hstoffice.UpdateCheck/LastCheck       long, unix seconds of the last automatic attempt
  /org.hasontech.hstoffice.UpdateCheck/SkippedVersion  string, version the user chose to skip
All texts are Vietnamese in every UI language (system/intro content, product policy).
"""
import platform
import traceback

import uno
import unohelper
from com.sun.star.awt import XCallback
from com.sun.star.document import XDocumentEventListener

from . import update_logic as logic

CONFIG_PATH = "/org.hasontech.hstoffice.UpdateCheck"
PROTOCOL = "org.hst.office.update:"
INFOBAR_ID = "hst-update-available"
TITLE = "Kiểm tra cập nhật"
TEXT = {
    "new": "Đã có HST Office %s — bản mới.",
    "current": "Bạn đang dùng %s.",
    "download": "Tải về", "notes": "Xem điểm mới", "skip": "Bỏ qua phiên bản này", "close": "Đóng",
    "uptodate": "Bạn đang dùng phiên bản mới nhất (%s).",
    "failed": "Không kiểm tra được cập nhật. Hãy kiểm tra kết nối mạng rồi thử lại sau.",
}
STATE = {"release": None, "pending": None, "listener": None}  # last release found (used by the infobar buttons)


def _node(ctx, path, writable=False):
    provider = ctx.ServiceManager.createInstanceWithContext("com.sun.star.configuration.ConfigurationProvider", ctx)
    arg = uno.createUnoStruct("com.sun.star.beans.PropertyValue")
    arg.Name, arg.Value = "nodepath", path
    kind = "ConfigurationUpdateAccess" if writable else "ConfigurationAccess"
    return provider.createInstanceWithArguments("com.sun.star.configuration." + kind, (arg,))


def settings(ctx):
    node = _node(ctx, CONFIG_PATH)
    return {name: node.getPropertyValue(name) for name in ("AutoCheck", "LastCheck", "SkippedVersion")}


def save(ctx, name, value):
    """Write one setting; a finalized (admin-locked) property makes this fail, which is logged and ignored."""
    try:
        node = _node(ctx, CONFIG_PATH, True)
        node.setPropertyValue(name, value)
        node.commitChanges()
    except Exception:  # noqa: BLE001 - a failing config write must never disturb the office
        traceback.print_exc()


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


def show_infobar(frame, release, installed):
    """Infobar on a Writer/Calc/Impress view; False when the frame has none (e.g. the Start Center)."""
    try:
        controller = frame.getController() if frame else None
        if controller is None or not hasattr(controller, "appendInfobar"):
            return False
        if controller.hasInfobar(INFOBAR_ID):
            controller.removeInfobar(INFOBAR_ID)
        buttons = []
        for key, cmd in (("download", "Download"), ("notes", "Notes"), ("skip", "Skip")):
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


def show_result(ctx, parent_peer, release, installed, failed):
    """Menu check result: up to date / new version (with the three actions) / could not check."""
    from .dialogs import CANCEL, Dialog
    if failed:
        text = TEXT["failed"]
    elif release is None:
        text = TEXT["uptodate"] % installed
    else:
        text = "%s\n%s" % (TEXT["new"] % release["version"], TEXT["current"] % installed)
    dialog = Dialog(ctx, TITLE, 250, 70)
    dialog.label("message", text, 8, 8, 234, 30, wrap=True)
    x = 8
    if release is not None and not failed:
        STATE["release"] = release
        for name, width, fn in (("download", 40, lambda: open_url(ctx, release_download(release))),
                                ("notes", 52, lambda: open_url(ctx, release["notes"])),
                                ("skip", 76, lambda: save(ctx, "SkippedVersion", release["version"]))):
            dialog.button(name, TEXT[name], x, 48, width, callback=(lambda f=fn: (f(), dialog.end(1))),
                          default=(name == "download"))
            x += width + 4
    dialog.button("close", TEXT["close"], 202, 48, 40, kind=CANCEL, default=release is None or failed)
    dialog.execute(parent_peer)

