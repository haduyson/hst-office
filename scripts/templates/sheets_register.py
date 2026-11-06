# SPDX-License-Identifier: AGPL-3.0-only
"""Registers of Decree 30/2020, Annex IV: a cover sheet and the register itself, with the annex's numbered columns."""
from .odf import NS, document, fonts, node, paragraph, style, xml
from .sheet_styles import settings

ROWS = 30  # empty lines ready to print; the table grows like any sheet


def _cell(row, name, text=None, span=0):
    attrs = {"table:style-name": name}
    if text is not None:
        attrs["office:value-type"] = "string"
    if span:
        attrs["table:number-columns-spanned"] = str(span)
    cell = node(row, "table:table-cell", attrs)
    if text is not None:
        paragraph(cell, text)
    for _ in range(span - 1):
        node(row, "table:covered-table-cell")


def _cover(body, source):
    """Annex IV, 'Bìa và trang đầu'."""
    sheet = node(body, "table:table", {"table:name": "Bìa", "table:style-name": "Sheet"})
    node(sheet, "table:table-column", {"table:style-name": "CoverCol"})
    lines = [("CoverParent", "[TÊN CƠ QUAN CHỦ QUẢN TRỰC TIẾP]"), ("CoverAgency", "[TÊN CƠ QUAN/ĐƠN VỊ]"), ("CoverAgency", ""),
             ("CoverTitle", source["coverTitle"]), ("CoverAgency", ""), ("CoverItalic", "Năm: [năm]"), ("CoverAgency", ""),
             ("CoverItalic", "Từ ngày [ngày] đến ngày [ngày]")]
    if source.get("numberRange"):
        lines.append(("CoverItalic", "Từ số [số] đến số [số]"))
    lines += [("CoverAgency", ""), ("CoverAgency", ""), ("CoverAgency", "Quyển số: [số]")]
    for name, text in lines:
        row = node(sheet, "table:table-row", {"table:style-name": "CoverRow"})
        _cell(row, name, text or None)


def _register(body, source):
    columns = source["columns"]
    # No fixed print range: a register grows downward entry by entry and every entry must print (the used area does)
    sheet = node(body, "table:table", {"table:name": "Sổ", "table:style-name": "Sheet"})
    for index in range(len(columns)):
        node(sheet, "table:table-column", {"table:style-name": f"Col{index}"})
    headers = node(sheet, "table:table-header-rows")
    row = node(headers, "table:table-row", {"table:style-name": "HeadRow"})
    for column in columns:
        _cell(row, "RegHead", column["title"])
    row = node(headers, "table:table-row", {"table:style-name": "NumRow"})
    for index in range(len(columns)):
        _cell(row, "RegNum", "(%d)" % (index + 1))
    for _ in range(ROWS):
        row = node(sheet, "table:table-row", {"table:style-name": "DataRow"})
        for _column in columns:
            _cell(row, "RegBody")


def _styles():
    root = document("styles")
    fonts(root, writer=True)
    office = node(root, "office:styles")
    base = {"style:font-name": "Times New Roman", "fo:language": "vi", "fo:country": "VN", "fo:color": "#000000"}
    border = {"fo:border": "0.75pt solid #000000", "fo:wrap-option": "wrap", "style:vertical-align": "middle", "fo:padding": "1mm"}
    plain = {"fo:wrap-option": "wrap", "style:vertical-align": "middle"}
    centre = {"fo:text-align": "center"}
    specs = {"RegHead": (border, centre, {"fo:font-size": "11pt", "fo:font-weight": "bold"}), "RegNum": (border, centre, {"fo:font-size": "11pt"}),
             "RegBody": (border, {}, {"fo:font-size": "11pt"}), "CoverParent": (plain, centre, {"fo:font-size": "12pt"}),
             "CoverAgency": (plain, centre, {"fo:font-size": "12pt", "fo:font-weight": "bold"}), "CoverTitle": (plain, centre, {"fo:font-size": "16pt", "fo:font-weight": "bold"}),
             "CoverItalic": (plain, centre, {"fo:font-size": "12pt", "fo:font-style": "italic"})}
    for name, (cell, para, text) in specs.items():
        style(office, name, "table-cell", {"table-cell": cell, "paragraph": para, "text": {**base, **text}})
    auto = node(root, "office:automatic-styles")
    layout = node(auto, "style:page-layout", {"style:name": "SheetPage"})
    node(layout, "style:page-layout-properties", {"fo:page-width": "297mm", "fo:page-height": "210mm", "style:print-orientation": "landscape", "fo:margin": "15mm",
         "style:scale-to-X": "1", "style:scale-to-Y": "0", "style:table-centering": "horizontal", "style:print": "objects charts drawings"})
    for part, side in [("header", "bottom"), ("footer", "top")]:
        box = node(layout, f"style:{part}-style")
        node(box, "style:header-footer-properties", {"fo:min-height": "5mm", f"fo:margin-{side}": "2mm"})
    masters = node(root, "office:master-styles")
    node(masters, "style:master-page", {"style:name": "Default", "style:page-layout-name": "SheetPage"})
    return xml(root)


def build(source):
    root = document("content")
    root.set("xmlns:of", NS["of"])
    fonts(root, writer=True)
    auto = node(root, "office:automatic-styles")
    style(auto, "Sheet", "table", {"table": {"table:display": "true"}}, {"style:master-page-name": "Default"})
    style(auto, "CoverCol", "table-column", {"table-column": {"style:column-width": "260mm"}})
    for name, height in [("CoverRow", 11), ("HeadRow", 24), ("NumRow", 7), ("DataRow", 9)]:
        style(auto, name, "table-row", {"table-row": {"style:min-row-height": f"{height}mm"}})
    for index, column in enumerate(source["columns"]):
        style(auto, f"Col{index}", "table-column", {"table-column": {"style:column-width": f'{column["widthMm"]}mm'}})
    body = node(node(root, "office:body"), "office:spreadsheet")
    node(body, "table:calculation-settings", {"table:automatic-find-labels": "false"})
    _cover(body, source)
    _register(body, source)
    return {"content.xml": xml(root), "styles.xml": _styles(), "settings.xml": settings("Sổ", 2)}
