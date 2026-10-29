# SPDX-License-Identifier: AGPL-3.0-only
"""Generate useful blank worksheets with executable OpenFormula expressions."""
from .odf import NS, document, fonts, node, paragraph, style, xml
from .sheet_styles import build as style_document, settings


def cell(row, kind="text", value=None, formula=None):
    attrs = {"table:style-name": "Cell_" + kind + ("_formula" if formula else "")}
    if formula:
        # No cached result: LibreOffice does not recalculate formulas that carry a stored
        # value when loading an ODF file, so an input change would otherwise stay at 0.
        attrs["table:formula"] = "of:=" + formula
    elif value is not None:
        attrs.update({"office:value-type": "string" if isinstance(value, str) else "float"})
        if not isinstance(value, str):
            attrs["office:value"] = str(value)
    result = node(row, "table:table-cell", attrs)
    if value is not None:
        paragraph(result, str(value))
    return result


def build(source, formats):
    root = document("content")
    root.set("xmlns:of", NS["of"])
    fonts(root)
    auto = node(root, "office:automatic-styles")
    style(auto, "Sheet", "table", {"table": {"table:display": "true"}},
          {"style:master-page-name": "Default"})
    for name, height in [("Title", 10), ("Period", 8), ("Note", 23), ("Header", 14), ("Data", 10)]:
        style(auto, "Row_" + name, "table-row", {"table-row": {"style:min-row-height": f"{height}mm"}})
    count = len(source["columns"])
    for i, column in enumerate(source["columns"]):
        width = 42 if column["type"] == "text" else 28
        style(auto, f"Col{i}", "table-column", {"table-column": {"style:column-width": f"{width}mm"}})
    body = node(node(root, "office:body"), "office:spreadsheet")
    node(body, "table:calculation-settings", {"table:automatic-find-labels": "false"})
    last = source["rows"] + 5
    sheet_name = source["sheetName"]
    sheet = node(body, "table:table", {"table:name": sheet_name, "table:style-name": "Sheet",
                 "table:print-ranges": f"'{sheet_name}'.$A$1:${chr(64 + count)}${last}"})
    for i in range(count):
        node(sheet, "table:table-column", {"table:style-name": f"Col{i}"})
    headers = node(sheet, "table:table-header-rows")
    for kind, value, row_style in [("Title", source["title"], "Title"), ("Note", source["period"], "Period"),
                                   ("Note", source["guidance"], "Note")]:
        row = node(headers, "table:table-row", {"table:style-name": "Row_" + row_style})
        merged = cell(row, kind, value)
        merged.set("{" + NS["table"] + "}number-columns-spanned", str(count))
        for _ in range(count - 1):
            node(row, "table:covered-table-cell")
    row = node(headers, "table:table-row", {"table:style-name": "Row_Header"})
    for column in source["columns"]:
        cell(row, "Header", column["title"])
    for r in range(5, last):
        row = node(sheet, "table:table-row", {"table:style-name": "Row_Data"})
        for column in source["columns"]:
            formula = column.get("formula", "").replace("{row}", str(r)) or None
            value = column.get("placeholder") if column["type"] == "text" else (None if column["type"] == "date" else 0)
            cell(row, column["type"], None if formula else value, formula)
    row = node(sheet, "table:table-row", {"table:style-name": "Row_Data"})
    for i, column in enumerate(source["columns"]):
        formula = source["totals"].get(chr(65 + i))
        cell(row, "Header" if i == 0 else column["type"], "TỔNG" if i == 0 else None, formula)
    return {"content.xml": xml(root), "styles.xml": style_document(formats),
            "settings.xml": settings(sheet_name)}
