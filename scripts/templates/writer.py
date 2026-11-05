# SPDX-License-Identifier: AGPL-3.0-only
"""ODF renderer of the shared document layout: the .ott templates are hst_office.nd30_layout, written directly as XML."""
from .odf import document, fonts, node, paragraph, style, xml
from .writer_layout import build_layout
from .writer_styles import build as style_document, Styles


def _rule(parent, para, cell_mm, styles):
    side = max(0.0, (cell_mm - para["rule_mm"]) / 2)
    paragraph(parent, name=styles.rule(side))


def _paragraph(parent, para, cell_mm, styles, auto):
    p = paragraph(parent, name=styles.paragraph(para))
    runs = para["runs"]
    if len(runs) == 1:
        p.text = runs[0]["text"]
    else:
        for item in runs:
            span = node(p, "text:span", {"text:style-name": styles.span(item, auto)}, item["text"])
            span.tail = None
    if para.get("rule_mm"):
        _rule(parent, para, cell_mm, styles)


def _grid(parent, block, text_mm, styles, auto, index):
    name = "%s%d" % (block.get("name", "Grid"), index)
    width = block.get("widthMm", text_mm)
    widths = [width * pct / 100 for pct in block["widthsPct"]]
    table_props = {"style:width": f"{width:g}mm", "table:align": "margins" if "widthMm" not in block else "left",
                   "style:may-break-between-rows": "false" if block.get("name") == "Signature" else "true"}
    if block.get("spacing_before_pt"):
        table_props["fo:margin-top"] = f'{block["spacing_before_pt"]:g}pt'
    style(auto, name, "table", {"table": table_props})
    table = node(parent, "table:table", {"table:name": name, "table:style-name": name})
    for i, column_width in enumerate(widths):
        column = "%s.%d" % (name, i)
        style(auto, column, "table-column", {"table-column": {"style:column-width": f"{column_width:g}mm"}})
        node(table, "table:table-column", {"table:style-name": column})
    for row in block["rows"]:
        tr = node(table, "table:table-row", {"table:style-name": styles.row(auto)})
        for cell, column_width in zip(row["cells"], widths):
            attrs = {"table:style-name": styles.cell(auto, row.get("valign", "top"), block.get("borders", False)), "office:value-type": "string"}
            td = node(tr, "table:table-cell", attrs)
            for para in cell:
                _paragraph(td, para, column_width, styles, auto)
            if not cell:
                paragraph(td, name=styles.empty())


def build(source, rules):
    layout = build_layout(source["documentType"], template=True)
    root = document("content")
    fonts(root, writer=True)
    auto = node(root, "office:automatic-styles")
    text = node(node(root, "office:body"), "office:text")
    styles = Styles(rules)
    for index, block in enumerate(layout["blocks"]):
        if block["type"] == "grid":
            _grid(text, block, layout["textWidthMm"], styles, auto, index)
        else:
            _paragraph(text, block, layout["textWidthMm"], styles, auto)
    return {"content.xml": xml(root), "styles.xml": style_document(rules, styles)}
