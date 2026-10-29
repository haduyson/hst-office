# SPDX-License-Identifier: AGPL-3.0-only
"""Writer styles derived exclusively from the frozen ND30 data contract."""
from .odf import document, fonts, node, paragraph, style, xml


def build(rules):
    root = document("styles")
    fonts(root, writer=True)
    styles = node(root, "office:styles")
    t = rules["typography"]
    default = node(styles, "style:default-style", {"style:family": "paragraph"})
    node(default, "style:text-properties", {"style:font-name": t["fontFamily"],
         "fo:font-size": f'{t["body"]}pt', "fo:language": "vi", "fo:country": "VN",
         "fo:color": "#000000"})
    node(default, "style:paragraph-properties", {"fo:text-align": "justify",
         "fo:text-indent": f'{t["bodyFirstLineIndentMm"]}mm',
         "fo:margin-bottom": f'{t["paragraphSpacingPt"]}pt',
         "fo:line-height": f'{t["lineSpacing"] * 100:g}%'})
    names = {"Body": ("body", "justify", False, False),
             "ParentAgency": ("parentAgency", "center", False, False),
             "Agency": ("agency", "center", True, False),
             "NationalTitle": ("nationalTitle", "center", True, False),
             "Motto": ("motto", "center", True, False),
             "Number": ("number", "center", False, False),
             "PlaceDate": ("placeDate", "center", False, True),
             "TypeName": ("typeName", "center", True, False),
             "Summary": ("summary", "center", True, False),
             "OfficialSummary": ("summaryOfficialLetter", "center", False, False),
             "KinhGui": ("kinhGui", "left", False, False),
             "Authority": ("signerAuthority", "center", True, False),
             "Signer": ("signerName", "center", True, False),
             "RecipientsHeading": ("recipientsHeading", "left", True, True),
             "RecipientsList": ("recipientsList", "left", False, False),
             "PageNumber": ("number", "center", False, False)}
    for name, (size, align, bold, italic) in names.items():
        props = {"fo:text-align": align, "fo:text-indent": "0mm"}
        if name == "Body":
            props["fo:text-indent"] = f'{t["bodyFirstLineIndentMm"]}mm'
        if name == "OfficialSummary":
            props["fo:margin-top"] = f'{t["paragraphSpacingPt"]}pt'
        if name in {"ParentAgency", "Agency", "NationalTitle", "Motto", "Number"}:
            props.update({"fo:line-height": "100%", "fo:margin-bottom": "0pt"})
        style(styles, name, "paragraph", {"paragraph": props, "text": {
            "fo:font-size": f'{t[size]}pt', "fo:font-weight": "bold" if bold else "normal",
            "fo:font-style": "italic" if italic else "normal"}})
    automatic = node(root, "office:automatic-styles")
    size, margins = rules["pageSizeMm"], rules["defaultMarginsMm"]
    for name, header in [("FirstLayout", False), ("NextLayout", True)]:
        layout = node(automatic, "style:page-layout", {"style:name": name})
        node(layout, "style:page-layout-properties", {
            "fo:page-width": f'{size["width"]}mm', "fo:page-height": f'{size["height"]}mm',
            "style:print-orientation": "portrait", "style:num-format": "1",
            **{f"fo:margin-{side}": f"{value}mm" for side, value in margins.items()}})
        if header:
            hs = node(layout, "style:header-style")
            node(hs, "style:header-footer-properties", {"fo:min-height": "5mm",
                 "fo:margin-bottom": "2mm", "style:dynamic-spacing": "false"})
    masters = node(root, "office:master-styles")
    node(masters, "style:master-page", {"style:name": "FirstPage",
         "style:page-layout-name": "FirstLayout", "style:next-style-name": "Standard"})
    master = node(masters, "style:master-page", {"style:name": "Standard",
                  "style:page-layout-name": "NextLayout"})
    page = paragraph(node(master, "style:header"), name="PageNumber")
    node(page, "text:page-number", {"text:select-page": "current"}, "2")
    return xml(root)
