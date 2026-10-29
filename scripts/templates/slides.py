# SPDX-License-Identifier: AGPL-3.0-only
"""Five Vietnamese slide themes with real masters, tables, notes and charts."""
from .odf import NS, document, fonts, node, paragraph, xml
from .slide_styles import build as style_document


def frame(parent, name, x, y, width, height, kind=None):
    attrs = {"draw:name": name, "draw:style-name": "TextBox", "draw:layer": "layout",
             "svg:x": f"{x}mm", "svg:y": f"{y}mm", "svg:width": f"{width}mm", "svg:height": f"{height}mm"}
    if kind:
        attrs["presentation:class"] = kind
    return node(parent, "draw:frame", attrs)


def textbox(parent, name, lines, x, y, width, height, text_style, kind=None):
    box = node(frame(parent, name, x, y, width, height, kind), "draw:text-box")
    for line in lines:
        paragraph(box, line, text_style)


def chart_document():
    root = document("content")
    body = node(node(root, "office:body"), "office:chart")
    chart = node(body, "chart:chart", {"chart:class": "chart:bar", "svg:width": "260mm",
                 "svg:height": "85mm"})
    plot = node(chart, "chart:plot-area", {"table:cell-range-address": "local-table.A1:B4",
                "chart:data-source-has-labels": "both", "svg:x": "20mm", "svg:y": "10mm",
                "svg:width": "220mm", "svg:height": "60mm"})
    axis = node(plot, "chart:axis", {"chart:dimension": "x", "chart:name": "primary-x"})
    node(axis, "chart:categories", {"table:cell-range-address": "local-table.A2:A4"})
    node(plot, "chart:axis", {"chart:dimension": "y", "chart:name": "primary-y"})
    series = node(plot, "chart:series", {"chart:class": "chart:bar",
                  "chart:values-cell-range-address": "local-table.B2:B4",
                  "chart:label-cell-address": "local-table.B1"})
    node(series, "chart:data-point", {"chart:repeated": "3"})
    table = node(chart, "table:table", {"table:name": "local-table"})
    for values in [("[Chỉ tiêu]", "[Giá trị]"), ("[Kỳ 1]", 0), ("[Kỳ 2]", 0), ("[Kỳ 3]", 0)]:
        row = node(table, "table:table-row")
        for value in values:
            attrs = {"office:value-type": "string" if isinstance(value, str) else "float"}
            if not isinstance(value, str):
                attrs["office:value"] = str(value)
            paragraph(node(row, "table:table-cell", attrs), str(value))
    return xml(root)


def build(source):
    root = document("content")
    fonts(root)
    node(root, "office:automatic-styles")
    body = node(node(root, "office:body"), "office:presentation")
    for index, slide in enumerate(source["slides"], 1):
        kind = slide["layout"]
        page = node(body, "draw:page", {"draw:name": f"Trang {index}",
                    "draw:master-page-name": "Section" if kind == "section" else "HST",
                    "presentation:presentation-page-layout-name": kind})
        textbox(page, "Tiêu đề", [slide["title"]], 20, 18, 280, 32, "Title", "title")
        if kind in {"title", "content", "section"}:
            textbox(page, "Nội dung", slide["lines"], 20, 60, 280, 95, "Body",
                    "outline" if kind == "content" else "subtitle")
        elif kind == "table":
            box = frame(page, "Bảng nội dung", 20, 60, 280, 90, "table")
            table = node(box, "table:table", {"table:name": "Kế hoạch"})
            for _ in range(3):
                node(table, "table:table-column")
            for values in [["Nội dung", "Phụ trách", "Thời hạn"]] + [["[Nội dung]", "[Đơn vị]", "[Thời hạn]"]] * 3:
                row = node(table, "table:table-row")
                for value in values:
                    cell = node(row, "table:table-cell", {"office:value-type": "string",
                                "table:style-name": "TableCell"})
                    paragraph(cell, value, "Small")
        else:
            box = frame(page, "Biểu đồ có thể sửa", 20, 55, 280, 85, "chart")
            node(box, "draw:object", {"xlink:href": "./Chart1", "xlink:type": "simple",
                 "xlink:show": "embed", "xlink:actuate": "onLoad"})
            textbox(page, "Hướng dẫn dữ liệu", ["[Nhập số liệu đã kiểm chứng vào bảng dữ liệu biểu đồ; giá trị ban đầu là 0.]"],
                    20, 145, 280, 25, "Small")
        notes = node(page, "presentation:notes")
        textbox(notes, "Ghi chú", [slide["notes"]], 20, 140, 170, 120, "Notes", "notes")
    return {"content.xml": xml(root), "styles.xml": style_document(source["theme"]),
            "Chart1/content.xml": chart_document()}
