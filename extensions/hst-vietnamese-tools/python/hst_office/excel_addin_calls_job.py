# SPDX-License-Identifier: LicenseRef-HST-Proprietary
# Copyright (C) 2026 HASON TECH
"""After a spreadsheet is loaded, its VND()/USD() calls through a Vietnamese number-words add-in become calls of the
HST functions, so the cells calculate instead of showing #NAME? or an external-reference error (excel_addin_calls.py
says which calls and how). Any file format: .xlsx, .xls and an .ods that kept such a call all show it the same way.

Runs as a job on OnLoadFinished for Sheets documents only (Jobs.xcu), before the document gets its window. The office
still lists the add-in file among the document's external files (no API removes it; the next save drops it), so its
window would offer "automatic update of external links has been disabled": at OnLoad, once the window is up, that bar
is removed when those add-in files were the document's only links. Cells are
found with the sheet's own formula search, so a file without such a call costs one search per sheet. The rewrite
adds no undo step and leaves the document unmodified: it is how the file is read, not an edit. A cell that cannot be
written (e.g. on a protected sheet) keeps its formula and is logged.
"""
import unohelper
from com.sun.star.lang import XServiceInfo
from com.sun.star.task import XJob

from . import diag_log
from .excel_addin_calls import (ADDIN_FILES, UNRESOLVED, document_file_name, external_link_files,
                                macro_defined_functions, rewrite)

JOB_NAME = "org.hst.office.vi.ExcelAddinCallsJob"
LOADED, SHOWN = "OnLoadFinished", "OnLoad"
EVENTS = (LOADED, SHOWN)
LINKS_INFOBAR = "enablecontent"  # the office's "automatic update of external links has been disabled" bar
# the sheet search looks at formula texts (SearchType 0), ignoring case, for the XLL prefix, an add-in file name or a
# numbered external link calling VND/USD: the text it searches is in the UI formula syntax, where an external name is
# not written as in the API grammar
LINK_SEARCH = r"ufunctions\.xla|acchelper|\]!"  # a formula still referring to an add-in file
SEARCH = r"_xll\.|ufunctions\.xla|acchelper|\]!(vnd|usd)\b|\b(vnd|usd)\s*\("


def _argument(arguments, name):
    for item in arguments or ():
        if item.Name == name:
            return item.Value
    return None


def _candidate_cells(sheet, search=None):
    """The cells of a sheet whose formula matches `search` (default: an add-in call form), as (sheet, XCell)."""
    descriptor = sheet.createSearchDescriptor()
    descriptor.SearchString = search or SEARCH
    descriptor.SearchRegularExpression = True
    descriptor.SearchCaseSensitive = False
    descriptor.setPropertyValue("SearchType", 0)
    found = sheet.findAll(descriptor)
    if found is None:
        return
    for index in range(found.getCount()):
        block = found.getByIndex(index)
        address = block.getRangeAddress()
        for row in range(address.EndRow - address.StartRow + 1):
            for column in range(address.EndColumn - address.StartColumn + 1):
                yield sheet, block.getCellByPosition(column, row)


class _LinkFiles:
    """The external link file names of the loaded .xlsx package, read once and only when a "[n]!" call needs them."""

    def __init__(self, doc):
        self.doc, self.files = doc, None

    def get(self):
        if self.files is None:
            self.files = {}
            try:
                import zipfile
                import uno
                url = self.doc.getURL()
                if url.startswith("file:"):
                    with zipfile.ZipFile(uno.fileUrlToSystemPath(url)) as package:
                        self.files = external_link_files(package)
            except Exception:  # noqa: BLE001 - not a readable .xlsx package: such calls stay as they are
                diag_log.warning("excel_addin_calls", "external links of the package not readable")
        return self.files


def macro_functions(doc):
    """Upper-case names among VND/USD that a Basic or VBA module of the document defines."""
    sources = []
    try:
        libraries = doc.BasicLibraries
        for library_name in libraries.ElementNames:
            libraries.loadLibrary(library_name)
            library = libraries.getByName(library_name)
            for module in library.ElementNames:
                source = library.getByName(module)
                sources.append(source if isinstance(source, str) else "")
    except Exception:  # noqa: BLE001 - no readable macros: nothing of the document to leave alone
        diag_log.warning("excel_addin_calls", "document macros not readable")
    return macro_defined_functions(sources)


