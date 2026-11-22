# SPDX-License-Identifier: LicenseRef-HST-Proprietary
# Copyright (C) 2026 HASON TECH
"""Realistic long Word documents: a Vietnamese administrative report of N pages, written as a stream.

    python large_file_fixtures_longdoc.py <out-dir> [--pages 500,1000,3000] [--units-per-page 1.0]

The document looks like a provincial annual report (bao cao tong ket) typed in Word: A4 with the decree 30/2020
margins (top/bottom 2 cm, left 3 cm, right 1.5 cm), Times New Roman 13 pt, line spacing 1.15, justified paragraphs
with a 1 cm first-line indent; Heading 1/2/3 sections, a table of contents (field with cached entries) after the
cover, a running header and a centred page number in the footer, bullet lists, a numbered table with a caption on
about one page in five, and a photo (with caption) about every 40 pages. One "unit" is roughly one page of text; the
units per page factor is calibrated against a measured page count (--units-per-page). All text is generated.
"""
import argparse
import os
import random
import sys
import zipfile
from xml.sax.saxutils import escape

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from large_file_fixture_words import sentence  # noqa: E402
from large_file_fixtures_media import photo_jpeg  # noqa: E402

W = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
NS = ('xmlns:w="%s" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships" '
      'xmlns:wp="http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing" '
      'xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main" '
      'xmlns:pic="http://schemas.openxmlformats.org/drawingml/2006/picture"' % W)
REL = "http://schemas.openxmlformats.org/officeDocument/2006/relationships/"
HEAD = '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
TOPICS = ("kinh tế", "văn hóa - xã hội", "quốc phòng - an ninh", "cải cách hành chính", "chuyển đổi số",
          "giáo dục và đào tạo", "y tế", "nông nghiệp và phát triển nông thôn", "tài nguyên và môi trường",
          "xây dựng chính quyền", "tài chính - ngân sách", "đầu tư công")


def run(text, rpr=""):
    return '<w:r>%s<w:t xml:space="preserve">%s</w:t></w:r>' % (rpr and "<w:rPr>%s</w:rPr>" % rpr, escape(text))


def para(body, style="", ppr=""):
    props = ('<w:pStyle w:val="%s"/>' % style if style else "") + ppr
    return "<w:p>%s%s</w:p>" % (props and "<w:pPr>%s</w:pPr>" % props, body)


def field(instr, cached, rpr=""):
    r = rpr and "<w:rPr>%s</w:rPr>" % rpr
    return ('<w:r>%s<w:fldChar w:fldCharType="begin"/></w:r><w:r>%s<w:instrText xml:space="preserve"> %s </w:instrText>'
            '</w:r><w:r>%s<w:fldChar w:fldCharType="separate"/></w:r>%s<w:r>%s<w:fldChar w:fldCharType="end"/></w:r>'
            % (r, r, escape(instr), r, run(cached, rpr), r))


