# SPDX-License-Identifier: AGPL-3.0-only
"""Trộn thư: "Hoàn tất và trộn" through the LibreOffice engine (com.sun.star.text.MailMerge). The chosen recipients
are staged first (mail_merge_session.stage), so the engine merges exactly what the preview showed, in that order.

  edit   one merged document, opened as a new untitled document
  print  the same document, then the print dialog on it
  pdf    one PDF per recipient   } named from the file-name column (pattern {Cột});
  docx   one DOCX per recipient  } an existing file is kept, the new one gets a number
  mail   one e-mail per recipient (engine SMTP settings; body text or PDF attachment)"""
import os
import tempfile

from . import mail_merge_store as store
from . import mail_merge_table as mt

EDIT, PRINT, PDF, DOCX, MAIL = "edit", "print", "pdf", "docx", "mail"
FILTERS = {PDF: "writer_pdf_Export", DOCX: "MS Word 2007 XML"}
FILE, MAILS = 2, 3  # com.sun.star.text.MailMergeType
MAIL_CONFIG = "/org.openoffice.Office.Writer/MailMergeWizard"


class Request:
    """What the finish dialog asks for."""

    def __init__(self, action, indexes, pattern="", folder="", mail_column="", subject="", attach=False):
        self.action, self.indexes, self.pattern, self.folder = action, list(indexes), pattern, folder
        self.mail_column, self.subject, self.attach = mail_column, subject, attach


def _prop(name, value):
    from com.sun.star.beans import PropertyValue
    return PropertyValue(Name=name, Value=value)


def mail_server_set(ctx):
    from .ui_language import _node
    try:
        return bool(_node(ctx, MAIL_CONFIG).getPropertyValue("MailServer"))
    except Exception:  # noqa: BLE001 - no Writer configuration: not set
        return False


def _engine(ctx, doc, source_name, work):
    """The engine on an ODF copy of the document in `work` (its Model property is read-only, and the copy keeps
    the user's document, its URL and its modified state untouched)."""
    import uno
    template = os.path.join(work, "mau.odt")
    doc.storeToURL(uno.systemPathToFileUrl(template), (_prop("FilterName", "writer8"),))
    merge = ctx.ServiceManager.createInstanceWithContext("com.sun.star.text.MailMerge", ctx)
    merge.DataSourceName, merge.Command, merge.CommandType = source_name, store.TABLE, 0
    merge.DocumentURL = uno.systemPathToFileUrl(template)
    return merge


def _open_merged(ctx, folder):
    """Open the single merged file as a new untitled document (AsTemplate) and return it."""
    import uno
    names = [n for n in os.listdir(folder) if n.endswith(".odt")]
    if not names:
        raise RuntimeError("no merged document")
    desktop = ctx.ServiceManager.createInstanceWithContext("com.sun.star.frame.Desktop", ctx)
    url = uno.systemPathToFileUrl(os.path.join(folder, names[0]))
    return desktop.loadComponentFromURL(url, "_blank", 0, (_prop("AsTemplate", True),))


def _remove_tree(folder):
    import shutil
    shutil.rmtree(folder, ignore_errors=True)  # a file still held open (Windows) stays in the temp folder


def run(ctx, doc, session, request, words=None):
    """Run the request; returns (merged document or None, number of recipients). Raises on engine errors."""
    pattern = request.pattern if request.action in (PDF, DOCX) else ""
    source_name = session.stage(ctx, request.indexes, pattern, words)
    work = tempfile.mkdtemp(prefix="hst-tron-thu-")
    try:
        merged = _execute(ctx, _engine(ctx, doc, source_name, work), request, work)
    finally:
        _remove_tree(work)
    return merged, len(request.indexes)


def _execute(ctx, merge, request, work):
    import uno
    if request.action in (EDIT, PRINT):
        result = os.path.join(work, "out")
        os.makedirs(result)
        merge.OutputType, merge.SaveAsSingleFile, merge.SaveFilter = FILE, True, "writer8"
        merge.OutputURL, merge.FileNamePrefix = uno.systemPathToFileUrl(result), "tron-thu"
        merge.execute(())
        merged = _open_merged(ctx, result)
        if request.action == PRINT:
            frame = merged.getCurrentController().getFrame()
            helper = ctx.ServiceManager.createInstanceWithContext("com.sun.star.frame.DispatchHelper", ctx)
            helper.executeDispatch(frame, ".uno:Print", "", 0, ())
        return merged
    if request.action in FILTERS:
        os.makedirs(request.folder, exist_ok=True)
        merge.OutputType, merge.SaveAsSingleFile = FILE, False
        merge.SaveFilter = FILTERS[request.action]
        merge.OutputURL = uno.systemPathToFileUrl(request.folder)
        merge.FileNameFromColumn, merge.FileNamePrefix = True, mt.FILE_COLUMN
        merge.execute(())
        return None
    if request.action == MAIL:
        merge.OutputType = MAILS
        merge.AddressFromColumn, merge.Subject = request.mail_column, request.subject
        merge.SendAsHTML, merge.SendAsAttachment = False, bool(request.attach)
        if request.attach:
            merge.AttachmentFilter = FILTERS[PDF]
            merge.AttachmentName = (request.subject or "Van ban").strip() + ".pdf"
            merge.MailBody = request.subject
        merge.execute(())
        return None
    raise ValueError(request.action)


def mail_columns(table):
    """Columns that look like e-mail addresses, the most likely first (header "Email", "Thư điện tử", or values)."""
    from .vietnamese_text import remove_diacritics
    scored = []
    for header in table.headers:
        plain = remove_diacritics(header).lower()
        named = any(word in plain for word in ("email", "e-mail", "thu dien tu", "mail"))
        filled = [r[table.column(header)] for r in table.rows if isinstance(r[table.column(header)], str)]
        looks = bool(filled) and all("@" in v for v in filled if v.strip())
        if named or looks:
            scored.append((0 if named else 1, header))
    return [h for _, h in sorted(scored, key=lambda item: item[0])]
