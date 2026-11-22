# SPDX-License-Identifier: LicenseRef-HST-Proprietary
# Copyright (C) 2026 HASON TECH
"""Job on OnLoad: a mail-merge document is connected to its recipient list again when it opens
(mail_merge_word_link.connect_on_load). Leaves at once for anything but a Writer document that is a Word package
with w:mailMerge or carries HST mail-merge settings, so opening other files costs one or two property reads.
Never stops a document from opening: problems go to HST's local log. Registered in Jobs.xcu and
hst_office_component.SERVICES."""
import unohelper
from com.sun.star.lang import XServiceInfo
from com.sun.star.task import XJob

from . import diag_log

JOB_NAME = "org.hst.office.vi.MailMergeWordJob"
EVENTS = ("OnLoad",)
PROPERTY = "HSTMailMerge"  # mail_merge_store.PROPERTY, read here without importing the mail-merge modules
WORD_PACKAGES = (".docx", ".docm", ".dotx", ".dotm")


def _argument(values, name):
    for value in values or ():
        if value.Name == name:
            return value.Value
    return None


def is_candidate(doc):
    """A Writer document from a Word package, or one with HST mail-merge settings."""
    if doc is None or not doc.supportsService("com.sun.star.text.TextDocument"):
        return False
    if doc.getURL().lower().endswith(WORD_PACKAGES):
        return True
    try:
        return doc.DocumentProperties.UserDefinedProperties.getPropertySetInfo().hasPropertyByName(PROPERTY)
    except Exception:  # noqa: BLE001 - no document properties: not one of ours
        return False


class MailMergeWordJob(unohelper.Base, XServiceInfo, XJob):
    def __init__(self, ctx, *args):
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
                if is_candidate(model):
                    from . import mail_merge_word_link
                    mail_merge_word_link.connect_on_load(self.ctx, model)
        except Exception:  # noqa: BLE001 - never stop a document from opening
            diag_log.exception("mail_merge_word_job")
        return None
