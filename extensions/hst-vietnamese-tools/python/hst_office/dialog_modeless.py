# SPDX-License-Identifier: LicenseRef-HST-Proprietary
# Copyright (C) 2026 HASON TECH
"""Show a dialogs.Dialog without a modal loop (the update pop-up): the other windows keep working."""
import unohelper
from com.sun.star.awt import XTopWindowListener


class _Closing(unohelper.Base, XTopWindowListener):
    """The title bar's close button."""

    def __init__(self, callback):
        self.callback = callback

    def windowClosing(self, event):
        self.callback()

    def windowOpened(self, event):
        pass

    def windowClosed(self, event):
        pass

    def windowMinimized(self, event):
        pass

    def windowNormalized(self, event):
        pass

    def windowActivated(self, event):
        pass

    def windowDeactivated(self, event):
        pass

    def disposing(self, event):
        pass


def open_modeless(dialog, parent_peer=None, on_close=None):
    """Show `dialog` (a dialogs.Dialog): its buttons' callbacks run on clicks, on_close (default: close) when the
    title bar's close button is used. Returns the listener, which the caller keeps alive with the dialog."""
    toolkit = dialog.smgr.createInstanceWithContext("com.sun.star.awt.Toolkit", dialog.ctx)
    dialog.dialog.setVisible(False)
    dialog.dialog.createPeer(toolkit, parent_peer)
    for name, listener in dialog._listeners:  # what Dialog.execute adds before its modal loop
        dialog.dialog.getControl(name).addActionListener(listener)
    closing = _Closing(on_close or (lambda: close(dialog)))
    dialog.dialog.addTopWindowListener(closing)
    dialog.dialog.setVisible(True)
    return closing


def close(dialog):
    try:
        dialog.dialog.setVisible(False)
        dialog.dialog.dispose()
    except Exception:  # noqa: BLE001 - already disposed (closed twice)
        pass
