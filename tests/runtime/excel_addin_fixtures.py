# SPDX-License-Identifier: LicenseRef-HST-Proprietary
# Copyright (C) 2026 HASON TECH
"""Small .xlsx files that call VND()/USD() through a Vietnamese number-words add-in, written part by part the way
Excel writes such calls (ECMA-376 Part 1, 18.14 External Workbook References and 18.17 Formulas; the relationship
types of [MS-XLSX] 2.1 for links relative to an Office folder):

  - a function of an add-in workbook (.xlam/.xla): the cell formula is "[1]!VND(A1,TRUE)", workbook.xml lists
    <externalReferences>, xl/externalLinks/externalLink1.xml holds <externalBook r:id> with a <definedName> per
    function used, and its relationship (TargetMode="External") points at the add-in file;
  - a function registered by an XLL add-in: the cell formula carries the "_xll." prefix, "_xll.VND(A1)".

Each formula cell keeps the result text Excel computed as a cached string value (t="str"). Used by
tests/unit/test_excel_addin_calls.py and tests/runtime/check-sheets-vnd-usd.py; no other dependency than the standard
library.
"""
import zipfile
from xml.sax.saxutils import escape, quoteattr

MAIN = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
OFFICE_RELS = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
PACKAGE_RELS = "http://schemas.openxmlformats.org/package/2006/relationships"
LINK_PATH = OFFICE_RELS + "/externalLinkPath"
MS_LINK_PATH = "http://schemas.microsoft.com/office/2006/relationships/xlExternalLinkPath/"
XLSTARTUP, XLLIBRARY, XLPATHMISSING = MS_LINK_PATH + "xlStartup", MS_LINK_PATH + "xlLibrary", MS_LINK_PATH + "xlPathMissing"
VNTOOLS_PATH = "file:///C:\\Program%20Files%20(x86)\\vnTools\\Ufunctions.xlam"
HEADER = '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
SPREADSHEET = "application/vnd.openxmlformats-officedocument.spreadsheetml."


class Link:
    """An external workbook link: the relationship target and type, and the defined names Excel lists for it."""

    def __init__(self, target, names, rel_type=LINK_PATH):
        self.target, self.names, self.rel_type = target, names, rel_type


def _row_number(ref):
    return int("".join(ch for ch in ref if ch.isdigit()))


def _cell(ref, content):
    """content: a number (a value cell), a text (a string cell) or (formula, cached text) for a formula cell."""
    if isinstance(content, tuple):
        formula, cached = content
        return '<c r="%s" t="str"><f>%s</f><v>%s</v></c>' % (ref, escape(formula), escape(cached))
    if isinstance(content, str):
        return '<c r="%s" t="inlineStr"><is><t>%s</t></is></c>' % (ref, escape(content))
    return '<c r="%s"><v>%r</v></c>' % (ref, content)


def _sheet(cells):
    rows = {}
    for ref, content in cells.items():
        rows.setdefault(_row_number(ref), []).append(_cell(ref, content))
    data = "".join('<row r="%d">%s</row>' % (number, "".join(rows[number])) for number in sorted(rows))
    return HEADER + '<worksheet xmlns="%s" xmlns:r="%s"><sheetData>%s</sheetData></worksheet>' % (MAIN, OFFICE_RELS, data)


def write_xlsx(path, cells, links=()):
    """Write an .xlsx with one sheet "Sheet1" holding `cells` ({"B1": ("[1]!VND(A1)", "cached"), "A1": 1500}) and
    the external links `links` (Link objects; "[1]" is the first)."""
    types = ['<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>',
             '<Default Extension="xml" ContentType="application/xml"/>',
             '<Override PartName="/xl/workbook.xml" ContentType="%ssheet.main+xml"/>' % SPREADSHEET,
             '<Override PartName="/xl/worksheets/sheet1.xml" ContentType="%sworksheet+xml"/>' % SPREADSHEET]
    workbook_rels = ['<Relationship Id="rId1" Type="%s/worksheet" Target="worksheets/sheet1.xml"/>' % OFFICE_RELS]
    references = []
    parts = {}
    for number, link in enumerate(links, 1):
        rel_id = "rId%d" % (number + 1)
        types.append('<Override PartName="/xl/externalLinks/externalLink%d.xml" ContentType="%sexternalLink+xml"/>'
                     % (number, SPREADSHEET))
        workbook_rels.append('<Relationship Id="%s" Type="%s/externalLink" Target="externalLinks/externalLink%d.xml"/>'
                             % (rel_id, OFFICE_RELS, number))
        references.append('<externalReference r:id="%s"/>' % rel_id)
        names = "".join("<definedName name=%s/>" % quoteattr(name) for name in link.names)
        parts["xl/externalLinks/externalLink%d.xml" % number] = (
            HEADER + '<externalLink xmlns="%s" xmlns:r="%s"><externalBook r:id="rId1"><definedNames>%s</definedNames>'
            '</externalBook></externalLink>' % (MAIN, OFFICE_RELS, names))
        parts["xl/externalLinks/_rels/externalLink%d.xml.rels" % number] = (
            HEADER + '<Relationships xmlns="%s"><Relationship Id="rId1" Type="%s" Target=%s TargetMode="External"/>'
            '</Relationships>' % (PACKAGE_RELS, link.rel_type, quoteattr(link.target)))
    external = "<externalReferences>%s</externalReferences>" % "".join(references) if references else ""
    parts.update({
        "[Content_Types].xml": HEADER + '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
                               '%s</Types>' % "".join(types),
        "_rels/.rels": HEADER + '<Relationships xmlns="%s"><Relationship Id="rId1" Type="%s/officeDocument" '
                                'Target="xl/workbook.xml"/></Relationships>' % (PACKAGE_RELS, OFFICE_RELS),
        "xl/workbook.xml": HEADER + '<workbook xmlns="%s" xmlns:r="%s"><sheets><sheet name="Sheet1" sheetId="1" '
                                    'r:id="rId1"/></sheets>%s<calcPr calcId="191029"/></workbook>'
                                    % (MAIN, OFFICE_RELS, external),
        "xl/_rels/workbook.xml.rels": HEADER + '<Relationships xmlns="%s">%s</Relationships>'
                                               % (PACKAGE_RELS, "".join(workbook_rels)),
        "xl/worksheets/sheet1.xml": _sheet(cells),
    })
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as package:
        for name in ("[Content_Types].xml", "_rels/.rels"):
            package.writestr(name, parts.pop(name))
        for name, data in parts.items():
            package.writestr(name, data)
    return path
