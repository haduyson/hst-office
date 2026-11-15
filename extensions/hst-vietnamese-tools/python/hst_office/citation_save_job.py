# SPDX-License-Identifier: AGPL-3.0-only
"""Before a document is saved, bring its citation numbers and bibliography up to date (job on OnSave, OnSaveAs).

Exits at once for documents without HST citation settings (one property lookup), so every other save costs
nothing. Never asks anything and never stops a save: problems go to HST's local log. Nothing is written when the
citations are already current, so a second save of an unchanged document changes nothing (and "Phiên bản trước"
keeps no duplicate). Registered in Jobs.xcu and hst_office_component.SERVICES.
"""
import unohelper
from com.sun.star.lang import XServiceInfo
from com.sun.star.task import XJob

from . import diag_log

JOB_NAME = "org.hst.office.vi.CitationSaveJob"
EVENTS = ("OnSave", "OnSaveAs")


def _argument(values, name):
    for value in values or ():
        if value.Name == name:
            return value.Value
    return None


def update_before_save(ctx, doc):
    """Refresh when the document carries HST citation settings; returns True when something was written."""
    from . import citation_refresh, citation_settings, citation_texts
    if doc is None or not citation_refresh.is_writable(doc) or citation_settings.read(doc) is None:
        return False
    texts = citation_texts.load(ctx)
    try:
        plan = citation_refresh.refresh(ctx, doc, texts["undo"]["update"], texts["bibliography"]["empty"])
    except citation_refresh.StyleMissing:  # a user's own style from another computer: keep the results as saved
        return False
    return bool(plan and plan["written"])


class CitationSaveJob(unohelper.Base, XServiceInfo, XJob):
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
            if _argument(environment, "EventName") in EVENTS:
                model = _argument(environment, "Model")
                if model is not None and model.supportsService("com.sun.star.text.TextDocument"):
                    update_before_save(self.ctx, model)
        except Exception:  # noqa: BLE001 - a save must never fail because of the citations
            diag_log.exception("citation_save_job")
        return None
