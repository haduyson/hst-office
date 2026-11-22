# SPDX-License-Identifier: LicenseRef-HST-Proprietary
# Copyright (C) 2026 HASON TECH
"""macOS only: a dialog of the office itself (Format > Character, Tools > Options...) follows a document opened in
native full screen instead of staying in the Space the user left.

With the dialog's document in native full screen, a document opened while the dialog runs (Finder, a launcher, the
Dock) shows in a full screen Space of its own. The dialog stays behind with its document and still blocks it: the
office looks frozen (probe: Format > Character, then a new document, dialog off screen). The extension's own dialogs
move themselves (dialog_on_screen.watch_new_documents); for the others, once the new document's window is shown, the
dialog's window is put over it (mac_native_window.adopt_dialogs, looked for a few times while the Space changes), so
the user can finish or cancel it there. Started once per office process (start); Windows and Linux watch nothing.
"""
import sys
import threading

import unohelper
from com.sun.star.awt import XCallback

from . import diag_log

EVENTS = ("OnNew", "OnLoad", "OnViewCreated")
# seconds after a new document's event at which stranded dialogs are looked for: the Space animation that takes the
# user to the new document's Space ends at an unknown time (once moved, later looks find nothing left)
DELAYS = (1.0, 2.5, 5.0)
_STATE = {"listener": None}


def _document_window(event):
    try:
        return event.Source.getCurrentController().getFrame().getContainerWindow()
    except Exception:  # noqa: BLE001 - no view yet (OnNew/OnLoad before OnViewCreated) or closed
        return None


class _Adopt(unohelper.Base, XCallback):
    """Main thread: dialogs stranded in another full screen Space move onto `window`."""

    def __init__(self, window):
        self.window = window

    def notify(self, data):
        adopt(self.window)


def adopt(window):
    """Move stranded office dialogs onto `window` unless one of the extension's dialogs runs (it moves itself)."""
    from . import dialog_registry, mac_native_window
    try:
        if dialog_registry.OPEN or not window.isVisible():
            return 0
        moved = mac_native_window.adopt_dialogs(window)
        if moved:
            diag_log.info("dialog", "%d office dialog(s) moved onto a new full screen document" % moved)
        return moved
    except Exception:  # noqa: BLE001 - AppKit not reachable or a window closed meanwhile: nothing moved
        diag_log.exception("mac_full_screen_dialogs")
        return 0


def _post(ctx, callback):
    ctx.ServiceManager.createInstanceWithContext("com.sun.star.awt.AsyncCallback", ctx).addCallback(callback, None)


def _daemon_timer(delay, action):
    t = threading.Timer(delay, action)
    t.daemon = True
    t.start()


def on_document(ctx, event, timer=None):
    """A document event: for an opened document, look for stranded dialogs once its window has settled."""
    if getattr(event, "EventName", "") not in EVENTS:
        return
    window = _document_window(event)
    if window is not None:
        for delay in DELAYS:
            (timer or _daemon_timer)(delay, lambda: _post(ctx, _Adopt(window)))


def start(ctx, platform=None, timer=None):
    """Watch opened documents for the rest of the process (macOS only, once). Returns True when watching."""
    if (platform or sys.platform) != "darwin":
        return False
    if _STATE["listener"] is not None:
        return True
    from com.sun.star.document import XDocumentEventListener

    class _Opened(unohelper.Base, XDocumentEventListener):
        def documentEventOccured(self, event):  # noqa: N802 - UNO method name (sic)
            try:
                on_document(ctx, event, timer)
            except Exception:  # noqa: BLE001 - never raise into the office's event broadcast
                diag_log.exception("mac_full_screen_dialogs")

        def disposing(self, event):
            pass
    try:
        listener = _Opened()
        ctx.getValueByName("/singletons/com.sun.star.frame.theGlobalEventBroadcaster").addDocumentEventListener(listener)
    except Exception:  # noqa: BLE001 - no broadcaster: nothing to watch
        diag_log.exception("mac_full_screen_dialogs")
        return False
    _STATE["listener"] = listener
    return True
