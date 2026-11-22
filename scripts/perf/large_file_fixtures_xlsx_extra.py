# SPDX-License-Identifier: LicenseRef-HST-Proprietary
# Copyright (C) 2026 HASON TECH
"""Pivot tables and pictures added to a workbook of large_file_fixtures_xlsx.write_xlsx (sheet DuLieu, columns
A..O/P), for large_file_fixtures_sized.py. The parts are written as the common spreadsheet application writes them.

add_pivots(src, dst, rows): a third sheet BaoCao with two pivot tables over DuLieu!A1:K<rows+1>: Kho x Nhân viên
    (8 x 300 items) and Mã hàng (5000 items), both summing Thành tiền, with their pivot caches (no records).
add_pictures(src, dst, count): `count` distinct photos anchored over the data sheet (a picture catalogue).
"""
import random
import zipfile
from xml.sax.saxutils import escape

from large_file_fixtures_media import photo_jpeg
from large_file_fixtures_xlsx_parts import HEAD, LOOKUP_ROWS

SML = 'xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"'
R = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
RELX = '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">%s</Relationships>'
XML = '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
FIELDS = {1: ["MH%05d" % i for i in range(1, LOOKUP_ROWS + 1)], 6: ["Kho %d" % i for i in range(1, 9)],
          7: ["NV%03d" % i for i in range(1, 300)]}


def cache_def(rows):
    fields = []
    for i in range(11):
        items = FIELDS.get(i)
        if items:
            fields.append('<cacheField name="%s" numFmtId="0"><sharedItems count="%d">%s</sharedItems></cacheField>'
                          % (escape(HEAD[i]), len(items), "".join('<s v="%s"/>' % x for x in items)))
        else:
            fields.append('<cacheField name="%s" numFmtId="0"><sharedItems containsSemiMixedTypes="0" '
                          'containsString="0" containsNumber="1" minValue="0" maxValue="1E12"/></cacheField>'
                          % escape(HEAD[i]))
    return (XML + '<pivotCacheDefinition %s xmlns:r="%s" saveData="0" refreshOnLoad="0" createdVersion="6" '
            'refreshedVersion="6" minRefreshableVersion="3" recordCount="%d"><cacheSource type="worksheet">'
            '<worksheetSource ref="A1:K%d" sheet="DuLieu"/></cacheSource><cacheFields count="11">%s</cacheFields>'
            "</pivotCacheDefinition>" % (SML, R, rows, rows + 1, "".join(fields)))


def table_def(name, cache_id, row_fields, ref_rows):
    pf = []
    for i in range(11):
        items = FIELDS.get(i)
        if i in row_fields:
            pf.append('<pivotField axis="axisRow" showAll="0"><items count="%d">%s<item t="default"/></items>'
                      "</pivotField>" % (len(items) + 1, "".join('<item x="%d"/>' % k for k in range(len(items)))))
        elif i == 10:
            pf.append('<pivotField dataField="1" numFmtId="3" showAll="0"/>')
        else:
            pf.append('<pivotField showAll="0"/>')
    rf = "".join('<field x="%d"/>' % i for i in row_fields)
    col = "AF"[row_fields == [1]]
    return (XML + '<pivotTableDefinition %s name="%s" cacheId="%d" applyNumberFormats="0" applyBorderFormats="0" '
            'applyFontFormats="0" applyPatternFormats="0" applyAlignmentFormats="0" applyWidthHeightFormats="1" '
            'dataCaption="Giá trị" updatedVersion="6" minRefreshableVersion="3" useAutoFormatting="1" '
            'itemPrintTitles="1" createdVersion="6" indent="0" outline="1" outlineData="1" multipleFieldFilters="0">'
            '<location ref="%s3:%s%d" firstHeaderRow="1" firstDataRow="1" firstDataCol="1"/><pivotFields count="11">%s'
            '</pivotFields><rowFields count="%d">%s</rowFields><dataFields count="1"><dataField name="Tổng Thành tiền" '
            'fld="10" baseField="0" baseItem="0" numFmtId="3"/></dataFields><pivotTableStyleInfo name="PivotStyleLight16" '
            'showRowHeaders="1" showColHeaders="1" showRowStripes="0" showColStripes="0" showLastColumn="1"/>'
            "</pivotTableDefinition>" % (SML, name, cache_id, col, chr(ord(col) + 1), ref_rows, "".join(pf),
                                         len(row_fields), rf))


def copy_with(src, dst, extra, edit, sheet1=None):
    """Copy src to dst, passing each small text part through edit(name, text), adding the extra {name: bytes|str};
    sheet1=(old, new) replaces the tail of the streamed big xl/worksheets/sheet1.xml (and declares the r: prefix)."""
    with zipfile.ZipFile(src) as zin, zipfile.ZipFile(dst, "w", zipfile.ZIP_DEFLATED, compresslevel=6) as zout:
        for item in zin.infolist():
            if item.filename.endswith((".xml", ".rels")) and item.file_size < 1 << 20:
                zout.writestr(item.filename, edit(item.filename, zin.read(item.filename).decode("utf-8")))
                continue
            big = sheet1 and item.filename == "xl/worksheets/sheet1.xml"
            with zin.open(item) as fin, zout.open(item.filename, "w", force_zip64=True) as fout:
                pending, first = b"", True
                while chunk := fin.read(1 << 22):
                    if big and first:
                        chunk = chunk.replace(b"main\">", b"main\" xmlns:r=\"%s\">" % R.encode(), 1)
                        first = False
                    pending += chunk
                    if len(pending) > 1 << 16:  # keep the tail back for the replacement at the end
                        fout.write(pending[:-(1 << 16)])
                        pending = pending[-(1 << 16):]
                if big:
                    pending = pending.replace(sheet1[0].encode(), sheet1[1].encode(), 1)
                fout.write(pending)
        for name, data in extra.items():
            zout.writestr(name, data, compress_type=zipfile.ZIP_STORED if name.endswith(".jpeg") else None)


