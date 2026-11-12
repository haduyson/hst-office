# SPDX-License-Identifier: AGPL-3.0-only
"""Synthetic large documents for open-time measurements (scripts/perf/large-file-open.py).

    python large_file_fixtures.py <out-dir> [--rows N] [--pages N] [--slides N] [--pdf-pages N]

Writes, all synthetic (random numbers, generated Vietnamese-like text, noise pictures):
- calc-values.xlsx      one big sheet of numbers, text and dates with a handful of cell styles (no formulas)
- calc-formulas.xlsx    the same rows plus formula columns with cached results (shared formulas, IF, VLOOKUP into a
                        lookup sheet, SUMIF over whole columns), written as by the common spreadsheet application
- calc-formulas-plain.xlsx  the same workbook with every formula written out per cell instead of shared formulas
- calc-formulas-other.xlsx  byte-identical sheets, but docProps/app.xml names another generator: the importer then
                        treats the cached results as untrusted (as for files exported by accounting software)
- calc-styles.xlsx      formula rows with ~4000 distinct cell formats scattered over the cells, conditional formatting
                        rules over whole columns and data validation lists (style-heavy workbooks)
- calc-sheets.xlsx      60 sheets of 4000 rows each, every sheet summing into a summary sheet (many-sheet workbooks)
- writer-text.docx      many pages of headings, paragraphs and tables
- writer-images.docx    fewer pages with a large picture on every page
- slides-images.pptx    one large picture and a title per slide
- pdf-mixed.pdf         text pages with a picture on every 5th page
- text-lines-10mb.txt / text-longlines-10mb.txt / text-lines-50mb.txt / text-oneline-10mb.txt  Vietnamese UTF-8 plain text (Writer)
Needs Pillow, python-docx and python-pptx. Sizes are printed; nothing here reads a user file.
"""
import argparse
import io
import os
import random
import sys
import zipfile
from xml.sax.saxutils import escape

WORDS = ("công ty", "hóa đơn", "khách hàng", "số lượng", "đơn giá", "thành tiền", "ngày", "tháng", "năm", "báo cáo",
         "doanh thu", "chi phí", "hợp đồng", "thanh toán", "nhân viên", "phòng ban", "kế toán", "tổng cộng", "ghi chú",
         "Hà Nội", "Đà Nẵng", "Hồ Chí Minh", "vật tư", "kho", "nhập", "xuất", "tồn", "mã hàng", "đơn vị", "chiếc")


def sentence(rnd, n):
    return " ".join(rnd.choice(WORDS) for _ in range(n)).capitalize()


def col(i):
    s = ""
    i += 1
    while i:
        i, r = divmod(i - 1, 26)
        s = chr(65 + r) + s
    return s


# ---------------------------------------------------------------- xlsx (written by hand: cached results, shared formulas)
CT = ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
      '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
      '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
      '<Default Extension="xml" ContentType="application/xml"/>'
      '<Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>'
      '<Override PartName="/xl/worksheets/sheet1.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>'
      '<Override PartName="/xl/worksheets/sheet2.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>'
      '<Override PartName="/xl/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.styles+xml"/>'
      '<Override PartName="/xl/sharedStrings.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sharedStrings+xml"/>'
      '<Override PartName="/docProps/core.xml" ContentType="application/vnd.openxmlformats-package.core-properties+xml"/>'
      '<Override PartName="/docProps/app.xml" ContentType="application/vnd.openxmlformats-officedocument.extended-properties+xml"/>'
      '</Types>')
RELS = ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
        '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
        '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/>'
        '<Relationship Id="rId2" Type="http://schemas.openxmlformats.org/package/2006/relationships/metadata/core-properties" Target="docProps/core.xml"/>'
        '<Relationship Id="rId3" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/extended-properties" Target="docProps/app.xml"/>'
        '</Relationships>')
WB = ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
      '<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" '
      'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">'
      '<sheets><sheet name="DuLieu" sheetId="1" r:id="rId1"/><sheet name="DanhMuc" sheetId="2" r:id="rId2"/></sheets>'
      '<calcPr calcId="191029"/></workbook>')
WB_RELS = ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
           '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
           '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet1.xml"/>'
           '<Relationship Id="rId2" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet2.xml"/>'
           '<Relationship Id="rId3" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles" Target="styles.xml"/>'
           '<Relationship Id="rId4" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/sharedStrings" Target="sharedStrings.xml"/>'
           '</Relationships>')
