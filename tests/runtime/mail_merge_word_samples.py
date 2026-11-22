# SPDX-License-Identifier: LicenseRef-HST-Proprietary
# Copyright (C) 2026 HASON TECH
"""Word-made mail-merge samples, written by the OOXML spec the way Word 2016+ writes them: a letter .docx whose
w:mailMerge settings name an Excel (or CSV) recipient list, MERGEFIELDs with \\# \\@ \\* \\b \\f switches and IF
fields with nested MERGEFIELDs; the recipient list as .xlsx (dates, numbers, a Text-formatted column) and as .csv.

EXPECTED holds, per recipient, the paragraph texts Word 2016 (vi-VN) gives the letter's paragraphs when it merges
it; word_output() the paragraphs of Word's merged document: like Word, a paragraph made only of merge fields that all
came out empty is left out, unless the letter has w:doNotSuppressBlankLines (ECMA-376 17.14.12). The runtime check
(check-mail-merge-word.py) and the unit tests compare with them."""
import datetime
import os
import zipfile
from xml.sax.saxutils import escape, quoteattr

SHEET = "Nhân viên"
HEADERS = ("STT", "Họ và tên", "Giới tính", "Ngày sinh", "Lương", "Năm sinh", "CCCD", "Chức vụ")
# (kind per column): n = number, d = date, t = text, s = number typed into a Text-formatted cell
KINDS = ("n", "t", "t", "d", "n", "s", "t", "t")
ROWS = (
    (1, "Nguyễn Văn An", "Nam", datetime.date(1985, 3, 7), 15000000, "1985", "001085012345", "trưởng phòng"),
    (2, "Trần Thị Bích Ngọc", "Nữ", datetime.date(1990, 12, 25), 8250000.5, "1990", "079190000123", ""),
    (3, "lê hoàng ánh", "nam", datetime.date(2001, 1, 1), 0, "2001", "048201009999", "nhân viên"),
)
XLSX, CSV, DOCX = "danh-sach.xlsx", "danh-sach.csv", "thu-moi.docx"
NESTED_BEGIN, NESTED_END = "\x13", "\x15"  # a nested field inside an instruction (as in Word's binary format)

