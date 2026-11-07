# SPDX-License-Identifier: AGPL-3.0-only
"""Tùy chọn ▸ HST Office ▸ Giao diện: "Kiểu biểu tượng" Hiện đại (nhiều màu, default) or Cổ điển (owner 2026-11-07).

Writes /org.openoffice.Office.Common/Misc/SymbolStyle. The office applies it at once: the change notifies
SvtMiscOptions, which reloads the value and sets the icon theme of every window (svtools miscopt.cxx Notify ->
SetIconTheme), so no restart is needed.
  * Hiện đại: "auto"; the office picks the modern pack and its dark variant from the dark mode (hst_modern /
    hst_modern_dark, icon-theme stream).
  * Cổ điển: "hst_classic" or "hst_classic_dark" (LibreOffice Colibre with HST glyphs for the commands Colibre does not
    draw), chosen from the current dark mode when the page is confirmed. Profiles of earlier versions hold "hst" /
    "hst_dark" for Cổ điển; they read back as Cổ điển and the office maps them to the same packs.
The pack names are the icon-theme stream's; MODERN/CLASSIC below are the only place they appear here.
"""
import os
import traceback

import unohelper
from com.sun.star.awt import XContainerWindowEventHandler
from com.sun.star.lang import XServiceInfo

HANDLER_NAME = "org.hst.office.vi.OptionsAppearance"
CONFIG_PATH = "/org.openoffice.Office.Common/Misc"
MODERN = "auto"
MODERN_NAMES = ("auto", "", "hst_modern", "hst_modern_dark")
CLASSIC = ("hst_classic", "hst_classic_dark")  # (light, dark)
CLASSIC_NAMES = CLASSIC + ("hst", "hst_dark")  # "hst" / "hst_dark": the Cổ điển value of earlier versions
PREVIEWS = {"modernPreview": "icon-style-modern", "classicPreview": "icon-style-classic"}  # + ".png" / "-dark.png"


def style_of(value):
    """'modern', 'classic' or None (another theme chosen in the core Appearance page), from SymbolStyle (pure)."""
    value = (value or "").strip()
    if value in MODERN_NAMES:
        return "modern"
    if value in CLASSIC_NAMES:
        return "classic"
    return None


def value_for(style, dark):
    """SymbolStyle value for a choice (pure)."""
    if style == "modern":
        return MODERN
    if style == "classic":
        return CLASSIC[1 if dark else 0]
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
    from .dialogs import is_dark
    value = value_for(style, is_dark(ctx))
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
            traceback.print_exc()
        return True

    def _load(self, window):
        style = current_style(self.ctx)
        window.getControl("modern").setState(style == "modern")
        window.getControl("classic").setState(style == "classic")
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
        if window.getControl("modern").getState():
            save_style(self.ctx, "modern")
        elif window.getControl("classic").getState():
            save_style(self.ctx, "classic")
