# SPDX-License-Identifier: AGPL-3.0-only
"""Xuất/PDF ▸ Mở trong HST PDF (org.hst.office.vi:OpenInHstPdf): show the document in HST PDF.

The way back from "Chỉnh sửa bằng HST Draw" of HST PDF: a PDF opened in HST Draw and not changed is shown as it
is; anything else (a changed PDF, a drawing, a text, a sheet) is exported to a PDF in a folder of its own under
the temporary directory first, so the original file is never written. The PDF is then loaded like a file the
user opens, which HST PDF's frame loader takes (unless Tools ▸ Options ▸ HST Office turned HST PDF off; the
PDF then opens in HST Draw, as every PDF does).
"""
import os
import re
import tempfile

# Export filter by document service, most specific first (a drawing is also a generic drawing document).
PDF_FILTERS = (
    ("com.sun.star.presentation.PresentationDocument", "impress_pdf_Export"),
    ("com.sun.star.drawing.DrawingDocument", "draw_pdf_Export"),
    ("com.sun.star.text.TextDocument", "writer_pdf_Export"),
    ("com.sun.star.sheet.SpreadsheetDocument", "calc_pdf_Export"),
)
FALLBACK_NAME = "Bản vẽ"


def pdf_filter(services):
    """Export filter for a document supporting these services, or None (pure)."""
    for service, name in PDF_FILTERS:
        if service in services:
            return name
    return None


def reusable_pdf(location, modified):
    """The document's own file when it is an unchanged PDF, else None (pure)."""
    if modified or not location:
        return None
    return location if location.lower().endswith(".pdf") else None


def pdf_file_name(title):
    """A safe file name for the exported PDF, from the window title (pure)."""
    stem = re.sub(r"\.[A-Za-z0-9]{1,5}$", "", (title or "").strip())  # "hop-dong.pdf" -> "hop-dong"
    stem = re.sub(r'[\\/:*?"<>|\x00-\x1f]+', " ", stem).strip(" .")
    return (stem or FALLBACK_NAME)[:120] + ".pdf"


def _services(doc):
    return [service for service, _name in PDF_FILTERS if doc.supportsService(service)]


def export_copy(doc, folder):
    """Export doc to a PDF in folder; returns its file URL."""
    import uno
    name = pdf_filter(_services(doc))
    if name is None:
        raise ValueError("this document cannot be exported to PDF")
    title = doc.getTitle() if hasattr(doc, "getTitle") else ""
    path = os.path.join(folder, pdf_file_name(title))
    arg = uno.createUnoStruct("com.sun.star.beans.PropertyValue")
    arg.Name, arg.Value = "FilterName", name
    url = uno.systemPathToFileUrl(path)
    doc.storeToURL(url, (arg,))
    return url


def run(host):
    doc = host.doc
    url = reusable_pdf(doc.getLocation() if doc.hasLocation() else "", doc.isModified())
    if url is None:
        url = export_copy(doc, tempfile.mkdtemp(prefix="hst-pdf-"))
    desktop = host.ctx.ServiceManager.createInstanceWithContext("com.sun.star.frame.Desktop", host.ctx)
    desktop.loadComponentFromURL(url, "_blank", 0, ())
    return url