# (instruction, field result Word last showed): one paragraph per entry; "\x13 … \x15" is a nested field
PARAGRAPHS = (
    (("Kính gửi: ", None), (' IF \x13 MERGEFIELD Giới_tính \x15 = "Nam" "Ông" "Bà" ', "Ông"), (" ", None),
     (" MERGEFIELD Họ_và_tên \\* Upper ", "«Họ_và_tên»")),
    (("Họ tên: ", None), (" MERGEFIELD Họ_và_tên \\* Caps ", "«Họ_và_tên»"), (" / ", None),
     (" MERGEFIELD Họ_và_tên \\* FirstCap ", "«Họ_và_tên»"), (" / ", None),
     (" MERGEFIELD Họ_và_tên \\* Lower ", "«Họ_và_tên»")),
    (("Ngày sinh: ", None), (' MERGEFIELD Ngày_sinh \\@ "dd/MM/yyyy" ', "«Ngày_sinh»"), ("; ", None),
     (" MERGEFIELD Ngày_sinh \\@ \"'ngày' dd 'tháng' MM 'năm' yyyy\" ", "«Ngày_sinh»"), ("; ", None),
     (' MERGEFIELD Ngày_sinh \\@ "d/M/yy" ', "«Ngày_sinh»")),
    (("Lương: ", None), (' MERGEFIELD Lương \\# "#,##0" ', "«Lương»"), (" đ; ", None),
     (' MERGEFIELD Lương \\# "#,##0.00" ', "«Lương»"), ("; ", None),
     (' MERGEFIELD Lương \\# "#.##0" ', "«Lương»"), ("; ", None),
     (" MERGEFIELD Lương \\# \"#,##0 'đồng';-#,##0 'đồng';'không đồng'\" ", "«Lương»")),
    (("Năm sinh: ", None), (" MERGEFIELD Năm_sinh ", "«Năm_sinh»"), (", CCCD: ", None),
     (" MERGEFIELD CCCD ", "«CCCD»"), (", STT: ", None), (" MERGEFIELD STT \\# 000 ", "«STT»")),
    ((' MERGEFIELD Chức_vụ \\b "Chức vụ: " \\f "." ', "«Chức_vụ»"),),
    ((' IF \x13 MERGEFIELD Lương \x15 > 10000000 "Mức lương cao" "Mức lương thường" ', "Mức lương cao"),),
    ((' IF "\x13 MERGEFIELD Họ_và_tên \x15" = "Nguyễn*" "Họ Nguyễn" "Họ khác" ', "Họ Nguyễn"),),
    ((' IF \x13 MERGEFIELD Giới_tính \x15 <> "Nam" "Chị \x13 MERGEFIELD Họ_và_tên \x15" '
      '"\x13 IF \x13 MERGEFIELD Lương \x15 >= 15000000 "Anh (quản lý)" "Anh" \x15" ', "Anh (quản lý)"),),
)
# Word's merged text per recipient. \* Caps lowers the rest of each word, \* FirstCap only raises the first
# letter. Word compares IF texts with case ("nam" is not "Nam"). A "#" of a numeric picture without a digit shows a
# space, and a group separator with no digit before it is left out (0 -> "   0"; Word 2021, HST4).
EXPECTED = (
    ("Kính gửi: Ông NGUYỄN VĂN AN",
     "Họ tên: Nguyễn Văn An / Nguyễn Văn An / nguyễn văn an",
     "Ngày sinh: 07/03/1985; ngày 07 tháng 03 năm 1985; 7/3/85",
     "Lương: 15,000,000 đ; 15,000,000.00; 15.000.000; 15,000,000 đồng",
     "Năm sinh: 1985, CCCD: 001085012345, STT: 001",
     "Chức vụ: trưởng phòng.",
     "Mức lương cao",
     "Họ Nguyễn",
     "Anh (quản lý)"),
    ("Kính gửi: Bà TRẦN THỊ BÍCH NGỌC",
     "Họ tên: Trần Thị Bích Ngọc / Trần Thị Bích Ngọc / trần thị bích ngọc",
     "Ngày sinh: 25/12/1990; ngày 25 tháng 12 năm 1990; 25/12/90",
     "Lương: 8,250,001 đ; 8,250,000.50; 8.250.001; 8,250,001 đồng",
     "Năm sinh: 1990, CCCD: 079190000123, STT: 002",
     "",
     "Mức lương thường",
     "Họ khác",
     "Chị Trần Thị Bích Ngọc"),
    ("Kính gửi: Bà LÊ HOÀNG ÁNH",
     "Họ tên: Lê Hoàng Ánh / Lê hoàng ánh / lê hoàng ánh",
     "Ngày sinh: 01/01/2001; ngày 01 tháng 01 năm 2001; 1/1/01",
     "Lương:    0 đ;    0.00;    0; không đồng",
     "Năm sinh: 2001, CCCD: 048201009999, STT: 003",
     "Chức vụ: nhân viên.",
     "Mức lương thường",
     "Họ khác",
     "Chị lê hoàng ánh"),
)

W = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
R = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
PKG = "http://schemas.openxmlformats.org/package/2006/relationships"
MAIL_MERGE_SOURCE = R + "/mailMergeSource"


def _run(inner):
    return "<w:r>%s</w:r>" % inner


def _instr(text):
    return _run('<w:instrText xml:space="preserve">%s</w:instrText>' % escape(text))


_fld = lambda kind: _run('<w:fldChar w:fldCharType="%s"/>' % kind)  # noqa: E731


def field_runs(instruction, result):
    """Complex-field runs of an instruction whose nested fields are marked with \\x13 … \\x15 (no result of their
    own, as Word writes a nested field it has not updated)."""
    runs = [_fld("begin")]
    text = ""
    for char in instruction:
        if char in (NESTED_BEGIN, NESTED_END):
            if text:
                runs.append(_instr(text))
            text = ""
            runs.append(_fld("begin" if char == NESTED_BEGIN else "end"))
        else:
            text += char
    if text:
        runs.append(_instr(text))
    runs += [_fld("separate"), _run('<w:t xml:space="preserve">%s</w:t>' % escape(result)), _fld("end")]
    return "".join(runs)


def document_xml(paragraphs=PARAGRAPHS):
    body = []
    for parts in paragraphs:
        runs = [_run('<w:t xml:space="preserve">%s</w:t>' % escape(text)) if result is None else field_runs(text, result)
                for text, result in parts]
        body.append('<w:p>%s</w:p>' % "".join(runs))
    return ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?><w:document xmlns:w="%s" xmlns:r="%s"><w:body>%s'
            '<w:sectPr><w:pgSz w:w="11906" w:h="16838"/></w:sectPr></w:body></w:document>' % (W, R, "".join(body)))


def connect_string(path):
    return ("Provider=Microsoft.ACE.OLEDB.12.0;User ID=Admin;Data Source=%s;Mode=Read;"
            'Extended Properties="HDR=YES;IMEX=1;";Jet OLEDB:System database="";Jet OLEDB:Engine Type=37;' % path)