STYLES = ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
          '<styleSheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
          '<numFmts count="1"><numFmt numFmtId="164" formatCode="#,##0"/></numFmts>'
          '<fonts count="2"><font><sz val="11"/><name val="Calibri"/></font><font><b/><sz val="11"/><name val="Calibri"/></font></fonts>'
          '<fills count="3"><fill><patternFill patternType="none"/></fill><fill><patternFill patternType="gray125"/></fill>'
          '<fill><patternFill patternType="solid"><fgColor rgb="FFDDEBF7"/></patternFill></fill></fills>'
          '<borders count="2"><border/><border><left style="thin"/><right style="thin"/><top style="thin"/><bottom style="thin"/></border></borders>'
          '<cellStyleXfs count="1"><xf numFmtId="0" fontId="0" fillId="0" borderId="0"/></cellStyleXfs>'
          '<cellXfs count="5"><xf numFmtId="0" fontId="0" fillId="0" borderId="0" xfId="0"/>'
          '<xf numFmtId="0" fontId="1" fillId="2" borderId="1" xfId="0" applyFont="1" applyFill="1" applyBorder="1"/>'
          '<xf numFmtId="164" fontId="0" fillId="0" borderId="1" xfId="0" applyNumberFormat="1" applyBorder="1"/>'
          '<xf numFmtId="14" fontId="0" fillId="0" borderId="1" xfId="0" applyNumberFormat="1" applyBorder="1"/>'
          '<xf numFmtId="0" fontId="0" fillId="0" borderId="1" xfId="0" applyBorder="1"/></cellXfs>'
          '</styleSheet>')
CORE = ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
        '<cp:coreProperties xmlns:cp="http://schemas.openxmlformats.org/package/2006/metadata/core-properties" '
        'xmlns:dc="http://purl.org/dc/elements/1.1/" xmlns:dcterms="http://purl.org/dc/terms/" '
        'xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"><dc:title>Synthetic</dc:title>'
        '<dcterms:created xsi:type="dcterms:W3CDTF">2026-11-12T00:00:00Z</dcterms:created></cp:coreProperties>')


def app_xml(generator):
    return ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
            '<Properties xmlns="http://schemas.openxmlformats.org/officeDocument/2006/extended-properties">'
            f'<Application>{generator}</Application><AppVersion>16.0300</AppVersion></Properties>')


LOOKUP_ROWS = 5000
HEAD = ("Ngày", "Mã hàng", "Diễn giải", "Số lượng", "Đơn giá", "Chiết khấu", "Kho", "Nhân viên", "Ghi chú", "Mã KH",
        "Thành tiền", "Sau CK", "Tên hàng", "Tổng theo mã", "Loại")