def table(rnd, rows, cols, n):
    widths = [600] + [(9360 - 600) // (cols - 1)] * (cols - 1)
    grid = "".join('<w:gridCol w:w="%d"/>' % w for w in widths)
    head = ["TT", "Chỉ tiêu", "Đơn vị", "Kế hoạch", "Thực hiện", "Tỷ lệ (%)", "Ghi chú"][:cols]
    out = []
    for r in range(rows):
        cells = []
        for c in range(cols):
            if r == 0:
                text, rpr, jc = head[c], "<w:b/>", "center"
            elif c == 0:
                text, rpr, jc = str(r), "", "center"
            elif c == 1:
                text, rpr, jc = sentence(rnd, rnd.randrange(3, 9)), "", "left"
            elif c == 2:
                text, rpr, jc = rnd.choice(("người", "tỷ đồng", "hộ", "%", "km", "ha", "hồ sơ")), "", "center"
            else:
                text, rpr, jc = "{:,}".format(rnd.randrange(10, 10 ** 6)).replace(",", "."), "", "right"
            cells.append('<w:tc><w:tcPr><w:tcW w:w="%d" w:type="dxa"/>%s</w:tcPr>%s</w:tc>'
                         % (widths[c], '<w:shd w:val="clear" w:color="auto" w:fill="D9E2F3"/>' if r == 0 else "",
                            para(run(text, rpr), "TableText", '<w:jc w:val="%s"/>' % jc)))
        trpr = "<w:trPr><w:tblHeader/></w:trPr>" if r == 0 else ""
        out.append("<w:tr>%s%s</w:tr>" % (trpr, "".join(cells)))
    caption = para(run("Bảng %d. Kết quả thực hiện các chỉ tiêu %s" % (n, rnd.choice(TOPICS)), "<w:b/>"), "Caption")
    return (caption + '<w:tbl><w:tblPr><w:tblStyle w:val="TableGrid"/><w:tblW w:w="9360" w:type="dxa"/>'
            '<w:tblLook w:val="04A0" w:firstRow="1" w:lastRow="0" w:firstColumn="1" w:lastColumn="0" w:noHBand="0" '
            'w:noVBand="1"/></w:tblPr><w:tblGrid>%s</w:tblGrid>%s</w:tbl>' % (grid, "".join(out)) + para(""))


def picture(n, rid, cx, cy):
    return ('<w:r><w:drawing><wp:inline distT="0" distB="0" distL="0" distR="0"><wp:extent cx="%d" cy="%d"/>'
            '<wp:docPr id="%d" name="Hình %d"/><a:graphic><a:graphicData uri="http://schemas.openxmlformats.org/'
            'drawingml/2006/picture"><pic:pic><pic:nvPicPr><pic:cNvPr id="%d" name="image%d.jpeg"/><pic:cNvPicPr/>'
            '</pic:nvPicPr><pic:blipFill><a:blip r:embed="%s"/><a:stretch><a:fillRect/></a:stretch></pic:blipFill>'
            '<pic:spPr><a:xfrm><a:off x="0" y="0"/><a:ext cx="%d" cy="%d"/></a:xfrm><a:prstGeom prst="rect">'
            '<a:avLst/></a:prstGeom></pic:spPr></pic:pic></a:graphicData></a:graphic></wp:inline></w:drawing></w:r>'
            % (cx, cy, n, n, n, n, rid, cx, cy))


def outline(units):
    """Heading plan: (unit, level, number, title) - a chapter every 30 units, sections every 6, subsections every 3."""
    rnd = random.Random(5)
    plan, ch, sec, sub = [], 0, 0, 0
    for u in range(units):
        if u % 30 == 0:
            ch, sec, sub = ch + 1, 0, 0
            plan.append((u, 1, "Phần %d" % ch, "Tình hình thực hiện nhiệm vụ " + rnd.choice(TOPICS)))
        elif u % 6 == 0:
            sec, sub = sec + 1, 0
            plan.append((u, 2, "%d.%d" % (ch, sec), sentence(rnd, 6).rstrip(".")))
        elif u % 3 == 0:
            sub += 1
            plan.append((u, 3, "%d.%d.%d" % (ch, sec, sub), sentence(rnd, 7).rstrip(".")))
    return plan


def body(units, units_per_page, media, rels):
    rnd = random.Random(13)
    plan = outline(units)
    heads = {u: (lvl, num, title) for u, lvl, num, title in plan}
    yield para(run("ỦY BAN NHÂN DÂN TỈNH QUẢNG NAM", "<w:b/>"), "", '<w:jc w:val="center"/>')
    yield para(run("CỘNG HÒA XÃ HỘI CHỦ NGHĨA VIỆT NAM", "<w:b/>"), "", '<w:jc w:val="center"/>')
    yield para(run("Độc lập - Tự do - Hạnh phúc", "<w:b/>"), "", '<w:jc w:val="center"/>')
    yield para(run("Số: 125/BC-UBND", ""), "", '<w:jc w:val="left"/>')
    yield para(run("BÁO CÁO", "<w:b/><w:sz w:val=\"32\"/>"), "", '<w:spacing w:before="1200"/><w:jc w:val="center"/>')
    yield para(run("Tổng kết tình hình thực hiện nhiệm vụ phát triển kinh tế - xã hội năm 2026 và phương hướng, "
                   "nhiệm vụ năm 2027", "<w:b/>"), "", '<w:jc w:val="center"/>')
    yield '<w:p><w:r><w:br w:type="page"/></w:r></w:p>'
    # Table of contents: Heading 1 and 2 entries with cached page numbers, as Word writes them.
    entries = [(lvl, num, title, 3 + int(u / units_per_page)) for u, lvl, num, title in plan if lvl <= 2]
    yield para(run("MỤC LỤC", "<w:b/>"), "TOCHeading")
    for i, (lvl, num, title, page) in enumerate(entries):
        text = run("%s. %s" % (num, title)) + '<w:r><w:tab/></w:r>' + run(str(page))
        if i == 0:  # the TOC field starts in the first entry and ends in its own paragraph after the last one
            text = ('<w:r><w:fldChar w:fldCharType="begin"/></w:r><w:r><w:instrText xml:space="preserve"> TOC \\o '
                    '"1-3" \\h \\z \\u </w:instrText></w:r><w:r><w:fldChar w:fldCharType="separate"/></w:r>' + text)
        yield para(text, "TOC%d" % lvl)
    yield para('<w:r><w:fldChar w:fldCharType="end"/></w:r>')
    yield '<w:p><w:r><w:br w:type="page"/></w:r></w:p>'
    ntab = npic = 0
    for u in range(units):
        if u in heads:
            lvl, num, title = heads[u]
            yield para(run("%s. %s" % (num, title) if lvl > 1 else "%s. %s" % (num, title.upper())), "Heading%d" % lvl)
        if u % 5 == 2:
            ntab += 1
            yield para(run(sentence(rnd, rnd.randrange(30, 50))), "BodyText")
            yield table(rnd, rnd.randrange(7, 13), rnd.choice((5, 6, 7)), ntab)
            yield para(run(sentence(rnd, rnd.randrange(40, 60))), "BodyText")
            continue
        if u % 40 == 18:
            npic += 1
            rid = "rIdImg%d" % npic
            media.append(("image%d.jpeg" % npic, photo_jpeg(rnd, 1200, 800, quality=80)))
            rels.append('<Relationship Id="%s" Type="%simage" Target="media/%s"/>' % (rid, REL, media[-1][0]))
            yield para(picture(npic, rid, 5040000, 3360000), "", '<w:jc w:val="center"/>')
            yield para(run("Hình %d. %s" % (npic, sentence(rnd, 8)), "<w:i/>"), "Caption", '<w:jc w:val="center"/>')
            yield para(run(sentence(rnd, rnd.randrange(50, 70))), "BodyText")
            yield para(run(sentence(rnd, rnd.randrange(50, 70))), "BodyText")
            continue
        n = 6
        if u % 4 == 1:
            for _ in range(3):
                yield para(run(sentence(rnd, rnd.randrange(12, 25))), "ListBullet")
            n = 4
        for _ in range(n):
            yield para(run(sentence(rnd, rnd.randrange(45, 75))), "BodyText")
    yield para(run("Nơi nhận:", "<w:b/><w:i/>"), "")
    yield para(run("- Như trên;"), "")
    yield para(run("TM. ỦY BAN NHÂN DÂN", "<w:b/>"), "", '<w:jc w:val="right"/>')
    yield ('<w:sectPr><w:headerReference w:type="default" r:id="rIdH"/><w:footerReference w:type="default" r:id="rIdF"/>'
           '<w:pgSz w:w="11906" w:h="16838"/><w:pgMar w:top="1134" w:right="850" w:bottom="1134" w:left="1701" '
           'w:header="567" w:footer="567" w:gutter="0"/><w:titlePg/></w:sectPr>')


def styles_xml():
    def pstyle(sid, name, ppr="", rpr="", based="Normal", nxt=""):
        return ('<w:style w:type="paragraph" w:styleId="%s"><w:name w:val="%s"/><w:basedOn w:val="%s"/>%s'
                '<w:qFormat/><w:pPr>%s</w:pPr><w:rPr>%s</w:rPr></w:style>'
                % (sid, name, based, nxt and '<w:next w:val="%s"/>' % nxt, ppr, rpr))
    tab = '<w:tabs><w:tab w:val="right" w:leader="dot" w:pos="9345"/></w:tabs>'
    return (HEAD + '<w:styles %s><w:docDefaults><w:rPrDefault><w:rPr><w:rFonts w:ascii="Times New Roman" '
            'w:hAnsi="Times New Roman" w:eastAsia="Times New Roman" w:cs="Times New Roman"/><w:sz w:val="26"/>'
            '<w:szCs w:val="26"/><w:lang w:val="vi-VN" w:eastAsia="en-US" w:bidi="ar-SA"/></w:rPr></w:rPrDefault>'
            '<w:pPrDefault><w:pPr><w:spacing w:after="120" w:line="276" w:lineRule="auto"/></w:pPr></w:pPrDefault>'
            '</w:docDefaults><w:style w:type="paragraph" w:default="1" w:styleId="Normal"><w:name w:val="Normal"/>'
            '<w:qFormat/></w:style>' % NS
            + pstyle("Heading1", "heading 1", '<w:keepNext/><w:pageBreakBefore/><w:spacing w:before="240" w:after="240"/>'
                     '<w:jc w:val="center"/><w:outlineLvl w:val="0"/>', '<w:b/><w:sz w:val="28"/>', nxt="BodyText")
            + pstyle("Heading2", "heading 2", '<w:keepNext/><w:spacing w:before="200" w:after="120"/><w:outlineLvl w:val="1"/>',
                     '<w:b/>', nxt="BodyText")
            + pstyle("Heading3", "heading 3", '<w:keepNext/><w:spacing w:before="120" w:after="120"/><w:outlineLvl w:val="2"/>',
                     '<w:b/><w:i/>', nxt="BodyText")
            + pstyle("BodyText", "Body Text", '<w:ind w:firstLine="567"/><w:jc w:val="both"/>')
            + pstyle("ListBullet", "List Bullet", '<w:numPr><w:ilvl w:val="0"/><w:numId w:val="1"/></w:numPr>'
                     '<w:ind w:left="851" w:hanging="284"/><w:jc w:val="both"/>')
            + pstyle("Caption", "caption", '<w:spacing w:before="120" w:after="120"/><w:jc w:val="center"/>', '<w:sz w:val="24"/>')
            + pstyle("TableText", "Table Text", '<w:spacing w:before="40" w:after="40" w:line="240" w:lineRule="auto"/>',
                     '<w:sz w:val="24"/>')
            + pstyle("TOCHeading", "TOC Heading", '<w:jc w:val="center"/>', '<w:b/><w:sz w:val="28"/>')
            + pstyle("TOC1", "toc 1", tab + '<w:spacing w:after="60"/>', '<w:b/>')
            + pstyle("TOC2", "toc 2", tab + '<w:spacing w:after="60"/><w:ind w:left="284"/>')
            + pstyle("Header", "header", '<w:tabs><w:tab w:val="center" w:pos="4680"/></w:tabs><w:spacing w:after="0"/>'
                     '<w:jc w:val="center"/>', '<w:i/><w:sz w:val="22"/>')
            + pstyle("Footer", "footer", '<w:spacing w:after="0"/><w:jc w:val="center"/>', '<w:sz w:val="24"/>')
            + '<w:style w:type="table" w:default="1" w:styleId="TableNormal"><w:name w:val="Normal Table"/><w:tblPr>'
            '<w:tblInd w:w="0" w:type="dxa"/><w:tblCellMar><w:top w:w="0" w:type="dxa"/><w:left w:w="108" w:type="dxa"/>'
            '<w:bottom w:w="0" w:type="dxa"/><w:right w:w="108" w:type="dxa"/></w:tblCellMar></w:tblPr></w:style>'
            '<w:style w:type="table" w:styleId="TableGrid"><w:name w:val="Table Grid"/><w:basedOn w:val="TableNormal"/>'
            '<w:pPr><w:spacing w:after="0" w:line="240" w:lineRule="auto"/></w:pPr><w:tblPr><w:tblBorders>'
            '<w:top w:val="single" w:sz="4" w:space="0" w:color="auto"/><w:left w:val="single" w:sz="4" w:space="0" '
            'w:color="auto"/><w:bottom w:val="single" w:sz="4" w:space="0" w:color="auto"/><w:right w:val="single" '
            'w:sz="4" w:space="0" w:color="auto"/><w:insideH w:val="single" w:sz="4" w:space="0" w:color="auto"/>'
            '<w:insideV w:val="single" w:sz="4" w:space="0" w:color="auto"/></w:tblBorders></w:tblPr></w:style>'
            '</w:styles>')


NUMBERING = (HEAD + '<w:numbering xmlns:w="%s"><w:abstractNum w:abstractNumId="0"><w:multiLevelType '
             'w:val="hybridMultilevel"/><w:lvl w:ilvl="0"><w:start w:val="1"/><w:numFmt w:val="bullet"/><w:lvlText '
             'w:val="-"/><w:lvlJc w:val="left"/><w:pPr><w:ind w:left="851" w:hanging="284"/></w:pPr><w:rPr><w:rFonts '
             'w:ascii="Times New Roman" w:hAnsi="Times New Roman"/></w:rPr></w:lvl></w:abstractNum><w:num w:numId="1">'
             '<w:abstractNumId w:val="0"/></w:num></w:numbering>' % W)


def write_longdoc(path, units, units_per_page=1.0):
    media, rels = [], []
    relx = '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">%s</Relationships>'
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED, compresslevel=6) as z:
        with z.open("word/document.xml", "w", force_zip64=True) as fh:
            fh.write((HEAD + "<w:document %s><w:body>" % NS).encode("utf-8"))
            for chunk in body(units, units_per_page, media, rels):
                fh.write(chunk.encode("utf-8"))
            fh.write(b"</w:body></w:document>")
        for name, data in media:
            z.writestr("word/media/" + name, data, compress_type=zipfile.ZIP_STORED)
        z.writestr("word/header1.xml", HEAD + '<w:hdr %s>%s</w:hdr>' % (NS, para(run(
            "Báo cáo tổng kết tình hình kinh tế - xã hội năm 2026"), "Header")))
        z.writestr("word/footer1.xml", HEAD + '<w:ftr %s>%s</w:ftr>' % (NS, para(field("PAGE", "1"), "Footer")))
        z.writestr("word/styles.xml", styles_xml())
        z.writestr("word/numbering.xml", NUMBERING)
        z.writestr("word/settings.xml", HEAD + '<w:settings %s><w:updateFields w:val="false"/><w:defaultTabStop '
                   'w:val="720"/><w:compat><w:compatSetting w:name="compatibilityMode" w:uri="http://schemas.microsoft.'
                   'com/office/word" w:val="15"/></w:compat></w:settings>' % NS)
        rels += ['<Relationship Id="rIdS" Type="%sstyles" Target="styles.xml"/>' % REL,
                 '<Relationship Id="rIdT" Type="%ssettings" Target="settings.xml"/>' % REL,
                 '<Relationship Id="rIdN" Type="%snumbering" Target="numbering.xml"/>' % REL,
                 '<Relationship Id="rIdH" Type="%sheader" Target="header1.xml"/>' % REL,
                 '<Relationship Id="rIdF" Type="%sfooter" Target="footer1.xml"/>' % REL]
        z.writestr("word/_rels/document.xml.rels", HEAD + relx % "".join(rels))
        wml = "application/vnd.openxmlformats-officedocument.wordprocessingml."
        ct = ['<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>',
              '<Default Extension="xml" ContentType="application/xml"/>',
              '<Default Extension="jpeg" ContentType="image/jpeg"/>']
        ct += ['<Override PartName="/word/%s.xml" ContentType="%s%s+xml"/>' % (n, wml, t) for n, t in (
            ("document", "document.main"), ("styles", "styles"), ("settings", "settings"), ("numbering", "numbering"),
            ("header1", "header"), ("footer1", "footer"))]
        ct += ['<Override PartName="/docProps/app.xml" ContentType="application/vnd.openxmlformats-officedocument.'
               'extended-properties+xml"/>']
        z.writestr("[Content_Types].xml", HEAD + '<Types xmlns="http://schemas.openxmlformats.org/package/2006/'
                   'content-types">%s</Types>' % "".join(ct))
        z.writestr("_rels/.rels", HEAD + relx % ('<Relationship Id="rId1" Type="%sofficeDocument" Target="word/'
                                                 'document.xml"/><Relationship Id="rId2" Type="%sextended-properties" '
                                                 'Target="docProps/app.xml"/>' % (REL, REL)))
        z.writestr("docProps/app.xml", HEAD + '<Properties xmlns="http://schemas.openxmlformats.org/officeDocument/'
                   '2006/extended-properties"><Application>Microsoft Office Word</Application><AppVersion>16.0000'
                   '</AppVersion></Properties>')


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("out")
    ap.add_argument("--pages", default="500,1000,3000")
    ap.add_argument("--units-per-page", type=float, default=1.0,
                    help="text units per laid-out page (measure a file and divide its units by its page count)")
    a = ap.parse_args()
    os.makedirs(a.out, exist_ok=True)
    for pages in (int(x) for x in a.pages.split(",")):
        path = os.path.join(a.out, "docx-report-%dp.docx" % pages)
        units = max(1, round(pages * a.units_per_page))
        write_longdoc(path + ".tmp", units, a.units_per_page)
        os.replace(path + ".tmp", path)
        print("%-28s %7.1f MB  units=%d" % (os.path.basename(path), os.path.getsize(path) / 1e6, units), flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
