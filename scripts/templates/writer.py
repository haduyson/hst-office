# SPDX-License-Identifier: AGPL-3.0-only
"""ODF renderer of the shared document layout: the .ott templates are hst_office.nd30_layout, written directly as XML."""
from .odf import document, fonts, node, paragraph, style, xml
from .writer_layout import build_layout, portable_blocks
from .writer_styles import build as style_document, Styles


def _rule(parent, para, cell_mm, styles):
    side = max(0.0, (cell_mm - para["rule_mm"]) / 2)
    paragraph(parent, name=styles.rule(side, para.get("spacing_after_pt", 0)))


def _paragraph(parent, para, cell_mm, styles, auto):
    # the space after a ruled paragraph belongs under the rule
    plain = {**para, "spacing_after_pt": 0} if para.get("rule_mm") else para
    p = paragraph(parent, name=styles.section(plain, auto) if para.get("new_section") else styles.paragraph(plain))
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
    if block.get("spacing_after_pt"):
        table_props["fo:margin-bottom"] = f'{block["spacing_after_pt"]:g}pt'
    if block.get("keep_with_next"):
        table_props["fo:keep-with-next"] = "always"
    extra = {}
    if block.get("new_section"):  # the attached document of forms 1.3 and 15 numbers its pages from 1
        table_props["style:page-number"] = "1"
        extra["style:master-page-name"] = "Attached"
        styles.attached = True
    style(auto, name, "table", {"table": table_props}, extra)
    table = node(parent, "table:table", {"table:name": name, "table:style-name": name})
    for i, column_width in enumerate(widths):
        column = "%s.%d" % (name, i)
        style(auto, column, "table-column", {"table-column": {"style:column-width": f"{column_width:g}mm"}})
        node(table, "table:table-column", {"table:style-name": column})
    holder = table
    if block.get("repeatHeader"):
        holder = node(table, "table:table-header-rows")
    for row_index, row in enumerate(block["rows"]):
        tr = node(holder, "table:table-row", {"table:style-name": styles.row(auto, row.get("heightMm"))})
        if holder is not table:
            holder = table
        for cell, column_width in zip(row["cells"], [width] if row.get("merged") else widths):
            attrs = {"table:style-name": styles.cell(auto, row.get("valign", "top"), block.get("borders", False), row_index == 0),
                     "office:value-type": "string"}
            if row.get("merged"):
                attrs["table:number-columns-spanned"] = str(len(widths))
            td = node(tr, "table:table-cell", attrs)
            for para in cell:
                _paragraph(td, para, column_width, styles, auto)
            if not cell:
                paragraph(td, name=styles.empty())
        if row.get("merged"):
            for _ in widths[1:]:
                node(tr, "table:covered-table-cell")


def build(source, rules):
    layout = build_layout(source["documentType"], template=True)
    root = document("content")
    fonts(root, writer=True)
    auto = node(root, "office:automatic-styles")
    text = node(node(root, "office:body"), "office:text")
    styles = Styles(rules)
    blocks, footer = portable_blocks(layout)
    for index, block in enumerate(blocks):
        if block["type"] == "grid":
            _grid(text, block, layout["textWidthMm"], styles, auto, index)
        else:
            _paragraph(text, block, layout["textWidthMm"], styles, auto)
    if blocks and blocks[-1]["type"] == "grid":
        # Writer always keeps a paragraph after a closing table; at 1 pt it cannot spill onto a blank last page
        paragraph(text, name=styles.document_end())
    if footer:
        styles.document_end()  # the empty footer of the pages after the first
    first_footer = [styles.paragraph(b) for b in footer]
    return {"content.xml": xml(root), "styles.xml": style_document(rules, styles, layout.get("page"), footer, first_footer)}
