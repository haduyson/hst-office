# SPDX-License-Identifier: AGPL-3.0-only
"""Job of "Phiên bản trước" on the document events of Jobs.xcu (strategy and timing: version_capture).

- OnModifyChanged, when the document has become modified: copy its file in the background (prepare).
- OnSave, before the office writes the file: store the copy, or copy within version_capture.WAIT_SECONDS.
- OnSaveDone, OnSaveAsDone: record the file just written, so that saving the unmodified document again keeps nothing.
- OnUnload: drop a staged copy that was never needed.
Only documents stored in a local or mounted file (file: URL) count; a new document's first save (Save As) has no
earlier file to keep. Nothing raises into the office: outcomes go to the local log (no path, diag_log).
"""
import time

import unohelper
from com.sun.star.lang import XServiceInfo
from com.sun.star.task import XJob

from . import diag_log

JOB_NAME = "org.hst.office.vi.PreviousVersionsJob"
SLOW_SECONDS = 0.5  # log an OnSave that took longer, with its outcome
LOGGED = ("timeout", "changed", "busy", "failed")
EVENTS = ("OnModifyChanged", "OnSave", "OnSaveDone", "OnSaveAsDone", "OnUnload")


def _argument(arguments, name):
    for item in arguments or ():
        if item.Name == name:
            return item.Value
    return None


def handle(ctx, event, model):
    """Run the action of one event; returns the outcome (for tests and the log) or None."""
    from . import version_capture, version_config
    from .version_config import document_path
    if event not in EVENTS:
        return None
    path = document_path(model)
    if path is None:
        return None
    if event == "OnUnload":
        version_capture.discard(path)
        return "discarded"
    if not version_config.enabled(ctx):
        version_capture.discard(path)
        return "disabled"
    if event in ("OnSaveDone", "OnSaveAsDone"):
        return version_capture.remember(path)
    store = version_config.store(ctx)
    if event == "OnModifyChanged":
        return version_capture.prepare(store, path) if model.isModified() else None
    started = time.monotonic()
    outcome = version_capture.before_save(store, path, modified=model.isModified())
    took = time.monotonic() - started
    if outcome in LOGGED or took > SLOW_SECONDS:
        diag_log.info("previous_versions", "OnSave copy: %s in %.2f s" % (outcome, took))
    return outcome


class PreviousVersionsJob(unohelper.Base, XServiceInfo, XJob):
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
            handle(self.ctx, _argument(environment, "EventName"), _argument(environment, "Model"))
        except Exception:  # noqa: BLE001 - a save must never fail because of a version copy
            diag_log.exception("previous_versions")
        return None
