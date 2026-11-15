# SPDX-License-Identifier: AGPL-3.0-only
"""Cases of check-sheets-excel-functions.py: every function added for the leading spreadsheet application.

Formulas use ';' between arguments and '.' as decimal point; the runner converts them to the locale. DATA fills
H1:J6 (header row, then region/product/quantity). Each case: (formula, expected display text, .xlsx substring or
None). ONLINE builds a synthetic .xlsx whose cells use functions of the reference vendor's online services.
"""
import zipfile

DATA = [["Region", "Product", "Qty"], ["N", "x", 1], ["S", "y", 2], ["N", "y", 3], ["S", "x", 4], ["N", "x", 5]]

NEW = ["ARRAYTOTEXT", "VALUETOTEXT", "DBCS", "PHONETIC", "PERCENTOF", "REGEXTEST", "REGEXEXTRACT",
       "REGEXREPLACE", "TRIMRANGE", "BINOM.DIST.RANGE"]

CASES = [
    ('=ARRAYTOTEXT(J2:J4)', "1{sep} 2{sep} 3", "_xlfn.ARRAYTOTEXT(J2:J4)"),
    ('=VALUETOTEXT(H2;1)', '"N"', "_xlfn.VALUETOTEXT(H2,1)"),
    ('=VALUETOTEXT(1/0)', "#DIV/0!", None),
    ('=DBCS("AB")', "ＡＢ", "_xlfn.DBCS("),
    ('=PHONETIC(H2)', "N", "PHONETIC(H2)"),
    ('=PERCENTOF(J2:J3;J2:J6)', "0{dec}2", "_xlfn.PERCENTOF(J2:J3,J2:J6)"),
    ('=REGEXTEST("Tiền 500";"[0-9]+")', "TRUE", "_xlfn.REGEXTEST("),
    ('=REGEXEXTRACT("mã HS-2026";"[0-9]+")', "2026", "_xlfn.REGEXEXTRACT("),
    ('=REGEXREPLACE("0912 345 678";" ";"")', "0912345678", "_xlfn.REGEXREPLACE("),
    ('=ROWS(TRIMRANGE(H1:H40))', "6", "_xlfn.TRIMRANGE(H1:H40)"),
    ('=BINOM.DIST.RANGE(10;0.5;2;4)', "0{dec}3662109375", "_xlfn.BINOM.DIST.RANGE(10,0.5,2,4)"),
    ('=INFO("system")', "pcdos", None),
]
# Per locale: CODE/CHAR follow the Windows ANSI code page of the locale (vi-VN 1258, en-US 1252).
CODEPAGE = {
    "vi-VN": [('=CODE("Đ")', "208"), ('=CHAR(208)', "Đ"), ('=CODE("A")', "65")],
    "en-US": [('=CODE("Đ")', "63"), ('=CHAR(233)', "é"), ('=CODE("é")', "233")],
}

ONLINE = [  # (formula as stored, cached value, cell type)
    ('_xlfn.STOCKHISTORY("MSFT",DATE(2024,1,2),DATE(2024,1,2),0,0,1)', "370.87", "n"),
    ('_xlfn.TRANSLATE("hello","en","vi")', "xin chào", "str"),
    ('CUBEVALUE("ThisWorkbookDataModel","[Measures].[Sum of Qty]")', "42", "n"),
    ('_xlfn.COPILOT("Summarize",B1)', "tóm tắt", "str"),
    ('RTD("hst.rtd",,"x")', "7", "n"),
]


def xml_escape(text):
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")


def build_online_xlsx(path):
    text_type = ' t="str"'
    rows = "".join(f'<row r="{i}"><c r="A{i}"{text_type if t == "str" else ""}><f>{xml_escape(f)}</f>'
                   f'<v>{xml_escape(v)}</v></c></row>' for i, (f, v, t) in enumerate(ONLINE, 1))
    rel = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
    ct = "application/vnd.openxmlformats-officedocument"
    files = {
        "[Content_Types].xml": '<?xml version="1.0" encoding="UTF-8"?><Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
        '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
        '<Default Extension="xml" ContentType="application/xml"/>'
        f'<Override PartName="/xl/workbook.xml" ContentType="{ct}.spreadsheetml.sheet.main+xml"/>'
        f'<Override PartName="/xl/worksheets/sheet1.xml" ContentType="{ct}.spreadsheetml.worksheet+xml"/>'
        f'<Override PartName="/docProps/app.xml" ContentType="{ct}.extended-properties+xml"/></Types>',
        "_rels/.rels": '<?xml version="1.0" encoding="UTF-8"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
        f'<Relationship Id="rId1" Type="{rel}/officeDocument" Target="xl/workbook.xml"/>'
        f'<Relationship Id="rId2" Type="{rel}/extended-properties" Target="docProps/app.xml"/></Relationships>',
        # The generator name decides whether cached text results are trusted on import.
        "docProps/app.xml": '<?xml version="1.0" encoding="UTF-8"?><Properties xmlns="http://schemas.openxmlformats.org/'
        'officeDocument/2006/extended-properties"><Application>Microsoft Excel</Application><AppVersion>16.0300</AppVersion></Properties>',
        "xl/workbook.xml": f'<?xml version="1.0" encoding="UTF-8"?><workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" xmlns:r="{rel}">'
        '<sheets><sheet name="Sheet1" sheetId="1" r:id="rId1"/></sheets></workbook>',
        "xl/_rels/workbook.xml.rels": '<?xml version="1.0" encoding="UTF-8"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
        f'<Relationship Id="rId1" Type="{rel}/worksheet" Target="worksheets/sheet1.xml"/></Relationships>',
        "xl/worksheets/sheet1.xml": '<?xml version="1.0" encoding="UTF-8" standalone="yes"?><worksheet xmlns='
        f'"http://schemas.openxmlformats.org/spreadsheetml/2006/main"><sheetData>{rows}</sheetData></worksheet>',
    }
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as archive:
        for name, data in files.items():
            archive.writestr(name, data)
