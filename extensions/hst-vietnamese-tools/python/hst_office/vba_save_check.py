# SPDX-License-Identifier: AGPL-3.0-only
"""After saving as an Excel or Word file, tell the user what of the VBA UserForms was not written.

The export writes UserForms with labels, text boxes, buttons, check boxes, option buttons, combo and
list boxes, frames, spin buttons and scroll bars. Other controls cannot be written: an Excel file
loses them; a Word file that already had such a form keeps its original VBA project, so code edits
are not saved there. Fixed list items are not stored in Office files either. Runs as a job on OnSaveDone / OnSaveAsDone (Jobs.xcu);
the message is Vietnamese (HST policy).
"""
import traceback

import unohelper
from com.sun.star.lang import XServiceInfo
from com.sun.star.task import XJob

from .vba_template import is_excel_filter, is_word_filter, unwritable_form_content

JOB_NAME = "org.hst.office.vi.VbaSaveCheckJob"
EVENTS = ("OnSaveDone", "OnSaveAsDone")
FORM_MODULE = 3  # com.sun.star.script.ModuleType.FORM
TITLE = "Macro VBA"
EXCEL_LOST = ("Tệp Excel vừa lưu không chứa các điều khiển sau trong biểu mẫu VBA (UserForm): %s.\n"
              "Mã VBA và các điều khiển khác vẫn được lưu. Để giữ đủ biểu mẫu, hãy lưu thêm một bản .ods "
              "(Tập tin → Lưu thành…).")
WORD_KEPT = ("Biểu mẫu VBA (UserForm) của tệp Word này có điều khiển chưa ghi được: %s.\n"
             "Nếu tệp vốn đã có biểu mẫu này, HST Office giữ nguyên dự án VBA gốc nên phần mã bạn vừa sửa không được "
             "lưu vào tệp; nếu biểu mẫu mới được tạo trong HST, các điều khiển này bị bỏ khỏi tệp. "
             "Để giữ đủ, hãy lưu thêm một bản .odt (Tập tin → Lưu thành…).")
LIST_ITEMS = ("Các mục danh sách nhập sẵn của %s không được lưu trong tệp Office (Office nạp danh sách bằng mã, "
              "ví dụ AddItem trong UserForm_Initialize). Bản .ods/.odt vẫn giữ các mục này.")


def _dialog_xml(doc, library_name, form):
    dialogs = doc.DialogLibraries
    if not dialogs.hasByName(library_name):
        return None
    dialogs.loadLibrary(library_name)
    library = dialogs.getByName(library_name)
    if not library.hasByName(form):
        return None
    stream = library.getByName(form).createInputStream()
    data = b""
    while True:
        count, chunk = stream.readBytes(None, 65536)
        data += bytes(chunk)
        if count < 65536:
            return data


def form_problems(doc):
    """(controls that cannot be written, controls with fixed list items), as "Form.Control" names."""
    unwritable, list_items = [], []
    libs = doc.BasicLibraries
    for library_name in libs.ElementNames:
        libs.loadLibrary(library_name)
        library = libs.getByName(library_name)
        if not hasattr(library, "hasModuleInfo"):
            continue
        for form in library.ElementNames:
            if library.hasModuleInfo(form) and library.getModuleInfo(form).ModuleType == FORM_MODULE:
                xml = _dialog_xml(doc, library_name, form)
                if xml:
                    lost, items = unwritable_form_content(xml)
                    unwritable += ["%s.%s" % (form, name) for name in lost]
                    list_items += ["%s.%s" % (form, name) for name in items]
    return unwritable, list_items


def _argument(arguments, name):
    for item in arguments or ():
        if item.Name == name:
            return item.Value
    return None


def check(ctx, doc):
    """Show the warning when needed; returns the message (or None) for tests."""
    if doc is None:
        return None
    filter_name = next((a.Value for a in doc.getArgs() if a.Name == "FilterName"), "")
    is_calc = doc.supportsService("com.sun.star.sheet.SpreadsheetDocument") and is_excel_filter(filter_name)
    is_writer = doc.supportsService("com.sun.star.text.TextDocument") and is_word_filter(filter_name)
    if not is_calc and not is_writer:
        return None
    unwritable, list_items = form_problems(doc)
    parts = []
    if unwritable:
        parts.append((EXCEL_LOST if is_calc else WORD_KEPT) % ", ".join(unwritable))
    if list_items:
        parts.append(LIST_ITEMS % ", ".join(list_items))
    if not parts:
        return None
    text = "\n\n".join(parts)
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
