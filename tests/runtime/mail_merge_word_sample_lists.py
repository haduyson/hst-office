# SPDX-License-Identifier: LicenseRef-HST-Proprietary
# Copyright (C) 2026 HASON TECH
"""The recipient list of the Word mail-merge samples (mail_merge_word_samples.py) as Excel and as CSV save it."""
import datetime
import zipfile
from xml.sax.saxutils import escape, quoteattr

from mail_merge_word_samples import HEADERS, KINDS, PKG, R, ROWS, SHEET


def _serial(day):
    return (day - datetime.date(1899, 12, 30)).days


def _column(index):
    return chr(ord("A") + index)


def _cell(ref, kind, value):
    if value in ("", None):
        return ""
    if kind == "t":
        return '<c r="%s" t="inlineStr"><is><t>%s</t></is></c>' % (ref, escape(value))
    if kind == "s":  # a year typed before the column became Text: a number in a Text cell (style 2 = "@")
        return '<c r="%s" s="2"><v>%s</v></c>' % (ref, value)
    if kind == "d":
        return '<c r="%s" s="1"><v>%d</v></c>' % (ref, _serial(value))
    return '<c r="%s" s="3"><v>%s</v></c>' % (ref, value)


def write_xlsx(path, sheet=SHEET):
    """An .xlsx as Excel saves it: inline strings, dates as serial numbers with a date style, a Text column."""
    rows = ['<row r="1">%s</row>' % "".join(_cell("%s1" % _column(i), "t", h) for i, h in enumerate(HEADERS))]
    for number, values in enumerate(ROWS, 2):
        rows.append('<row r="%d">%s</row>' % (number, "".join(
            _cell("%s%d" % (_column(i), number), KINDS[i], v) for i, v in enumerate(values))))
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as package:
        package.writestr("[Content_Types].xml",
                         '<?xml version="1.0" encoding="UTF-8"?><Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
                         '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
                         '<Default Extension="xml" ContentType="application/xml"/>'
                         '<Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>'
                         '<Override PartName="/xl/worksheets/sheet1.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>'
                         '<Override PartName="/xl/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.styles+xml"/>'
                         '</Types>')
        package.writestr("_rels/.rels",
                         '<?xml version="1.0" encoding="UTF-8"?><Relationships xmlns="%s"><Relationship Id="rId1" '
                         'Type="%s/officeDocument" Target="xl/workbook.xml"/></Relationships>' % (PKG, R))
        package.writestr("xl/workbook.xml",
                         '<?xml version="1.0" encoding="UTF-8"?><workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" '
                         'xmlns:r="%s"><sheets><sheet name=%s sheetId="1" r:id="rId1"/></sheets></workbook>' % (R, quoteattr(sheet)))
        package.writestr("xl/_rels/workbook.xml.rels",
                         '<?xml version="1.0" encoding="UTF-8"?><Relationships xmlns="%s">'
                         '<Relationship Id="rId1" Type="%s/worksheet" Target="worksheets/sheet1.xml"/>'
                         '<Relationship Id="rId2" Type="%s/styles" Target="styles.xml"/></Relationships>' % (PKG, R, R))
        package.writestr("xl/styles.xml",
                         '<?xml version="1.0" encoding="UTF-8"?><styleSheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
                         '<fonts count="1"><font><sz val="11"/><name val="Calibri"/></font></fonts>'
                         '<fills count="2"><fill><patternFill patternType="none"/></fill><fill><patternFill patternType="gray125"/></fill></fills>'
                         '<borders count="1"><border/></borders><cellStyleXfs count="1"><xf numFmtId="0"/></cellStyleXfs>'
                         '<cellXfs count="4"><xf numFmtId="0"/><xf numFmtId="14" applyNumberFormat="1"/>'
                         '<xf numFmtId="49" applyNumberFormat="1"/><xf numFmtId="3" applyNumberFormat="1"/></cellXfs>'
                         '</styleSheet>')
        package.writestr("xl/worksheets/sheet1.xml",
                         '<?xml version="1.0" encoding="UTF-8"?><worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
                         '<sheetData>%s</sheetData></worksheet>' % "".join(rows))


def write_csv(path):
    """The same list as a UTF-8 CSV with BOM (Excel's "CSV UTF-8"), dates as dd/mm/yyyy."""
    lines = [",".join(HEADERS)]
    for values in ROWS:
        cells = [v.strftime("%d/%m/%Y") if isinstance(v, datetime.date) else ("%s" % v) for v in values]
        lines.append(",".join(cells))
    with open(path, "w", encoding="utf-8-sig", newline="") as handle:
        handle.write("\r\n".join(lines) + "\r\n")
