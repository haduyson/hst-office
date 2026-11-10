# SPDX-License-Identifier: AGPL-3.0-only
"""Tùy chọn ▸ HST Office ▸ Giao diện: "Kiểu biểu tượng" Cổ điển (default) or Hiện đại (nhiều màu) (owner 2026-11-08).

Writes /org.openoffice.Office.Common/Misc/SymbolStyle. The office applies it at once: the change notifies
SvtMiscOptions, which reloads the value and sets the icon theme of every window (svtools miscopt.cxx Notify ->
SetIconTheme), so no restart is needed.
  * Cổ điển: "auto", also an unset value; the office picks the classic pack (LibreOffice Colibre with HST glyphs
    for the commands Colibre does not draw) and its dark variant from the dark mode (hst_classic /
    hst_classic_dark, icon-theme stream). Profiles of earlier versions hold "hst_classic", "hst_classic_dark",
    "hst" or "hst_dark" for Cổ điển; they read back as Cổ điển and are rewritten as "auto" on the next OK.
  * Hiện đại: "hst_modern"; the office picks hst_modern_dark itself while the UI is dark. A pinned
    "hst_modern_dark" of an earlier version reads back as Hiện đại and is rewritten as "hst_modern".
The pack names are the icon-theme stream's; MODERN/CLASSIC below are the only place they appear here.
"""
import os

import unohelper
from com.sun.star.awt import XContainerWindowEventHandler
from com.sun.star.lang import XServiceInfo
from . import diag_log

HANDLER_NAME = "org.hst.office.vi.OptionsAppearance"
CONFIG_PATH = "/org.openoffice.Office.Common/Misc"
CLASSIC = "auto"
CLASSIC_NAMES = ("auto", "", "hst_classic", "hst_classic_dark", "hst", "hst_dark")  # hst*: earlier versions' Cổ điển
MODERN = ("hst_modern", "hst_modern_dark")  # (light, dark)
MODERN_NAMES = MODERN
PREVIEWS = {"modernPreview": "icon-style-modern", "classicPreview": "icon-style-classic"}  # + ".png" / "-dark.png"


def style_of(value):
    """'modern', 'classic' or None (another theme chosen in the core Appearance page), from SymbolStyle (pure)."""
    value = (value or "").strip()
    if value in CLASSIC_NAMES:
        return "classic"
    if value in MODERN_NAMES:
        return "modern"
    return None


def value_for(style):
    """SymbolStyle value for a choice (pure). Always the base style: the office's selector adds "_dark" while the UI is
    dark (vcl HstIconTheme styleForMode), so a later switch to a light UI gets the light pack again."""
    if style == "classic":
        return CLASSIC
    if style == "modern":
        return MODERN[0]
    raise ValueError("unknown icon style: %r" % (style,))


def _node(ctx, writable):
    import uno
    provider = ctx.ServiceManager.createInstanceWithContext("com.sun.star.configuration.ConfigurationProvider", ctx)
    arg = uno.createUnoStruct("com.sun.star.beans.PropertyValue")
    arg.Name, arg.Value = "nodepath", CONFIG_PATH
    kind = "ConfigurationUpdateAccess" if writable else "ConfigurationAccess"
    return provider.createInstanceWithArguments("com.sun.star.configuration." + kind, (arg,))


def current_style(ctx):
    return style_of(_node(ctx, False).getPropertyValue("SymbolStyle"))


def save_style(ctx, style):
    """Write the choice; returns the value written. Nothing is written when it would not change."""
    value = value_for(style)  # also replaces a dark pack pinned by an earlier version
    node = _node(ctx, True)
    if node.getPropertyValue("SymbolStyle") != value:
        node.setPropertyValue("SymbolStyle", value)
        node.commitChanges()
    return value


def preview_file(name, dark):
    """File name of a style preview for the UI mode (pure)."""
    return name + ("-dark" if dark else "") + ".png"


def _dialog_dir():
    return os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "dialogs")


class AppearanceOptionsHandler(unohelper.Base, XServiceInfo, XContainerWindowEventHandler):
    def __init__(self, ctx):
        self.ctx = ctx

    def getImplementationName(self):
        return HANDLER_NAME

    def supportsService(self, name):
        return name in self.getSupportedServiceNames()

    def getSupportedServiceNames(self):
        return (HANDLER_NAME,)

    def getSupportedMethodNames(self):
        return ("external_event",)

    def callHandlerMethod(self, window, event, method):
        if method != "external_event":
            return False
        try:
            if event in ("initialize", "back"):
                self._load(window)
            elif event == "ok":
                self._save(window)
        except Exception:  # noqa: BLE001 - never raise into the options dialog
            diag_log.exception("appearance_options")
        return True

    def _load(self, window):
        style = current_style(self.ctx)
        window.getControl("classic").setState(style == "classic")
        window.getControl("modern").setState(style == "modern")
        from .dialogs import is_dark
        dark = is_dark(self.ctx)
        for name, base in PREVIEWS.items():  # icons drawn by each pack, for the light or the dark UI
            path = os.path.join(_dialog_dir(), preview_file(base, dark))
            control = window.getControl(name)
            if control is None:
                continue
            if os.path.isfile(path):
                import uno
                control.getModel().ImageURL = uno.systemPathToFileUrl(path)
            control.setVisible(os.path.isfile(path))

    def _save(self, window):
        if window.getControl("classic").getState():
            save_style(self.ctx, "classic")
        elif window.getControl("modern").getState():
            save_style(self.ctx, "modern")