def _rewrite_cell(sheet, cell, done_arrays, links, plain):
    """Rewrite one cell (or the array formula it belongs to, once); True when something changed. Most cells found
    by the search already call the HST functions and are left after one formula read."""
    def new_text(text):
        return rewrite(text, links.get() if "]!" in text else None, bool(UNRESOLVED.search(text)) and plain())

    formula = cell.getFormula()
    if new_text(formula) == formula:
        return False
    cursor = sheet.createCursorByRange(cell)
    cursor.collapseToCurrentArray()
    array = cursor.getArrayFormula()
    if array:
        if cursor.AbsoluteName in done_arrays:
            return False
        done_arrays.add(cursor.AbsoluteName)
        if array.startswith("{") and array.endswith("}"):  # read back as "{=...}", written without the braces
            array = array[1:-1]
        cursor.setArrayFormula(new_text(array))
        return True
    cell.setFormula(new_text(formula))
    return True


def rewrite_document(doc):
    """Rewrite the add-in calls of a spreadsheet document; returns the number of cells (or array formulas) changed."""
    if doc is None or not doc.supportsService("com.sun.star.sheet.SpreadsheetDocument"):
        return 0
    sheets = doc.getSheets()
    candidates = [c for index in range(sheets.getCount()) for c in _candidate_cells(sheets.getByIndex(index))]
    if not candidates:
        return 0
    modified = doc.isModified()
    undo = doc.getUndoManager()
    undo.lock()
    changed, done_arrays, links = 0, set(), _LinkFiles(doc)
    macros = []

    def plain():
        """Whether bare names may be rewritten: the document's macros are read once, on the first such name."""
        if not macros:
            macros.append(macro_functions(doc))
        return not macros[0]

    try:
        for sheet, cell in candidates:
            try:
                changed += _rewrite_cell(sheet, cell, done_arrays, links, plain)
            except Exception:  # noqa: BLE001 - one cell that cannot be written must not stop the others
                diag_log.warning("excel_addin_calls", "cell %s kept its formula" % cell.AbsoluteName)
    finally:
        undo.unlock()
        if not modified and doc.isModified():
            doc.setModified(False)
    if changed:
        diag_log.info("excel_addin_calls", "%d add-in VND/USD formula(s) now use the HST functions" % changed)
    return changed


def only_addin_links(doc):
    """True when the document's external links are all add-in files that no formula refers to any more (the rewrite
    removed every call) and it has no other kind of link: then the links bar has nothing to offer."""
    names = list(doc.ExternalDocLinks.ElementNames)
    if not names or doc.AreaLinks.getCount() or doc.SheetLinks.getElementNames() or doc.DDELinks.getElementNames():
        return False
    # a link kept without its path (Office library folder) is named by its number only
    if any(document_file_name(name) not in ADDIN_FILES and name.strip("0123456789") for name in names):
        return False
    sheets = doc.getSheets()
    return not any(next(_candidate_cells(sheets.getByIndex(index), LINK_SEARCH), None)
                   for index in range(sheets.getCount()))


def hide_links_infobar(doc):
    """After the window is shown: drop the links bar of a file whose only links were add-in files (see above)."""
    if doc is None or not doc.supportsService("com.sun.star.sheet.SpreadsheetDocument"):
        return False
    controller = doc.getCurrentController()
    if controller is None or not controller.hasInfobar(LINKS_INFOBAR) or not only_addin_links(doc):
        return False
    controller.removeInfobar(LINKS_INFOBAR)
    diag_log.info("excel_addin_calls", "links bar of the add-in file removed")
    return True


class ExcelAddinCallsJob(unohelper.Base, XServiceInfo, XJob):
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
            event = _argument(environment, "EventName")
            if event == LOADED:
                rewrite_document(_argument(environment, "Model"))
            elif event == SHOWN:
                hide_links_infobar(_argument(environment, "Model"))
        except Exception:  # noqa: BLE001 - loading a file must never fail because of this
            diag_log.exception("excel_addin_calls")
        return None