def word_output(keep_blank_lines=False):
    """Per recipient, the paragraphs of Word's merged document (see the module text)."""
    fields_only = [all(result is not None for _text, result in parts) for parts in PARAGRAPHS]
    return tuple(tuple(text for text, only in zip(record, fields_only) if text or keep_blank_lines or not only)
                 for record in EXPECTED)


def settings_xml(source_path, sheet=SHEET, keep_blank_lines=False):
    """w:mailMerge as Word writes it for an Excel list (OLE DB) or a CSV file (text file); `keep_blank_lines`:
    Word's "do not suppress blank lines" (w:doNotSuppressBlankLines)."""
    keep = "<w:doNotSuppressBlankLines/>" if keep_blank_lines else ""
    if source_path.lower().endswith(".csv"):
        merge = ('<w:mailMerge><w:mainDocumentType w:val="formLetters"/><w:linkToQuery/><w:dataType w:val="textFile"/>'
                 '<w:query w:val=%s/><w:dataSource r:id="rId1"/>%s<w:odso><w:src r:id="rId2"/>'
                 '<w:colDelim w:val="44"/><w:fHdr/></w:odso></w:mailMerge>'
                 % (quoteattr("SELECT * FROM %s" % source_path), keep))
    else:
        merge = ('<w:mailMerge><w:mainDocumentType w:val="formLetters"/><w:linkToQuery/><w:dataType w:val="native"/>'
                 '<w:connectString w:val=%s/><w:query w:val=%s/><w:dataSource r:id="rId1"/>%s<w:odso>'
                 '<w:udl w:val=%s/><w:table w:val=%s/><w:src r:id="rId2"/><w:colDelim w:val="9"/><w:fHdr/></w:odso>'
                 '</w:mailMerge>' % (quoteattr(connect_string(source_path)),
                                     quoteattr("SELECT * FROM `%s$` " % sheet), keep,
                                     quoteattr(connect_string(source_path)), quoteattr(sheet + "$")))
    return ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?><w:settings xmlns:w="%s" xmlns:r="%s">%s'
            '<w:defaultTabStop w:val="720"/></w:settings>' % (W, R, merge))


def write_docx(path, source_path, paragraphs=PARAGRAPHS, keep_blank_lines=False):
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as package:
        package.writestr("[Content_Types].xml",
                         '<?xml version="1.0" encoding="UTF-8"?><Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
                         '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
                         '<Default Extension="xml" ContentType="application/xml"/>'
                         '<Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>'
                         '<Override PartName="/word/settings.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.settings+xml"/>'
                         '</Types>')
        package.writestr("_rels/.rels",
                         '<?xml version="1.0" encoding="UTF-8"?><Relationships xmlns="%s"><Relationship Id="rId1" '
                         'Type="%s/officeDocument" Target="word/document.xml"/></Relationships>' % (PKG, R))
        package.writestr("word/_rels/document.xml.rels",
                         '<?xml version="1.0" encoding="UTF-8"?><Relationships xmlns="%s"><Relationship Id="rId1" '
                         'Type="%s/settings" Target="settings.xml"/></Relationships>' % (PKG, R))
        target = quoteattr("file:///" + source_path.lstrip("/"))  # Word: file:///C:\\folder\\list.xlsx
        package.writestr("word/_rels/settings.xml.rels",
                         '<?xml version="1.0" encoding="UTF-8"?><Relationships xmlns="%s">'
                         '<Relationship Id="rId2" Type="%s" Target=%s TargetMode="External"/>'
                         '<Relationship Id="rId1" Type="%s" Target=%s TargetMode="External"/></Relationships>'
                         % (PKG, MAIL_MERGE_SOURCE, target, MAIL_MERGE_SOURCE, target))
        package.writestr("word/settings.xml", settings_xml(source_path, keep_blank_lines=keep_blank_lines))
        package.writestr("word/document.xml", document_xml(paragraphs))


def write_all(folder, source_path=None, keep_blank_lines=False):
    from mail_merge_word_sample_lists import write_csv, write_xlsx
    """The list (.xlsx and .csv) and the letter in `folder`; the letter names `source_path` (default: the .xlsx in
    a Windows folder that does not exist here, so the office must find the list next to the letter)."""
    os.makedirs(folder, exist_ok=True)
    write_xlsx(os.path.join(folder, XLSX))
    write_csv(os.path.join(folder, CSV))
    write_docx(os.path.join(folder, DOCX), source_path or "C:\\Users\\vanthu\\Documents\\Tron thu\\" + XLSX,
               keep_blank_lines=keep_blank_lines)
    return os.path.join(folder, DOCX)