def write_xlsx(path, rows, formulas, generator, many_styles=False, shared=True):
    rnd = random.Random(7)
    strings, index = [], {}

    def s(text):
        if text not in index:
            index[text] = len(strings)
            strings.append(text)
        return index[text]

    names = [sentence(rnd, 3) for _ in range(LOOKUP_ROWS)]
    notes = [sentence(rnd, 6) for _ in range(20000)]
    ncols = 15 if formulas else 10
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED, compresslevel=6) as z:
        with z.open("xl/worksheets/sheet1.xml", "w", force_zip64=True) as fh:
            w = lambda t: fh.write(t.encode("utf-8"))  # noqa: E731
            w('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n<worksheet xmlns="http://schemas.openxml'
              'formats.org/spreadsheetml/2006/main"><dimension ref="A1:%s%d"/><sheetViews><sheetView workbookViewId="0">'
              '<pane ySplit="1" topLeftCell="A2" activePane="bottomLeft" state="frozen"/></sheetView></sheetViews>'
              '<cols><col min="1" max="%d" width="14" customWidth="1"/></cols><sheetData>' % (col(ncols - 1), rows + 1, ncols))
            w('<row r="1">' + "".join('<c r="%s1" s="1" t="s"><v>%d</v></c>' % (col(i), s(HEAD[i])) for i in range(ncols)) + "</row>")
            last = rows + 1
            qty_by_code = {}
            data = []
            for r in range(2, last + 1):
                code = rnd.randrange(1, LOOKUP_ROWS + 1)
                qty, price, disc = rnd.randrange(1, 500), rnd.randrange(1000, 5_000_000), rnd.choice((0, 0.05, 0.1))
                data.append((code, qty, price, disc))
                qty_by_code[code] = qty_by_code.get(code, 0) + qty * price
            for r, (code, qty, price, disc) in enumerate(data, start=2):
                c = ['<c r="A%d" s="3"><v>%d</v></c>' % (r, 45000 + r % 900),
                     '<c r="B%d" s="4" t="s"><v>%d</v></c>' % (r, s("MH%05d" % code)),
                     '<c r="C%d" s="4" t="s"><v>%d</v></c>' % (r, s(rnd.choice(notes))),
                     '<c r="D%d" s="2"><v>%d</v></c>' % (r, qty),
                     '<c r="E%d" s="2"><v>%d</v></c>' % (r, price),
                     '<c r="F%d"><v>%s</v></c>' % (r, disc),
                     '<c r="G%d" t="s"><v>%d</v></c>' % (r, s("Kho %d" % rnd.randrange(1, 9))),
                     '<c r="H%d" t="s"><v>%d</v></c>' % (r, s("NV%03d" % rnd.randrange(1, 300))),
                     '<c r="I%d"><v>%.4f</v></c>' % (r, rnd.random() * 1e6),
                     '<c r="J%d" t="s"><v>%d</v></c>' % (r, s("KH%04d" % rnd.randrange(1, 3000)))]
                if formulas:
                    first = r == 2
                    amount = qty * price
                    def f(cell, si, template, value, t=""):  # template: the formula with {r} for its row
                        if not shared:  # every cell its own formula text, as some writers do
                            head = "<f>%s</f>" % escape(template.format(r=r))
                        elif first:
                            head = '<f t="shared" ref="%s2:%s%d" si="%d">%s</f>' % (
                                cell, cell, last, si, escape(template.format(r=2)))
                        else:
                            head = '<f t="shared" si="%d"/>' % si
                        return '<c r="%s%d" s="2"%s>%s<v>%s</v></c>' % (cell, r, t, head, value)
                    c += [f("K", 0, "D{r}*E{r}", amount),
                          f("L", 1, "K{r}*(1-F{r})", amount * (1 - disc)),
                          f("M", 2, "VLOOKUP(B{r},DanhMuc!$A$1:$B$%d,2,0)" % LOOKUP_ROWS, escape(names[code - 1]),
                            ' t="str"'),
                          f("N", 3, "SUMIF(B:B,B{r},K:K)", qty_by_code[code]),
                          f("O", 4, 'IF(L{r}>1000000,"Lớn","Nhỏ")', "Lớn" if amount * (1 - disc) > 1e6 else "Nhỏ",
                            ' t="str"')]
                if many_styles:  # every cell its own style out of a few thousand
                    c = [x.replace(' s="2"', ' s="%d"' % rnd.randrange(5, 5 + MANY_XF), 1) if ' s="2"' in x
                         else x.replace('<c r=', '<c s="%d" r=' % rnd.randrange(5, 5 + MANY_XF), 1) if ' s="' not in x
                         else x for x in c]
                w('<row r="%d">%s</row>' % (r, "".join(c)))
            w("</sheetData>")
            if many_styles:
                w(CF_RULES % {"last": last})
            w("</worksheet>")
        sheet2 = ['<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n<worksheet xmlns="http://schemas.openxml'
                  'formats.org/spreadsheetml/2006/main"><sheetData>']
        for i, name in enumerate(names, start=1):
            sheet2.append('<row r="%d"><c r="A%d" t="s"><v>%d</v></c><c r="B%d" t="s"><v>%d</v></c></row>'
                          % (i, i, s("MH%05d" % i), i, s(name)))
        sheet2.append("</sheetData></worksheet>")
        z.writestr("xl/worksheets/sheet2.xml", "".join(sheet2))
        sst = ['<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n<sst xmlns="http://schemas.openxmlformats.org/'
               'spreadsheetml/2006/main" count="%d" uniqueCount="%d">' % (len(strings), len(strings))]
        sst += ["<si><t>%s</t></si>" % escape(t) for t in strings]
        sst.append("</sst>")
        z.writestr("xl/sharedStrings.xml", "".join(sst))
        for name, text in (("[Content_Types].xml", CT), ("_rels/.rels", RELS), ("xl/workbook.xml", WB),
                           ("xl/_rels/workbook.xml.rels", WB_RELS),
                           ("xl/styles.xml", many_styles_xml(rnd) if many_styles else STYLES),
                           ("docProps/core.xml", CORE), ("docProps/app.xml", app_xml(generator))):
            z.writestr(name, text)