def ct(path, ctype):
    return '<Override PartName="/%s" ContentType="application/vnd.openxmlformats-officedocument.%s"/>' % (path, ctype)


def add_pivots(src, dst, rows):
    sheet3 = XML + "<worksheet %s><sheetData/></worksheet>" % SML
    extra = {"xl/worksheets/sheet3.xml": sheet3,
             "xl/worksheets/_rels/sheet3.xml.rels": XML + RELX % "".join(
                 '<Relationship Id="rId%d" Type="%s/pivotTable" Target="../pivotTables/pivotTable%d.xml"/>' % (i, R, i)
                 for i in (1, 2)),
             "xl/pivotTables/pivotTable1.xml": table_def("PivotKho", 1, [6, 7], 8 * 300 + 4),
             "xl/pivotTables/pivotTable2.xml": table_def("PivotMaHang", 2, [1], LOOKUP_ROWS + 4)}
    for i in (1, 2):
        extra["xl/pivotTables/_rels/pivotTable%d.xml.rels" % i] = XML + RELX % (
            '<Relationship Id="rId1" Type="%s/pivotCacheDefinition" Target="../pivotCache/pivotCacheDefinition%d.xml"/>'
            % (R, i))
        extra["xl/pivotCache/pivotCacheDefinition%d.xml" % i] = cache_def(rows)

    def edit(name, text):
        if name == "[Content_Types].xml":
            add = ct("xl/worksheets/sheet3.xml", "spreadsheetml.worksheet+xml") + "".join(
                ct("xl/pivotTables/pivotTable%d.xml" % i, "spreadsheetml.pivotTable+xml")
                + ct("xl/pivotCache/pivotCacheDefinition%d.xml" % i, "spreadsheetml.pivotCacheDefinition+xml")
                for i in (1, 2))
            return text.replace("</Types>", add + "</Types>")
        if name == "xl/workbook.xml":
            text = text.replace("</sheets>", '<sheet name="BaoCao" sheetId="3" r:id="rIdP3"/></sheets>')
            caches = "".join('<pivotCache cacheId="%d" r:id="rIdC%d"/>' % (i, i) for i in (1, 2))
            return text.replace("</workbook>", "<pivotCaches>%s</pivotCaches></workbook>" % caches)
        if name == "xl/_rels/workbook.xml.rels":
            add = '<Relationship Id="rIdP3" Type="%s/worksheet" Target="worksheets/sheet3.xml"/>' % R + "".join(
                '<Relationship Id="rIdC%d" Type="%s/pivotCacheDefinition" Target="pivotCache/pivotCacheDefinition%d.xml"/>'
                % (i, R, i) for i in (1, 2))
            return text.replace("</Relationships>", add + "</Relationships>")
        return text
    copy_with(src, dst, extra, edit)


def add_pictures(src, dst, count, seed=23):
    rnd = random.Random(seed)
    anchors, rels, extra = [], [], {}
    for i in range(count):
        extra["xl/media/image%d.jpeg" % (i + 1)] = photo_jpeg(rnd, 1600, 1067)
        rels.append('<Relationship Id="rId%d" Type="%s/image" Target="../media/image%d.jpeg"/>' % (i + 1, R, i + 1))
        top = 2 + i * 22
        anchors.append('<xdr:twoCellAnchor editAs="oneCell"><xdr:from><xdr:col>17</xdr:col><xdr:colOff>0</xdr:colOff>'
                       '<xdr:row>%d</xdr:row><xdr:rowOff>0</xdr:rowOff></xdr:from><xdr:to><xdr:col>24</xdr:col>'
                       '<xdr:colOff>0</xdr:colOff><xdr:row>%d</xdr:row><xdr:rowOff>0</xdr:rowOff></xdr:to><xdr:pic>'
                       '<xdr:nvPicPr><xdr:cNvPr id="%d" name="Ảnh %d"/><xdr:cNvPicPr><a:picLocks noChangeAspect="1"/>'
                       '</xdr:cNvPicPr></xdr:nvPicPr><xdr:blipFill><a:blip r:embed="rId%d"/><a:stretch><a:fillRect/>'
                       '</a:stretch></xdr:blipFill><xdr:spPr><a:prstGeom prst="rect"><a:avLst/></a:prstGeom></xdr:spPr>'
                       '</xdr:pic><xdr:clientData/></xdr:twoCellAnchor>' % (top, top + 20, i + 2, i + 1, i + 1))
    extra["xl/drawings/drawing1.xml"] = (XML + '<xdr:wsDr xmlns:xdr="http://schemas.openxmlformats.org/drawingml/2006/'
                                         'spreadsheetDrawing" xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/'
                                         'main" xmlns:r="%s">%s</xdr:wsDr>' % (R, "".join(anchors)))
    extra["xl/drawings/_rels/drawing1.xml.rels"] = XML + RELX % "".join(rels)
    extra["xl/worksheets/_rels/sheet1.xml.rels"] = XML + RELX % (
        '<Relationship Id="rIdD1" Type="%s/drawing" Target="../drawings/drawing1.xml"/>' % R)

    def edit(name, text):
        if name == "[Content_Types].xml":
            return text.replace("</Types>", '<Default Extension="jpeg" ContentType="image/jpeg"/>'
                                + ct("xl/drawings/drawing1.xml", "drawing+xml") + "</Types>")
        return text
    copy_with(src, dst, extra, edit, ("</worksheet>", '<drawing r:id="rIdD1"/></worksheet>'))
