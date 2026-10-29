# SPDX-License-Identifier: AGPL-3.0-only
"""Seven editable administrative forms, including the distinct official letter."""
from .odf import document, fonts, node, paragraph, style, xml
from .writer_styles import build as style_document


def table(parent, name, widths, auto, first=False):
    attrs = {"style:master-page-name": "FirstPage"} if first else {}
    style(auto, name, "table", {"table": {"style:width": f"{sum(widths):g}mm",
          "table:align": "margins", "fo:keep-with-next": "always"}}, attrs)
    result = node(parent, "table:table", {"table:name": name, "table:style-name": name})
    for index, width in enumerate(widths):
        col = name + str(index)
        style(auto, col, "table-column", {"table-column": {"style:column-width": f"{width:g}mm"}})
        node(result, "table:table-column", {"table:style-name": col})
    row = node(result, "table:table-row")
    return [node(row, "table:table-cell", {"table:style-name": "Borderless",
                 "office:value-type": "string"}) for _ in widths]


def rule(parent, name, width, auto):
    """A paragraph-anchored vector line; widths come from ND30, never underscores."""
    style_name = "Rule" + name
    style(auto, style_name, "graphic", {"graphic": {
        "draw:stroke": "solid", "svg:stroke-width": "0.2mm", "svg:stroke-color": "#000000",
        "style:horizontal-pos": "center", "style:horizontal-rel": "paragraph",
        "style:vertical-pos": "middle", "style:vertical-rel": "text"}})
    p = paragraph(parent, name="RuleParagraph")
    node(p, "draw:line", {"draw:style-name": style_name, "text:anchor-type": "as-char",
         "svg:x1": "0mm", "svg:y1": "0mm", "svg:x2": f"{width}mm", "svg:y2": "0mm"})


def build(source, rules):
    root = document("content")
    fonts(root, writer=True)
    auto = node(root, "office:automatic-styles")
    style(auto, "Borderless", "table-cell", {"table-cell": {
        "fo:border": "none", "fo:padding": "0mm", "style:vertical-align": "top"}})
    style(auto, "RuleParagraph", "paragraph", {"paragraph": {
        "fo:text-align": "center", "fo:text-indent": "0mm", "fo:line-height": "3mm",
        "fo:margin-top": "1mm", "fo:margin-bottom": "2mm"}})
    text = node(node(root, "office:body"), "office:text")
    p = rules["placeholders"]
    page = rules["pageSizeMm"]["width"]
    margin = rules["defaultMarginsMm"]
    usable = page - margin["left"] - margin["right"]
    widths = [usable * x / 100 for x in rules["layoutRules"]["headerWidthsPct"]]
    left, right = table(text, "Header", widths, auto, first=True)
    paragraph(left, p["parentAgency"], "ParentAgency")
    paragraph(left, p["agency"], "Agency")
    rule(left, "Agency", rules["ruleWidthMm"]["agency"], auto)
    paragraph(left, f'Số: {p["number"]}/{p["symbol"]}', "Number")
    dtype = next(d for d in rules["documentTypes"] if d["id"] == source["documentType"])
    if dtype["officialLetter"]:
        paragraph(left, "V/v " + p["summary"], "OfficialSummary")
    paragraph(right, rules["nationalTitle"], "NationalTitle")
    paragraph(right, rules["motto"], "Motto")
    rule(right, "Motto", rules["ruleWidthMm"]["motto"], auto)
    paragraph(right, p["place"] + ", ngày " + p["date"], "PlaceDate")
    paragraph(text, name="Body")
    if not dtype["officialLetter"]:
        paragraph(text, dtype["typeName"], "TypeName")
        paragraph(text, p["summary"], "Summary")
        rule(text, "Title", rules["ruleWidthMm"]["title"], auto)
    if dtype["kinhGui"]:
        paragraph(text, "Kính gửi: " + p["kinhGui"], "KinhGui")
    for line in source["paragraphs"]:
        paragraph(text, line, "Body")
    widths = [usable * x / 100 for x in rules["layoutRules"]["signatureWidthsPct"]]
    left, right = table(text, "Signature", widths, auto)
    if source["id"] == "bien-ban":
        paragraph(left, "[CHỦ TRÌ]", "Authority")
        paragraph(left, "[Ký, ghi rõ họ tên]", "PlaceDate")
        paragraph(left, "[Họ và tên]", "Signer")
        paragraph(right, "[THƯ KÝ]", "Authority")
    else:
        paragraph(left, "Nơi nhận:", "RecipientsHeading")
        paragraph(left, "- " + p["recipients"] + ";", "RecipientsList")
        paragraph(left, "- " + rules["layoutRules"]["recipientsAppendLuuIfMissing"] + ".",
                  "RecipientsList")
        paragraph(right, p["signerAuthority"], "Authority")
    paragraph(right, "[Ký, ghi rõ họ tên]", "PlaceDate")
    paragraph(right, name="Body")
    paragraph(right, p["signerName"], "Signer")
    if source["id"] == "bien-ban":
        paragraph(text, "Nơi nhận:", "RecipientsHeading")
        paragraph(text, "- " + p["recipients"] + ";", "RecipientsList")
        paragraph(text, "- " + rules["layoutRules"]["recipientsAppendLuuIfMissing"] + ".", "RecipientsList")
    return {"content.xml": xml(root), "styles.xml": style_document(rules)}
