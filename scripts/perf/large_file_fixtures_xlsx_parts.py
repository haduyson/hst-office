# SPDX-License-Identifier: AGPL-3.0-only
"""Fixed .xlsx parts and the many-formats styles.xml of the large-file fixtures (large_file_fixtures_xlsx.py)."""

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
