# SPDX-License-Identifier: AGPL-3.0-only
"""After saving a spreadsheet as an Excel file, tell the user when its VBA UserForms were not written.

The Excel export writes the VBA code of every module but not the UserForm designs (the binary
MS-OFORMS storages), so an .xlsm/.xls saved by HST Sheets loses its forms; .ods keeps them.
Runs as a job on OnSaveDone / OnSaveAsDone (Jobs.xcu); the message is Vietnamese (HST policy).
"""
import traceback

import unohelper
from com.sun.star.lang import XServiceInfo
from com.sun.star.task import XJob

from .vba_template import is_excel_filter

JOB_NAME = "org.hst.office.vi.VbaSaveCheckJob"
EVENTS = ("OnSaveDone", "OnSaveAsDone")
FORM_MODULE = 3  # com.sun.star.script.ModuleType.FORM
TITLE = "Macro VBA"
MESSAGE = ("Tệp vừa lưu dạng Excel (%s) chưa chứa các biểu mẫu VBA (UserForm): %s.\n"
           "Mã VBA vẫn được lưu. Để giữ cả biểu mẫu, hãy lưu thêm một bản .ods "
           "(Tập tin → Lưu thành…).")


def form_modules(doc):
    """Names of the UserForm modules of the document's Basic libraries."""
    names = []
    libs = doc.BasicLibraries
    for library_name in libs.ElementNames:
        libs.loadLibrary(library_name)
        library = libs.getByName(library_name)
        if not hasattr(library, "hasModuleInfo"):
            continue
        names += [m for m in library.ElementNames
                  if library.hasModuleInfo(m) and library.getModuleInfo(m).ModuleType == FORM_MODULE]
    return names


def _argument(arguments, name):
    for item in arguments or ():
        if item.Name == name:
            return item.Value
    return None


def check(ctx, doc):
    """Show the warning when needed; returns the message (or None) for tests."""
    if doc is None or not doc.supportsService("com.sun.star.sheet.SpreadsheetDocument"):
        return None
    filter_name = next((a.Value for a in doc.getArgs() if a.Name == "FilterName"), "")
    if not is_excel_filter(filter_name):
        return None
    forms = form_modules(doc)
    if not forms:
        return None
    url = doc.getURL()
    text = MESSAGE % (url.rsplit(".", 1)[-1] if "." in url else filter_name, ", ".join(forms))
    from .dialogs import message_box
    controller = doc.getCurrentController()
    peer = controller.getFrame().getContainerWindow() if controller else None
    message_box(ctx, peer, TITLE, text)
    return text


class VbaSaveCheckJob(unohelper.Base, XServiceInfo, XJob):
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
                check(self.ctx, _argument(environment, "Model"))
        except Exception:  # noqa: BLE001 - a save must never fail because of this hint
            traceback.print_exc()
        return None
