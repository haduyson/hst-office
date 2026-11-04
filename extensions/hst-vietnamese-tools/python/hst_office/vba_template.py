# SPDX-License-Identifier: AGPL-3.0-only
"""Text of the VBA modules HST creates for "Macro VBA" (pure Python, no UNO; unit-tested).

Every new module starts with Option VBASupport 1, so Excel/Word object names (Range, Cells,
ActiveDocument…) work in it even when the document is not in VBA mode, followed by a short
Vietnamese guide and one example macro the user can run with F5.
"""
import unicodedata

OPTION_LINE = "Option VBASupport 1"
# Names the Office VBA editors use for a new file's project, so users find what they know.
PROJECT_NAMES = {"calc": "VBAProject", "writer": "Project"}
MODULE_PREFIX = "Module"
# Windows-1258 (Vietnamese): the code page Excel/Word on Vietnamese Windows store VBA source in.
# rtl_TextEncoding value of RTL_TEXTENCODING_MS_1258 (include/rtl/textenc.h).
VBA_TEXT_ENCODING_VI = 40

_GUIDE = {
    "calc": ("HST Sheets", "Excel", ".xlsm (Excel có macro) hoặc .ods"),
    "writer": ("HST Writer", "Word", ".docm (Word có macro) hoặc .odt"),
}
_EXAMPLE = {
    "calc": ('Sub XinChao()\n'
             '    \' Ví dụ: ghi lời chào vào ô A1 của trang tính đang mở\n'
             '    ActiveSheet.Range("A1").Value = "Xin chào từ VBA!"\n'
             '    MsgBox "Đã ghi vào ô A1", vbInformation, "HST Sheets"\n'
             'End Sub\n'),
    "writer": ('Sub XinChao()\n'
               '    \' Ví dụ: thêm một câu chào vào cuối văn bản\n'
               '    ActiveDocument.Content.InsertAfter "Xin chào từ VBA!"\n'
               '    MsgBox "Đã thêm câu chào vào cuối văn bản", vbInformation, "HST Writer"\n'
               'End Sub\n'),
}


def module_text(app):
    """Initial code of a new VBA module for app "calc" or "writer"."""
    product, office, formats = _GUIDE[app]
    return (f"{OPTION_LINE}\n"
            "' ==================================================================\n"
            f"'  Macro VBA của {product}: viết như trong Microsoft {office}.\n"
            "'  - Chạy macro: đặt con trỏ trong một Sub rồi nhấn F5.\n"
            "'  - Từ tài liệu: Alt+F8 mở hộp thoại Macro để chọn và chạy.\n"
            f"'  - Lưu tệp dạng {formats} để giữ macro.\n"
            "'  - Hướng dẫn chi tiết: nhấn F1, mục \"Macro VBA\".\n"
            "' ==================================================================\n\n"
            + _EXAMPLE[app])


def project_name(app):
    return PROJECT_NAMES[app]


def next_module_name(existing):
    """First free Module<n> (n from 1), as the Office VBA editors name new modules."""
    taken = {name.lower() for name in existing}
    n = 1
    while f"{MODULE_PREFIX}{n}".lower() in taken:
        n += 1
    return f"{MODULE_PREFIX}{n}"


def has_vba_option(code):
    """True when the module code switches VBA support on before its first procedure."""
    for line in code.splitlines():
        text = line.strip()
        lowered = text.lower()
        if lowered.startswith(("sub ", "function ", "private ", "public ", "property ")):
            return False
        if lowered.replace("\t", " ").split() == ["option", "vbasupport", "1"]:
            return True
    return False


def first_line_of(code, name):
    """1-based line of the procedure `name` in code (where the editor puts the cursor), else 1."""
    for number, line in enumerate(code.splitlines(), 1):
        words = line.strip().split("(")[0].split()
        if len(words) >= 2 and words[-2].lower() in ("sub", "function") and words[-1].lower() == name.lower():
            return number
    return 1


def same_text(a, b):
    """Compare module code as a user sees it: ignore line endings, Unicode normalisation (Windows-1258
    stores some Vietnamese letters decomposed) and the "Rem Attribute VBA_…" lines the import adds."""
    def norm(text):
        lines = text.replace("\r\n", "\n").replace("\r", "\n").split("\n")
        lines = [line for line in lines if not line.startswith("Rem Attribute VBA_")]
        return unicodedata.normalize("NFC", "\n".join(lines)).strip("\n")
    return norm(a) == norm(b)


# Dialog elements (xmlscript) of the controls HST can write into Excel and Word VBA projects.
_FORM_CONTROLS = {"button", "text", "textfield", "checkbox", "radio", "radiogroup", "combobox", "menulist", "titledbox", "frame",
                  "spinbutton", "scrollbar", "bulletinboard", "title", "menupopup", "menuitem", "styles", "style",
                  "window", "event", "listener-event"}


def unwritable_form_content(dialog_xml):
    """(controls that cannot be written, controls whose fixed list items are not stored) of a dialog's XML.

    Word and Excel keep no list items in a form file (code fills them with AddItem), so items typed in
    the HST dialog editor stay only in .ods/.odt."""
    import xml.etree.ElementTree as ET
    dialog_ns = "{http://openoffice.org/2000/dialog}"
    unwritable, list_items = [], []
    for element in ET.fromstring(dialog_xml).iter():
        tag = element.tag.replace(dialog_ns, "")
        control = element.get(dialog_ns + "id", tag)
        if tag not in _FORM_CONTROLS and element.tag.startswith(dialog_ns):
            unwritable.append(control)
        elif tag in ("combobox", "menulist") and element.find(dialog_ns + "menupopup") is not None:
            list_items.append(control)
    return unwritable, list_items


def is_excel_filter(name):
    """True for the filters that write an Excel file (xls, xlsx, xlsm, Excel templates)."""
    return bool(name) and ("Excel" in name or "Calc Office Open XML" in name)


def is_word_filter(name):
    """True for the filters that write a Word file with a VBA project (.doc, .docm)."""
    return name in ("MS Word 97", "MS Word 97 Vorlage", "MS Word 2007 XML VBA", "Office Open XML Text VBA")
