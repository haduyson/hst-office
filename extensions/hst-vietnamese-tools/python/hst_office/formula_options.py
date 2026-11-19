# SPDX-License-Identifier: AGPL-3.0-only
"""Tùy chọn ▸ HST Office ▸ Công thức (OptionsDialog.xcu, dialogs/Formula.xdl): "tự chuyển khi mở", the office option
MathType5ToMath (off by default) read by the imports and by formula_open_job. Saved on OK; Cancel keeps it."""
import unohelper
from com.sun.star.awt import XContainerWindowEventHandler
from com.sun.star.lang import XServiceInfo

from . import diag_log

HANDLER_NAME = "org.hst.office.vi.OptionsFormula"
METHODS = ("external_event",)


class FormulaOptionsHandler(unohelper.Base, XServiceInfo, XContainerWindowEventHandler):
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
            from . import formula_open_job
            box = window.getControl("convertOnOpen")
            if event in ("initialize", "back"):
                box.setState(1 if formula_open_job.enabled(self.ctx) else 0)
            elif event == "ok":
                formula_open_job.set_enabled(self.ctx, box.getState() == 1)
        except Exception:  # noqa: BLE001 - never raise into the options dialog
            diag_log.exception("formula_options")
        return True
