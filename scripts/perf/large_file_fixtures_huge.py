# SPDX-License-Identifier: LicenseRef-HST-Proprietary
# Copyright (C) 2026 HASON TECH
"""Spreadsheets of 50-200 MB for scripts/perf/large-file-open.py, written as a stream (no per-file memory growth).

    python large_file_fixtures_huge.py <out-dir> [--sizes 50,100,200] [--only xlsx-ketoan,xlsx-congthuc,docx-text,...]

Kinds (all generated, no user data):
- xlsx-ketoan: an accounting/HR export, 20 columns per row, mostly distinct strings (voucher numbers, descriptions,
  notes), at most 500 000 rows per sheet, a SUM row at the end of every sheet.
- xlsx-congthuc: a sales ledger with 7 formulas per row (multiplication, VLOOKUP into a catalogue sheet, IF, TEXT,
  ROUND), every formula shared and stored with its cached result.
- every kind of large_file_fixtures_sized.py (docx-text, docx-images, pptx-images, ...) at the same sizes.
Files are fitted to the target size with large_file_fixtures_sized.sized(). Shared strings are spooled to a temporary
file while the sheets are written, so 200 MB files need only a small, constant amount of memory.
"""
import argparse
import datetime
import os
import random
import sys
import tempfile
import zipfile
from xml.sax.saxutils import escape

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from large_file_fixture_words import col, sentence  # noqa: E402
from large_file_fixtures_sized import KINDS as SIZED_KINDS, sized  # noqa: E402
from large_file_fixtures_xlsx_parts import CORE, RELS, STYLES, app_xml  # noqa: E402

NS = 'xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"'
MAX_ROWS = 500_000
CATALOGUE = 3000
KETOAN_HEAD = ("Ngày", "Số chứng từ", "Diễn giải", "TK Nợ", "TK Có", "Số tiền", "Mã KH", "Tên khách hàng", "Mã NV",
               "Họ tên nhân viên", "Phòng ban", "Mã hàng", "Tên hàng", "ĐVT", "Số lượng", "Đơn giá", "Thành tiền",
               "Thuế GTGT", "Ghi chú", "Trạng thái")
CONGTHUC_HEAD = ("Ngày", "Mã hàng", "Số lượng", "Đơn giá", "Ghi chú", "Thành tiền", "Thuế GTGT", "Tổng cộng",
                 "Tên hàng", "Loại", "Kỳ", "Chiết khấu")


class Strings:
    """Shared strings: repeated values (catalogues) are indexed once, unique values are only spooled to disk."""

    def __init__(self, spool):
        self.spool, self.count, self.index = spool, 0, {}

    def unique(self, text):
        self.spool.write("<si><t>%s</t></si>" % escape(text))
        self.count += 1
        return self.count - 1

    def shared(self, text):
        if text not in self.index:
            self.index[text] = self.unique(text)
        return self.index[text]


def sheet_head(ncols, nrows):
    return ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n<worksheet %s><dimension ref="A1:%s%d"/>'
            '<sheetViews><sheetView workbookViewId="0"><pane ySplit="1" topLeftCell="A2" activePane="bottomLeft" '
            'state="frozen"/></sheetView></sheetViews><sheetFormatPr defaultRowHeight="15"/><cols><col min="1" '
            'max="%d" width="16" customWidth="1"/></cols><sheetData>' % (NS, col(ncols - 1), nrows, ncols))


