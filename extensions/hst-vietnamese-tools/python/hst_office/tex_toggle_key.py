# SPDX-License-Identifier: AGPL-3.0-only
"""Chuyển TeX ⇄ công thức on Alt+\\ in HST Writer, the key MathType's TeX toggle uses in Word.

The office's shortcut table cannot hold this key: it has no key code for the backslash (only for keys such as
[ ] ; ' ` #), so no shortcut uses it and none can. A key handler on each Writer view (XUserInputInterception,
attached by formula_open_job at OnViewCreated) watches for the character "\\" typed with Alt alone, and runs the
command after the event has been consumed (com.sun.star.awt.AsyncCallback). AltGr+\\ on layouts that type the
backslash with AltGr is Ctrl+Alt to the office and is left alone, as is every other key. macOS: Option+\\ types
« there, so the key handler never sees a backslash and the command stays on the menu."""
import unohelper
from com.sun.star.awt import XCallback, XKeyHandler

from . import diag_log

COMMAND = "org.hst.office.vi:TexToggle"
ALT = 4  # com.sun.star.awt.KeyModifier.MOD2
MODIFIERS = 1 | 2 | 4 | 8  # SHIFT, MOD1, MOD2, MOD3


def is_toggle_key(event):
    return event.KeyChar == "\\" and (event.Modifiers & MODIFIERS) == ALT


class _RunLater(unohelper.Base, XCallback):
    def __init__(self, frame):
        self.frame = frame

    def notify(self, data):
        try:
            import uno
            url = uno.createUnoStruct("com.sun.star.util.URL")
            url.Complete, url.Protocol, url.Path = COMMAND, "org.hst.office.vi:", "TexToggle"
            dispatcher = self.frame.queryDispatch(url, "", 0)
            if dispatcher is not None:
                dispatcher.dispatch(url, ())
        except Exception:  # noqa: BLE001 - never raise into the office's event loop
            diag_log.exception("tex_toggle_key")


class TexToggleKeyHandler(unohelper.Base, XKeyHandler):
    def __init__(self, ctx, controller):
        self.ctx, self.controller = ctx, controller

    def keyPressed(self, event):
        try:
            if not is_toggle_key(event) or self.controller is None:
                return False
            callback = self.ctx.ServiceManager.createInstanceWithContext("com.sun.star.awt.AsyncCallback", self.ctx)
            callback.addCallback(_RunLater(self.controller.getFrame()), None)
            return True
        except Exception:  # noqa: BLE001 - typing must keep working whatever happens here
            diag_log.exception("tex_toggle_key")
            return False

    def keyReleased(self, event):
        return is_toggle_key(event)

    def disposing(self, source):
        self.controller = None


def attach(ctx, controller):
    """Watch for Alt+\\ on a Writer view; other views are left alone."""
    model = controller.getModel() if controller is not None else None
    if (model is not None and model.supportsService("com.sun.star.text.TextDocument")
            and hasattr(controller, "addKeyHandler")):
        controller.addKeyHandler(TexToggleKeyHandler(ctx, controller))
