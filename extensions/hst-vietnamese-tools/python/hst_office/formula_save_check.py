# SPDX-License-Identifier: AGPL-3.0-only
"""HST Công thức: before a document with formulas is saved as .doc, .xls or .ppt, say that its formulas are written
as Equation Editor 3.0 objects, which Word removed in 2018 (they show and print there but cannot be edited), and
recommend .docx/.xlsx/.pptx. "Vẫn lưu" saves; "Hủy" (or closing the question) saves nothing.

Asked by save_format_check (the core's check before a file is written, hst-save-format-check.patch)."""
from . import formula_ole

# filter name prefix -> extension the user knows; covers the templates and PowerPoint's AutoPlay as well
BINARY_FILTERS = (("MS Word 97", ".doc"), ("MS Excel 97", ".xls"), ("MS PowerPoint 97", ".ppt"))


def binary_extension(filter_name):
    """".doc", ".xls" or ".ppt" for the binary Office filters, else None."""
    return next((ext for prefix, ext in BINARY_FILTERS if (filter_name or "").startswith(prefix)), None)


def _shapes_have_formula(container):
    for i in range(container.getCount()):
        shape = container.getByIndex(i)
        kind = shape.getShapeType()
        if kind == "com.sun.star.drawing.GroupShape" and _shapes_have_formula(shape):
            return True
        if kind == "com.sun.star.drawing.OLE2Shape" and formula_ole.is_math_clsid(shape.CLSID):
            return True
    return False


def has_formula(doc):
    """True when the document holds a Math formula object."""
    if doc.supportsService("com.sun.star.text.TextDocument"):
        objects = doc.getEmbeddedObjects()
        return any(formula_ole.is_math_clsid(objects.getByName(n).CLSID) for n in objects.getElementNames())
    from .formula_convert import shape_pages
    return any(_shapes_have_formula(page) for page in shape_pages(doc))


def _ask(ctx, doc, extension):
    from .data_files import load_locale
    from .dialogs import message_box
    s, common = load_locale("vi")["formula"], load_locale("vi")["common"]
    peer = doc.getCurrentController().getFrame().getContainerWindow()
    return message_box(ctx, peer, s["title"], s["saveDoc"] % extension, ask=True,
                       buttons=(s["saveAnyway"], common["cancel"]))


def check(ctx, doc, filter_name, ask=_ask):
    """False cancels the save; True saves (other formats, or no formula, or "Vẫn lưu")."""
    extension = binary_extension(filter_name)
    if doc is None or extension is None:
        return True
    try:
        if not has_formula(doc):
            return True
    except Exception:  # noqa: BLE001 - a document this check cannot read is saved as asked
        return True
    return bool(ask(ctx, doc, extension))
