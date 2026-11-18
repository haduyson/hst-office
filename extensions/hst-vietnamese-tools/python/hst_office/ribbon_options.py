# SPDX-License-Identifier: AGPL-3.0-only
"""Tùy chọn ▸ HST Office ▸ Ribbon (OptionsDialog.xcu, dialogs/Ribbon.xdl).

The ribbon lives in the core: this page talks to its UNO service vn.hasontech.hst.RibbonCustomization (an XJob whose
"Action" argument names what to do, see hst/ribbon/lo/ribbon-custom-service.cxx in the core patches).

- "Tùy chỉnh ribbon" opens the core's dialog for the current document's ribbon at once (it saves on its own OK).
- "Hiện thẻ Sử dụng gần đây" is read when the page opens and written on OK; Cancel keeps the old value. Turning it
  off stops recording and hides the tab; the history stays until "Xóa lịch sử".
- "Xóa lịch sử" clears every app's command history at once: an action, not a setting, so OK/Cancel do not undo it.
A core without the service (an older build) shows the page with its controls greyed out and a note.
"""
import unohelper
from com.sun.star.awt import XContainerWindowEventHandler
from com.sun.star.lang import XServiceInfo

from . import diag_log

HANDLER_NAME = "org.hst.office.vi.OptionsRibbon"
CORE_SERVICE = "vn.hasontech.hst.RibbonCustomization"
METHODS = ("external_event", "customize", "clearHistory")
CONTROLS = ("customize", "recentEnabled", "clearHistory")

CLEARED = "Đã xóa lịch sử dùng lệnh."
CLEAR_FAILED = "Không xóa được lịch sử dùng lệnh."
UNAVAILABLE = "Bản HST Office này chưa có tùy chỉnh ribbon."


def job_arguments(action, **values):
    """Pure: the (name, value) pairs of an XJob call, "Action" first, the others by name."""
    return [("Action", action)] + sorted(values.items())


def value_to_save(ticked, enabled):
    """Pure: the switch to write on OK, or None when it is unchanged."""
    ticked = bool(ticked)
    return None if ticked == bool(enabled) else ticked


def _named_values(pairs):
    import uno
    values = []
    for name, value in pairs:
        named = uno.createUnoStruct("com.sun.star.beans.NamedValue")
        named.Name, named.Value = name, value
        values.append(named)
    return tuple(values)


class RibbonOptionsHandler(unohelper.Base, XServiceInfo, XContainerWindowEventHandler):
    def __init__(self, ctx, to_uno=_named_values):
        self.ctx = ctx
        self._to_uno = to_uno
        self._loaded = None  # the switch as the page found it

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
            elif method == "customize":
                self._call("customize", ParentWindow=window.getPeer())
            elif method == "clearHistory":
                cleared = self._call("clearHistory")
                window.getControl("status").setText(CLEARED if cleared else CLEAR_FAILED)
        except Exception:  # noqa: BLE001 - never raise into the options dialog
            diag_log.exception("ribbon_options")
        return True

    def _service(self):
        try:
            return self.ctx.ServiceManager.createInstanceWithContext(CORE_SERVICE, self.ctx)
        except Exception:  # noqa: BLE001 - not registered: an older core
            return None

    def _call(self, action, **values):
        """The service's answer, or None when the core has no such service."""
        service = self._service()
        if service is None:
            return None
        return service.execute(self._to_uno(job_arguments(action, **values)))

    def _load(self, window):
        enabled = self._call("getRecentEnabled")
        available = enabled is not None
        for name in CONTROLS:
            window.getControl(name).setEnable(available)
        window.getControl("status").setText("" if available else UNAVAILABLE)
        self._loaded = bool(enabled) if available else None
        window.getControl("recentEnabled").setState(1 if self._loaded or not available else 0)

    def _save(self, window):
        if self._loaded is None:
            return
        value = value_to_save(window.getControl("recentEnabled").getState() == 1, self._loaded)
        if value is not None:
            self._call("setRecentEnabled", Enabled=value)
            self._loaded = value