MANY_XF = 4000
CF_RULES = ('<conditionalFormatting sqref="K2:K%(last)d"><cfRule type="cellIs" dxfId="0" priority="1" operator="greaterThan">'
            '<formula>100000000</formula></cfRule></conditionalFormatting>'
            '<conditionalFormatting sqref="L2:L%(last)d"><cfRule type="top10" dxfId="1" priority="2" rank="100"/>'
            '</conditionalFormatting>'
            '<conditionalFormatting sqref="D2:D%(last)d"><cfRule type="dataBar" priority="3"><dataBar><cfvo type="min"/>'
            '<cfvo type="max"/><color rgb="FF638EC6"/></dataBar></cfRule></conditionalFormatting>'
            '<conditionalFormatting sqref="A2:O%(last)d"><cfRule type="expression" dxfId="0" priority="4">'
            '<formula>$F2&gt;0.05</formula></cfRule></conditionalFormatting>'
            '<conditionalFormatting sqref="N2:N%(last)d"><cfRule type="duplicateValues" dxfId="1" priority="5"/>'
            '</conditionalFormatting>'
            '<dataValidations count="1"><dataValidation type="list" allowBlank="1" sqref="G2:G%(last)d">'
            '<formula1>"Kho 1,Kho 2,Kho 3,Kho 4,Kho 5,Kho 6,Kho 7,Kho 8"</formula1></dataValidation></dataValidations>')


def many_styles_xml(rnd):
    """styles.xml with the 5 base formats plus MANY_XF combinations of fonts, fills, borders and number formats."""
    fonts = ['<font><sz val="11"/><name val="Calibri"/></font>', '<font><b/><sz val="11"/><name val="Calibri"/></font>']
    fonts += ['<font>%s<sz val="%d"/><color rgb="FF%06X"/><name val="%s"/></font>'
              % (rnd.choice(("", "<b/>", "<i/>", "<u/>")), rnd.choice((9, 10, 11, 12, 13)), rnd.randrange(1 << 24),
                 rnd.choice(("Calibri", "Arial", "Times New Roman", "Tahoma"))) for _ in range(200)]
    fills = ['<fill><patternFill patternType="none"/></fill>', '<fill><patternFill patternType="gray125"/></fill>']
    fills += ['<fill><patternFill patternType="solid"><fgColor rgb="FF%06X"/></patternFill></fill>'
              % rnd.randrange(1 << 24) for _ in range(300)]
    borders = ['<border/>', '<border><left style="thin"/><right style="thin"/><top style="thin"/><bottom style="thin"/></border>']
    borders += ['<border><left style="%s"/><right style="thin"/><top style="hair"/><bottom style="%s"/></border>'
                % (rnd.choice(("thin", "medium", "dashed")), rnd.choice(("thin", "double"))) for _ in range(40)]
    xfs = ['<xf numFmtId="0" fontId="0" fillId="0" borderId="0" xfId="0"/>',
           '<xf numFmtId="0" fontId="1" fillId="2" borderId="1" xfId="0" applyFont="1" applyFill="1" applyBorder="1"/>',
           '<xf numFmtId="164" fontId="0" fillId="0" borderId="1" xfId="0" applyNumberFormat="1" applyBorder="1"/>',
           '<xf numFmtId="14" fontId="0" fillId="0" borderId="1" xfId="0" applyNumberFormat="1" applyBorder="1"/>',
           '<xf numFmtId="0" fontId="0" fillId="0" borderId="1" xfId="0" applyBorder="1"/>']
    xfs += ['<xf numFmtId="%d" fontId="%d" fillId="%d" borderId="%d" xfId="0" applyNumberFormat="1" applyFont="1" '
            'applyFill="1" applyBorder="1"/>' % (rnd.choice((0, 3, 4, 10, 14, 164)), rnd.randrange(len(fonts)),
                                                 rnd.randrange(len(fills)), rnd.randrange(len(borders)))
            for _ in range(MANY_XF)]
    return ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
            '<styleSheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
            '<numFmts count="1"><numFmt numFmtId="164" formatCode="#,##0"/></numFmts>'
            '<fonts count="%d">%s</fonts><fills count="%d">%s</fills><borders count="%d">%s</borders>'
            '<cellStyleXfs count="1"><xf numFmtId="0" fontId="0" fillId="0" borderId="0"/></cellStyleXfs>'
            '<cellXfs count="%d">%s</cellXfs>'
            '<dxfs count="2"><dxf><font><b/><color rgb="FF9C0006"/></font><fill><patternFill><bgColor rgb="FFFFC7CE"/>'
            '</patternFill></fill></dxf><dxf><fill><patternFill><bgColor rgb="FFC6EFCE"/></patternFill></fill></dxf></dxfs>'
            '</styleSheet>' % (len(fonts), "".join(fonts), len(fills), "".join(fills), len(borders), "".join(borders),
                               len(xfs), "".join(xfs)))


