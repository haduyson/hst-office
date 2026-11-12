# SPDX-License-Identifier: AGPL-3.0-only
"""Tùy chọn ▸ HST Office ▸ Phiên bản trước (OptionsDialog.xcu, dialogs/PreviousVersions.xdl).

"Lưu phiên bản trước khi ghi đè tệp" is read and written through version_config, so an administrator lock shows the
box greyed out with the locked value and nothing is written; saved on OK, Cancel keeps the old value. "Xóa toàn bộ
phiên bản đã lưu" asks on the page itself (confirmText, Xóa / Không xóa) and clears at once: it is an action, not a
setting, so OK/Cancel do not undo it. Clearing is allowed even when the setting is locked: the copies are the user's.
"""
import unohelper
from com.sun.star.awt import XContainerWindowEventHandler
from com.sun.star.lang import XServiceInfo

from . import diag_log
from . import version_texts as T

HANDLER_NAME = "org.hst.office.vi.OptionsPreviousVersions"
METHODS = ("external_event", "clearVersions", "confirmClear", "cancelClear")
CONFIRM_CONTROLS = ("confirmText", "confirmClear", "cancelClear")


def value_to_save(ticked, enabled, locked):
    """Pure: the value to write on OK, or None when it is locked or unchanged."""
    ticked = bool(ticked)
    return None if locked or ticked == bool(enabled) else ticked


class PreviousVersionsOptionsHandler(unohelper.Base, XServiceInfo, XContainerWindowEventHandler):
    def __init__(self, ctx):
        self.ctx = ctx

    def getImplementationName(self):
        return HANDLER_NAME

    def supportsService(self, name):
        return name in self.getSupportedServiceNames()

    def getSupportedServiceNames(self):
        return (HANDLER_NAME,)

    def getSupportedMethodNames(self):
        return METHODS

    def callHandlerMethod(self, window, event, method):
        if method not in METHODS:
            return False
        try:
            if method == "external_event":
                if event in ("initialize", "back"):
                    self._load(window)
                elif event == "ok":
                    self._save(window)
            elif method == "clearVersions":
                self._confirming(window, True)
            elif method == "cancelClear":
                self._confirming(window, False)
            elif method == "confirmClear":
                self._clear(window)
        except Exception:  # noqa: BLE001 - never raise into the options dialog
            diag_log.exception("version_options")
        return True

    def _store(self):
        from . import version_config
        return version_config.store(self.ctx)

    def _confirming(self, window, shown):
        for name in CONFIRM_CONTROLS:
            window.getControl(name).setVisible(shown)
        window.getControl("clear").setEnable(not shown)

    def _show_usage(self, window, text=None):
        if text is None:
            try:
                text = T.usage_label(*self._store().usage())
            except Exception:  # noqa: BLE001 - a busy or unreadable store: the page still opens
                diag_log.exception("version_options")
                text = ""
        window.getControl("usage").setText(text)

    def _load(self, window):
        from . import version_config
        enabled, locked = version_config.load(self.ctx)
        box = window.getControl("enabled")
        box.setState(1 if enabled else 0)
        box.setEnable(not locked)
        window.getControl("locked").setVisible(locked)
        window.getControl("confirmText").setText(T.CLEAR_CONFIRM)
        self._confirming(window, False)
        self._show_usage(window)

    def _save(self, window):
        from . import version_config
        enabled, locked = version_config.load(self.ctx)
        value = value_to_save(window.getControl("enabled").getState() == 1, enabled, locked)
        if value is not None:
            version_config.save(self.ctx, value)

    def _clear(self, window):
        from .version_store import StoreBusy
        self._confirming(window, False)
        try:
            count = self._store().clear()
        except StoreBusy:
            return self._show_usage(window, T.CLEAR_FAILED)
        diag_log.info("previous_versions", "cleared %d stored versions" % count)
        self._show_usage(window, T.CLEARED % count)