def ketoan_row(r, rnd, st, people, customers, items):
    qty, price = rnd.randrange(1, 300), rnd.randrange(1, 2000) * 1000
    amount = qty * price
    cust, emp, item = rnd.choice(customers), rnd.choice(people), rnd.choice(items)
    cells = ((3, None, 44927 + r % 1460), (4, "s", st.unique("CT%07d-%d" % (r, rnd.randrange(1000)))),
             (4, "s", st.unique(sentence(rnd, 8))), (4, "s", st.shared(rnd.choice(("131", "331", "111", "112")))),
             (4, "s", st.shared(rnd.choice(("511", "156", "632", "642")))), (2, None, amount * 11 // 10),
             (4, "s", st.shared(cust[0])), (4, "s", st.shared(cust[1])), (4, "s", st.shared(emp[0])),
             (4, "s", st.shared(emp[1])), (4, "s", st.shared(emp[2])), (4, "s", st.shared(item[0])),
             (4, "s", st.shared(item[1])), (4, "s", st.shared(rnd.choice(("cái", "hộp", "kg", "thùng")))),
             (2, None, qty), (2, None, price), (2, None, amount), (2, None, amount // 10),
             (4, "s", st.unique(sentence(rnd, 5) + " %d" % rnd.randrange(10 ** 6))),
             (4, "s", st.shared(rnd.choice(("Đã duyệt", "Chờ duyệt", "Đã hủy")))))
    return "".join('<c r="%s%d" s="%d"%s><v>%s</v></c>' % (col(i), r, s, ' t="s"' if t else "", v)
                   for i, (s, t, v) in enumerate(cells))


def congthuc_row(r, rnd, st, items, last):
    code = rnd.randrange(CATALOGUE)
    qty, price = rnd.randrange(1, 300), rnd.randrange(1, 2000) * 1000
    amount = qty * price
    total = amount + amount * 0.1
    serial = 44927 + r % 1460
    day = datetime.date(1899, 12, 30) + datetime.timedelta(days=serial)  # the cached TEXT(A,"mm/yyyy") result
    year, month = day.year, day.month
    out = ['<c r="A%d" s="3"><v>%d</v></c>' % (r, serial), '<c r="B%d" s="4" t="s"><v>%d</v></c>'
           % (r, st.shared(items[code][0])), '<c r="C%d" s="2"><v>%d</v></c>' % (r, qty),
           '<c r="D%d" s="2"><v>%d</v></c>' % (r, price),
           '<c r="E%d" s="4" t="s"><v>%d</v></c>' % (r, st.unique(sentence(rnd, 6) + " %d" % r))]
    formulas = (("F", "C{r}*D{r}", amount, ""), ("G", "F{r}*0.1", amount * 0.1, ""), ("H", "F{r}+G{r}", total, ""),
                ("I", "VLOOKUP(B{r},DanhMuc!$A$1:$B$%d,2,0)" % CATALOGUE, escape(items[code][1]), ' t="str"'),
                ("J", 'IF(H{r}>1000000,"Lớn","Nhỏ")', "Lớn" if total > 1e6 else "Nhỏ", ' t="str"'),
                ("K", 'TEXT(A{r},"mm/yyyy")', "%02d/%d" % (month, year), ' t="str"'),
                ("L", "ROUND(H{r}*IF(C{r}>100,0.05,0),0)", round(total * (0.05 if qty > 100 else 0)), ""))
    for si, (c, template, value, t) in enumerate(formulas):
        if "!" in template:  # Excel rejects a shared formula that refers to another sheet: write it per cell
            head = "<f>%s</f>" % escape(template.format(r=r))
        elif r == 2:
            head = '<f t="shared" ref="%s2:%s%d" si="%d">%s</f>' % (c, c, last, si, escape(template.format(r=2)))
        else:
            head = '<f t="shared" si="%d"/>' % si
        out.append('<c r="%s%d" s="2"%s>%s<v>%s</v></c>' % (c, r, t, head, value))
    return "".join(out)


def write_huge_xlsx(path, rows, kind):
    rnd = random.Random(11)
    people = [("NV%04d" % i, sentence(rnd, 3), "Phòng " + sentence(rnd, 1)) for i in range(400)]
    customers = [("KH%05d" % i, "Công ty " + sentence(rnd, 3)) for i in range(5000)]
    items = [("MH%05d" % i, sentence(rnd, 4)) for i in range(CATALOGUE)]
    head = KETOAN_HEAD if kind == "ketoan" else CONGTHUC_HEAD
    nsheets = max(1, -(-rows // MAX_ROWS))
    names = ["DuLieu%d" % (i + 1) for i in range(nsheets)] + (["DanhMuc"] if kind == "congthuc" else [])
    with tempfile.TemporaryFile("w+", encoding="utf-8", dir=os.path.dirname(os.path.abspath(path))) as spool, \
            zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED, compresslevel=6) as z:
        st = Strings(spool)
        for n in range(nsheets):
            nrows = min(MAX_ROWS, rows - n * MAX_ROWS)
            last = nrows + 1
            with z.open("xl/worksheets/sheet%d.xml" % (n + 1), "w", force_zip64=True) as fh:
                w = lambda t: fh.write(t.encode("utf-8"))  # noqa: E731
                w(sheet_head(len(head), last + 1))
                w('<row r="1">' + "".join('<c r="%s1" s="1" t="s"><v>%d</v></c>' % (col(i), st.shared(h))
                                          for i, h in enumerate(head)) + "</row>")
                for r in range(2, last + 1):
                    w('<row r="%d">%s</row>' % (r, ketoan_row(r, rnd, st, people, customers, items)
                                                 if kind == "ketoan" else congthuc_row(r, rnd, st, items, last)))
                total_col = col(16 if kind == "ketoan" else 7)
                w('<row r="%d"><c r="A%d" s="1" t="s"><v>%d</v></c><c r="%s%d" s="2"><f>SUM(%s2:%s%d)</f></c></row>'
                  % (last + 1, last + 1, st.shared("Tổng cộng"), total_col, last + 1, total_col, total_col, last))
                w("</sheetData></worksheet>")
        if kind == "congthuc":
            cat = ['<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n<worksheet %s><sheetData>' % NS]
            cat += ['<row r="%d"><c r="A%d" t="s"><v>%d</v></c><c r="B%d" t="s"><v>%d</v></c></row>'
                    % (i, i, st.shared(code), i, st.shared(name)) for i, (code, name) in enumerate(items, start=1)]
            z.writestr("xl/worksheets/sheet%d.xml" % len(names), "".join(cat) + "</sheetData></worksheet>")
        with z.open("xl/sharedStrings.xml", "w", force_zip64=True) as fh:
            fh.write(('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n<sst %s count="%d" uniqueCount="%d">'
                      % (NS, st.count, st.count)).encode())
            spool.seek(0)
            for chunk in iter(lambda: spool.read(1 << 20), ""):
                fh.write(chunk.encode("utf-8"))
            fh.write(b"</sst>")
        write_package_parts(z, names)


def write_package_parts(z, names):
    ws = "application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"
    rel = "http://schemas.openxmlformats.org/officeDocument/2006/relationships/"
    sml = "application/vnd.openxmlformats-officedocument.spreadsheetml."
    n = len(names)
    ct = ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n<Types xmlns="http://schemas.openxmlformats.org/'
          'package/2006/content-types"><Default Extension="rels" ContentType="application/vnd.openxmlformats-package.'
          'relationships+xml"/><Default Extension="xml" ContentType="application/xml"/><Override PartName="/xl/'
          'workbook.xml" ContentType="%ssheet.main+xml"/>' % sml
          + "".join('<Override PartName="/xl/worksheets/sheet%d.xml" ContentType="%s"/>' % (i, ws) for i in range(1, n + 1))
          + '<Override PartName="/xl/styles.xml" ContentType="%sstyles+xml"/><Override PartName="/xl/sharedStrings.xml"'
          ' ContentType="%ssharedStrings+xml"/><Override PartName="/docProps/core.xml" ContentType="application/vnd.'
          'openxmlformats-package.core-properties+xml"/><Override PartName="/docProps/app.xml" ContentType="application/'
          'vnd.openxmlformats-officedocument.extended-properties+xml"/></Types>' % (sml, sml))
    wb = ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n<workbook %s xmlns:r="%s"><sheets>' % (NS, rel[:-1])
          + "".join('<sheet name="%s" sheetId="%d" r:id="rId%d"/>' % (s, i, i) for i, s in enumerate(names, start=1))
          + '</sheets><calcPr calcId="191029"/></workbook>')
    rels = ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n<Relationships xmlns="http://schemas.'
            'openxmlformats.org/package/2006/relationships">'
            + "".join('<Relationship Id="rId%d" Type="%sworksheet" Target="worksheets/sheet%d.xml"/>' % (i, rel, i)
                      for i in range(1, n + 1))
            + '<Relationship Id="rId%d" Type="%sstyles" Target="styles.xml"/><Relationship Id="rId%d" Type="%s'
              'sharedStrings" Target="sharedStrings.xml"/></Relationships>' % (n + 1, rel, n + 2, rel))
    for name, text in (("[Content_Types].xml", ct), ("_rels/.rels", RELS), ("xl/workbook.xml", wb),
                       ("xl/_rels/workbook.xml.rels", rels), ("xl/styles.xml", STYLES), ("docProps/core.xml", CORE),
                       ("docProps/app.xml", app_xml("Microsoft Excel"))):
        z.writestr(name, text)


KINDS = {
    "xlsx-ketoan": ("xlsx", lambda p, u: write_huge_xlsx(p, u, "ketoan"), (20000, 40000)),
    "xlsx-congthuc": ("xlsx", lambda p, u: write_huge_xlsx(p, u, "congthuc"), (20000, 40000)),
    **SIZED_KINDS,
}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("out")
    ap.add_argument("--sizes", default="50,100,200")
    ap.add_argument("--only", default="xlsx-ketoan,xlsx-congthuc,docx-text,docx-images,pptx-images")
    a = ap.parse_args()
    out = os.path.abspath(a.out)
    os.makedirs(out, exist_ok=True)
    for kind in filter(None, a.only.split(",")):
        ext, build, calib = KINDS[kind]
        for mb in (int(x) for x in a.sizes.split(",")):
            path = os.path.join(out, "%s-%dmb.%s" % (kind, mb, ext))
            if os.path.exists(path):
                continue
            units, size = sized(path + ".tmp", build, calib, mb * 1_000_000)
            os.replace(path + ".tmp", path)
            print("%-26s %7.1f MB  units=%d" % (os.path.basename(path), size / 1e6, units), flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