def write_xlsx_sheets(path, nsheets, rows):
    """nsheets data sheets (rows x 8, shared formulas) and a summary sheet with SUM/SUMIF over each of them."""
    rnd = random.Random(19)
    ws_ct = "application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"
    names = ["Thang%02d_%02d" % (1 + i % 12, i) for i in range(nsheets)] + ["TongHop"]
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED, compresslevel=6) as z:
        for i, name in enumerate(names[:-1], start=1):
            out = ['<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n<worksheet xmlns="http://schemas.openxml'
                   'formats.org/spreadsheetml/2006/main"><sheetData>']
            for r in range(1, rows + 1):
                a, b = rnd.randrange(1, 1000), rnd.randrange(1000, 100000)
                fe = ('<f t="shared" ref="E1:E%d" si="0">C1*D1</f>' % rows) if r == 1 else '<f t="shared" si="0"/>'
                ff = ('<f t="shared" ref="F1:F%d" si="1">SUM($E$1:E1)</f>' % rows) if r == 1 else '<f t="shared" si="1"/>'
                out.append('<row r="%d"><c r="A%d"><v>%d</v></c><c r="B%d" t="inlineStr"><is><t>MH%04d</t></is></c>'
                           '<c r="C%d"><v>%d</v></c><c r="D%d"><v>%d</v></c><c r="E%d">%s<v>%d</v></c>'
                           '<c r="F%d">%s<v>0</v></c><c r="G%d"><v>%.3f</v></c><c r="H%d"><v>%d</v></c></row>'
                           % (r, r, 45000 + r, r, rnd.randrange(1, 500), r, a, r, b, r, fe, a * b, r, ff, r,
                              rnd.random(), r, rnd.randrange(1 << 20)))
            out.append("</sheetData></worksheet>")
            z.writestr("xl/worksheets/sheet%d.xml" % i, "".join(out))
        summary = ['<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n<worksheet xmlns="http://schemas.openxml'
                   'formats.org/spreadsheetml/2006/main"><sheetData>']
        for i, name in enumerate(names[:-1], start=1):
            summary.append('<row r="%d"><c r="A%d" t="inlineStr"><is><t>%s</t></is></c><c r="B%d"><f>SUM(%s!E:E)</f>'
                           '<v>0</v></c><c r="C%d"><f>SUMIF(%s!B:B,"MH0001",%s!E:E)</f><v>0</v></c></row>'
                           % (i, i, name, i, name, i, name, name))
        summary.append("</sheetData></worksheet>")
        z.writestr("xl/worksheets/sheet%d.xml" % len(names), "".join(summary))
        ct = CT.split("<Override PartName=\"/xl/worksheets")[0] + "".join(
            '<Override PartName="/xl/worksheets/sheet%d.xml" ContentType="%s"/>' % (i, ws_ct)
            for i in range(1, len(names) + 1)) + CT[CT.index('<Override PartName="/xl/styles.xml"'):]
        ct = ct.replace('<Override PartName="/xl/sharedStrings.xml" ContentType="application/vnd.openxmlformats-'
                        'officedocument.spreadsheetml.sharedStrings+xml"/>', "")
        wb = WB.split("<sheets>")[0] + "<sheets>" + "".join(
            '<sheet name="%s" sheetId="%d" r:id="rId%d"/>' % (n, i, i) for i, n in enumerate(names, start=1)) + \
            '</sheets><calcPr calcId="191029" fullCalcOnLoad="0"/></workbook>'
        rels = WB_RELS.split("<Relationship ")[0] + "".join(
            '<Relationship Id="rId%d" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/'
            'worksheet" Target="worksheets/sheet%d.xml"/>' % (i, i) for i in range(1, len(names) + 1)) + \
            '<Relationship Id="rId%d" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/' \
            'styles" Target="styles.xml"/></Relationships>' % (len(names) + 1)
        for name, text in (("[Content_Types].xml", ct), ("_rels/.rels", RELS), ("xl/workbook.xml", wb),
                           ("xl/_rels/workbook.xml.rels", rels), ("xl/styles.xml", STYLES),
                           ("docProps/core.xml", CORE), ("docProps/app.xml", app_xml("Microsoft Excel"))):
            z.writestr(name, text)


