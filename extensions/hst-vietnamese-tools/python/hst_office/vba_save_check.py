# SPDX-License-Identifier: AGPL-3.0-only
"""After saving as an Excel or Word file, tell the user what of the VBA UserForms was not written.

The export writes UserForms with labels, text boxes, buttons, check boxes, option buttons, combo and
list boxes, frames, spin buttons and scroll bars, but real Office did not accept the first forms, so
any form HST wrote gets a warning until that is verified. Other controls cannot be written and are
left out. A Word file keeps the VBA project it was read with (Save As asks first when macros were
edited). Fixed list items are not stored in Office files either. Runs as a job on OnSaveDone / OnSaveAsDone (Jobs.xcu);
the message is Vietnamese (HST policy).
"""
import traceback

import unohelper
from com.sun.star.lang import XServiceInfo
from com.sun.star.task import XJob

from .vba_template import bound_form_controls, is_excel_filter, is_word_filter, unwritable_form_content

JOB_NAME = "org.hst.office.vi.VbaSaveCheckJob"
EVENTS = ("OnSaveDone", "OnSaveAsDone")
FORM_MODULE = 3  # com.sun.star.script.ModuleType.FORM
TITLE = "Macro VBA"
EXCEL_LOST = ("Tệp Excel vừa lưu không chứa các điều khiển sau trong biểu mẫu VBA (UserForm): %s.\n"
              "Mã VBA và các điều khiển khác vẫn được lưu. Để giữ đủ biểu mẫu, hãy lưu thêm một bản .ods "
              "(Tệp tin → Lưu thành).")
WORD_KEPT = ("Biểu mẫu VBA (UserForm) này có điều khiển chưa ghi được vào tệp Word: %s.\n"
             "Các điều khiển này bị bỏ khỏi tệp. Để giữ đủ, hãy lưu thêm một bản .odt (Tệp tin → Lưu thành).")
FORMS_NOT_VERIFIED = ("Biểu mẫu VBA (UserForm) trong tệp vừa lưu chưa dùng được chắc chắn trong Microsoft Office: "
                      "Excel hoặc Word có thể không mở được biểu mẫu hoặc macro. "
                      "Hãy giữ thêm một bản .ods hoặc .odt (Tệp tin → Lưu thành).")
BOUND = ("Liên kết với ô (ControlSource, RowSource) của %s không được ghi vào tệp Office vừa lưu: "
         "các điều khiển này sẽ không còn nối với bảng tính. Bản .ods vẫn giữ các liên kết này.")
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


def has_written_forms(doc):
    """True when HST wrote the forms itself: a file keeps a project with forms it was read with."""
    if doc.getDocumentStorage().hasByName("_MS_VBA_Macros"):
        return False
    libs = doc.BasicLibraries
    for library_name in libs.ElementNames:
        libs.loadLibrary(library_name)
        library = libs.getByName(library_name)
        if hasattr(library, "hasModuleInfo"):
            for name in library.ElementNames:
                if library.hasModuleInfo(name) and library.getModuleInfo(name).ModuleType == FORM_MODULE:
                    return True
    return False


def form_problems(doc):
    """(controls that cannot be written, with fixed list items, bound to cells), as "Form.Control" names."""
    unwritable, list_items, bound = [], [], []
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
                    bound += ["%s.%s" % (form, name) for name in bound_form_controls(xml)]
    return unwritable, list_items, bound


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
    # A project kept from the file has every control, list and link it was read with
    if doc.getDocumentStorage().hasByName("_MS_VBA_Macros"):
        return None
    unwritable, list_items, bound = form_problems(doc)
    parts = []
    if has_written_forms(doc):
        parts.append(FORMS_NOT_VERIFIED)
    if unwritable:
        parts.append((EXCEL_LOST if is_calc else WORD_KEPT) % ", ".join(unwritable))
    if list_items:
        parts.append(LIST_ITEMS % ", ".join(list_items))
    if bound:
        parts.append(BOUND % ", ".join(bound))
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
