# SPDX-License-Identifier: AGPL-3.0-only
"""HST Công thức "tự chuyển khi mở" (Tùy chọn ▸ HST Office ▸ Công thức; off by default): after a document is
opened, turn its remaining MathType equations into formulas (job on OnLoad). At OnViewCreated it also attaches
the double-click question of formula_click to the new view (always: the option only decides "on open").

The .doc/.xls/.ppt and .docx/.rtf imports convert MathType 4-7 equations themselves when this option is on
(hst-mathtype5-import-routing.patch); this job covers the other formats (.xlsx, .pptx, ODF files with MathType
objects). It asks nothing; an equation that cannot be read stays as it was. The open document looks as loaded:
no undo step and no modified flag. Registered in Jobs.xcu and hst_office_component.SERVICES."""
import unohelper
from com.sun.star.lang import XServiceInfo
from com.sun.star.task import XJob

from . import diag_log

JOB_NAME = "org.hst.office.vi.FormulaOpenJob"
OPTION_PATH = "/org.openoffice.Office.Common/Filter/Microsoft/Import"
OPTION = "MathType5ToMath"


def _argument(values, name):
    return next((v.Value for v in values or () if v.Name == name), None)


def _config(ctx, update=False):
    from com.sun.star.beans import PropertyValue
    provider = ctx.ServiceManager.createInstanceWithContext("com.sun.star.configuration.ConfigurationProvider", ctx)
    path = PropertyValue()
    path.Name, path.Value = "nodepath", OPTION_PATH
    kind = "ConfigurationUpdateAccess" if update else "ConfigurationAccess"
    return provider.createInstanceWithArguments("com.sun.star.configuration." + kind, (path,))


def enabled(ctx):
    """The user's "tự chuyển khi mở" choice (False when the option cannot be read)."""
    try:
        return bool(_config(ctx).getPropertyValue(OPTION))
    except Exception:  # noqa: BLE001 - an office without the option never converts on open
        return False


def set_enabled(ctx, value):
    access = _config(ctx, update=True)
    access.setPropertyValue(OPTION, bool(value))
    access.commitChanges()


def convert_on_open(ctx, doc):
    """Convert, then leave no undo step and no modified flag; returns the number converted."""
    from . import formula_convert
    manager = doc.getUndoManager()
    was_modified = doc.isModified()
    manager.lock()
    try:
        done = 0
        for container, obj in formula_convert.candidates(doc):
            if formula_convert.convert_one(ctx, doc, container, obj):
                done += 1
    finally:
        manager.unlock()
    if done and not was_modified:
        doc.setModified(False)
    return done


class FormulaOpenJob(unohelper.Base, XServiceInfo, XJob):
    def __init__(self, ctx):
        self.ctx = ctx

    def getImplementationName(self):
        return JOB_NAME

    def supportsService(self, name):
        return name in self.getSupportedServiceNames()

    def getSupportedServiceNames(self):
        return ("com.sun.star.task.Job",)

    def execute(self, arguments):
        try:
            environment = _argument(arguments, "Environment")
            model, event = _argument(environment, "Model"), _argument(environment, "EventName")
            if event == "OnViewCreated" and model is not None and hasattr(model, "getCurrentController"):
                from . import formula_click
                formula_click.attach(self.ctx, model.getCurrentController())
            elif event == "OnLoad" and model is not None and enabled(self.ctx):
                if hasattr(model, "getUndoManager") and not model.supportsService("com.sun.star.formula.FormulaProperties"):
                    convert_on_open(self.ctx, model)
        except Exception:  # noqa: BLE001 - opening a document must never fail because of this
            diag_log.exception("formula_open_job")