def retarget_generator(src, dst, generator):
    with zipfile.ZipFile(src) as zin, zipfile.ZipFile(dst, "w", zipfile.ZIP_DEFLATED, compresslevel=6) as zout:
        for item in zin.infolist():
            data = app_xml(generator).encode() if item.filename == "docProps/app.xml" else zin.read(item.filename)
            zout.writestr(item, data)


# ---------------------------------------------------------------- pictures, docx, pptx, pdf
def noise_jpeg(rnd, w, h, quality=85):
    from PIL import Image, ImageFilter
    img = Image.frombytes("RGB", (w // 4, h // 4), rnd.randbytes((w // 4) * (h // 4) * 3))
    img = img.resize((w, h), Image.BILINEAR).filter(ImageFilter.GaussianBlur(1))
    buf = io.BytesIO()
    img.save(buf, "JPEG", quality=quality)
    return buf.getvalue()


def write_docx(path, pages, images):
    import docx
    from docx.shared import Cm
    rnd = random.Random(11)
    doc = docx.Document()
    pics = [noise_jpeg(rnd, 1800, 1200, 80) for _ in range(8)] if images else []
    for p in range(pages):
        doc.add_heading("Mục %d. %s" % (p + 1, sentence(rnd, 4)), level=1 + p % 2)
        if images:
            doc.add_picture(io.BytesIO(rnd.choice(pics) + rnd.randbytes(64)), width=Cm(15))
            doc.add_paragraph(sentence(rnd, 30))
            doc.add_page_break()
            continue
        for _ in range(5):
            doc.add_paragraph(sentence(rnd, 60))
        if p % 4 == 0:
            t = doc.add_table(rows=8, cols=5)
            t.style = "Table Grid"
            for row in t.rows:
                for cell in row.cells:
                    cell.text = sentence(rnd, 2)
    doc.save(path)


def write_pptx(path, slides):
    from pptx import Presentation
    from pptx.util import Inches
    rnd = random.Random(13)
    prs = Presentation()
    prs.slide_width, prs.slide_height = Inches(13.333), Inches(7.5)
    for i in range(slides):
        slide = prs.slides.add_slide(prs.slide_layouts[5])
        slide.shapes.title.text = "Trang %d: %s" % (i + 1, sentence(rnd, 4))
        slide.shapes.add_picture(io.BytesIO(noise_jpeg(rnd, 2400, 1400, 80)), Inches(1), Inches(1.5), width=Inches(11))
    prs.save(path)


def write_txt(path, megabytes, line_words):
    """Vietnamese UTF-8 plain text of about <megabytes> MB, lines of <line_words> words (one paragraph each)."""
    rnd = random.Random(23)
    target = megabytes * 1_000_000
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        size = 0
        while size < target:
            line = sentence(rnd, line_words) + ".\n"
            f.write(line)
            size += len(line.encode("utf-8"))


def write_pdf(path, pages):
    rnd = random.Random(17)
    objs = []  # (number, bytes)

    def obj(body):
        objs.append(body)
        return len(objs)

    font = obj(b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica /Encoding /WinAnsiEncoding >>")
    pics = []
    for _ in range(6):
        jpg = noise_jpeg(rnd, 2000, 1400)
        pics.append(obj(b"<< /Type /XObject /Subtype /Image /Width 2000 /Height 1400 /ColorSpace /DeviceRGB "
                        b"/BitsPerComponent 8 /Filter /DCTDecode /Length %d >>\nstream\n" % len(jpg) + jpg
                        + b"\nendstream"))
    pages_id = len(objs) + 2 * pages + 1  # filled in after the pages
    kids = []
    for p in range(pages):
        lines = [b"BT /F1 10 Tf 50 800 Td 12 TL"]
        for _ in range(55):
            text = sentence(rnd, 12).encode("cp1252", "replace").replace(b"(", b"").replace(b")", b"")
            lines.append(b"(" + text + b") '")
        lines.append(b"ET")
        res = b"/Font << /F1 %d 0 R >>" % font
        if p % 5 == 0:
            pic = rnd.choice(pics)
            lines.append(b"q 495 0 0 346 50 50 cm /Im1 Do Q")
            res += b" /XObject << /Im1 %d 0 R >>" % pic
        stream = b"\n".join(lines)
        content = obj(b"<< /Length %d >>\nstream\n" % len(stream) + stream + b"\nendstream")
        kids.append(obj(b"<< /Type /Page /Parent %d 0 R /MediaBox [0 0 595 842] /Resources << %s >> /Contents %d 0 R >>"
                        % (pages_id, res, content)))
    assert len(objs) + 1 == pages_id
    obj(b"<< /Type /Pages /Count %d /Kids [%s] >>" % (pages, b" ".join(b"%d 0 R" % k for k in kids)))
    root = obj(b"<< /Type /Catalog /Pages %d 0 R >>" % pages_id)
    out = bytearray(b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n")
    offsets = []
    for i, body in enumerate(objs, start=1):
        offsets.append(len(out))
        out += b"%d 0 obj\n" % i + body + b"\nendobj\n"
    xref = len(out)
    out += b"xref\n0 %d\n0000000000 65535 f \n" % (len(objs) + 1)
    out += b"".join(b"%010d 00000 n \n" % o for o in offsets)
    out += b"trailer\n<< /Size %d /Root %d 0 R >>\nstartxref\n%d\n%%%%EOF\n" % (len(objs) + 1, root, xref)
    with open(path, "wb") as f:
        f.write(out)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("out")
    ap.add_argument("--rows", type=int, default=200000)
    ap.add_argument("--pages", type=int, default=1500)
    ap.add_argument("--image-pages", type=int, default=40)
    ap.add_argument("--slides", type=int, default=30)
    ap.add_argument("--pdf-pages", type=int, default=1500)
    ap.add_argument("--skip", default="", help="comma list of fixture names not to write")
    ap.add_argument("--only", default="", help="comma list of the fixture names to write (default: all)")
    a = ap.parse_args()
    os.makedirs(a.out, exist_ok=True)
    only = set(filter(None, a.only.split(",")))
    jobs = {
        "calc-values.xlsx": lambda p: write_xlsx(p, a.rows, False, "Microsoft Excel"),
        "calc-formulas.xlsx": lambda p: write_xlsx(p, a.rows, True, "Microsoft Excel"),
        "calc-formulas-plain.xlsx": lambda p: write_xlsx(p, a.rows, True, "Microsoft Excel", shared=False),
        "calc-formulas-other.xlsx": lambda p: retarget_generator(os.path.join(a.out, "calc-formulas.xlsx"), p,
                                                                 "SyntheticExport"),
        "calc-styles.xlsx": lambda p: write_xlsx(p, a.rows // 2, True, "Microsoft Excel", many_styles=True),
        "calc-sheets.xlsx": lambda p: write_xlsx_sheets(p, 60, 4000),
        "writer-text.docx": lambda p: write_docx(p, a.pages, False),
        "writer-images.docx": lambda p: write_docx(p, a.image_pages, True),
        "slides-images.pptx": lambda p: write_pptx(p, a.slides),
        "pdf-mixed.pdf": lambda p: write_pdf(p, a.pdf_pages),
        # plain text in Writer: short lines (many paragraphs) and long lines (~60 KB paragraphs)
        "text-lines-10mb.txt": lambda p: write_txt(p, 10, 14),
        "text-longlines-10mb.txt": lambda p: write_txt(p, 10, 6000),
        "text-lines-50mb.txt": lambda p: write_txt(p, 50, 14),
        "text-oneline-10mb.txt": lambda p: write_txt(p, 10, 1_500_000),  # no line break at all
    }
    for name, job in jobs.items():
        if (only and name not in only) or name in a.skip.split(","):
            continue
        path = os.path.join(a.out, name)
        job(path)
        print("%-26s %8.1f MB" % (name, os.path.getsize(path) / 1e6), flush=True)


if __name__ == "__main__":
    sys.exit(main())
