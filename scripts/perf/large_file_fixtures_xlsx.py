# SPDX-License-Identifier: AGPL-3.0-only
"""Spreadsheet fixtures of scripts/perf/large_file_fixtures.py, written by hand: cached results, shared formulas."""
import random
import zipfile
from xml.sax.saxutils import escape

from large_file_fixture_words import col, sentence
from large_file_fixtures_xlsx_parts import (CF_RULES, CORE, CT, HEAD, LOOKUP_ROWS, MANY_XF, RELS, STYLES, WB, WB_RELS,
                                           app_xml, many_styles_xml)


def write_xlsx(path, rows, formulas, generator, many_styles=False, shared=True, results=True):
    """results=False: formulas without cached results (as some exporters write them), all calculated on load."""
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
                        if not results:
                            return '<c r="%s%d" s="2">%s</c>' % (cell, r, head)
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
