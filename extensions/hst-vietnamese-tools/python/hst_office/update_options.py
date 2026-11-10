# SPDX-License-Identifier: AGPL-3.0-only
"""Tùy chọn ▸ HST Office ▸ Cập nhật (OptionsDialog.xcu, dialogs/Update.xdl): "Gửi mã máy ẩn danh khi kiểm tra cập nhật".

Reads and writes SendInstallId through update_config, so an administrator lock (docs/UPDATE_ADMIN.md) shows the box
greyed out with the value the administrator set, and nothing is written. Saved on OK; Cancel keeps the old value.
"""
import unohelper
from com.sun.star.awt import XContainerWindowEventHandler
from com.sun.star.lang import XServiceInfo

from . import diag_log
from . import update_config
from .update_install_id import SEND_KEY, set_sending

HANDLER_NAME = "org.hst.office.vi.OptionsUpdate"


def page_state(values, locked):
    """Pure: (ticked, editable) of the checkbox from the resolved settings."""
    return bool(values[SEND_KEY]), SEND_KEY not in locked


def value_to_save(ticked, values, locked):
    """Pure: the SendInstallId to write on OK, or None when it is locked or unchanged."""
    ticked = bool(ticked)
    if SEND_KEY in locked or ticked == bool(values[SEND_KEY]):
        return None
    return ticked


class UpdateOptionsHandler(unohelper.Base, XServiceInfo, XContainerWindowEventHandler):
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
            diag_log.exception("update_options")
        return True

    def _load(self, window):
        ticked, editable = page_state(*update_config.load(self.ctx))
        box = window.getControl("sendInstallId")
        box.setState(1 if ticked else 0)
        box.setEnable(editable)
        window.getControl("locked").setVisible(not editable)

    def _save(self, window):
        value = value_to_save(window.getControl("sendInstallId").getState() == 1, *update_config.load(self.ctx))
        if value is not None and update_config.save(self.ctx, SEND_KEY, value):
            set_sending(value)
