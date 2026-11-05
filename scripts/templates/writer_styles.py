# SPDX-License-Identifier: AGPL-3.0-only
"""Writer styles of a template: named paragraph styles per role and the one page style both creation paths use."""
from .odf import document, fonts, node, paragraph, style, xml

ALIGN = {"left": "left", "center": "center", "justify": "justify", "right": "right"}
RULE_WIDTH = "0.75pt solid #000000"


def _props(para):
    props = {"fo:text-align": ALIGN[para.get("align", "left")],
             "fo:text-indent": f'{para.get("indent_first_mm", 0):g}mm',
             "fo:margin-left": f'{para.get("indent_left_mm", 0):g}mm', "fo:margin-right": "0mm",
             "fo:margin-top": f'{para.get("spacing_before_pt", 0):g}pt',
             "fo:margin-bottom": f'{para.get("spacing_after_pt", 0):g}pt'}
    if para.get("line_exact_pt"):
        props["fo:line-height"] = f'{para["line_exact_pt"]:g}pt'
    else:
        props["fo:line-height"] = f'{para.get("line_spacing", 1.0) * 100:g}%'
    if para.get("keep_with_next"):
        props["fo:keep-with-next"] = "always"
    if para.get("top_rule"):
        props.update({"fo:border-top": RULE_WIDTH, "fo:padding-top": "1mm"})
    return props


def _text_props(item):
    props = {"fo:font-size": f'{item["size"]:g}pt', "fo:font-weight": "bold" if item["bold"] else "normal",
             "fo:font-style": "italic" if item["italic"] else "normal"}
    if item.get("underline"):
        props.update({"style:text-underline-style": "solid", "style:text-underline-width": "auto", "style:text-underline-color": "font-color"})
    return props


class Styles:
    """Collects the styles a document needs while it is rendered; identical formats share one style."""

    def __init__(self, rules):
        self.rules = rules
        self.named = {}  # name -> (paragraph properties, text properties)
        self.keys = {}
        self.auto = {}

    def paragraph(self, para):
        first = para["runs"][0]
        text = _text_props(first if len(para["runs"]) == 1 else {**first, "bold": False, "italic": False})
        props = _props(para)
        key = (para.get("role", "Body"), tuple(sorted(props.items())), tuple(sorted(text.items())))
        if key not in self.keys:
            base = key[0]
            count = sum(1 for k in self.keys if k[0] == base)
            name = base if not count else "%s%d" % (base, count + 1)
            self.keys[key] = name
            self.named[name] = (props, text)
        return self.keys[key]

    def rule(self, side_mm):
        name = "Rule%d" % round(side_mm * 100)
        self.named[name] = ({"fo:margin-left": f"{side_mm:g}mm", "fo:margin-right": f"{side_mm:g}mm", "fo:margin-top": "0pt", "fo:margin-bottom": "0pt",
                             "fo:text-indent": "0mm", "fo:line-height": "100%", "fo:border-bottom": RULE_WIDTH, "fo:padding": "0mm"}, {"fo:font-size": "1pt"})
        return name

    def empty(self):
        self.named["EmptyCell"] = ({"fo:margin-bottom": "0pt", "fo:text-indent": "0mm"}, {"fo:font-size": "1pt"})
        return "EmptyCell"

    def span(self, item, auto):
        props = _text_props(item)
        key = ("span", tuple(sorted(props.items())))
        if key not in self.auto:
            self.auto[key] = "T%d" % (len(self.auto) + 1)
            style(auto, self.auto[key], "text", {"text": props})
        return self.auto[key]

    def cell(self, auto, valign, borders):
        key = ("cell", valign, borders)
        if key not in self.auto:
            self.auto[key] = "Cell%d" % (len(self.auto) + 1)
            border = {"fo:border": RULE_WIDTH, "fo:padding": "0.5mm"} if borders else {"fo:border": "none", "fo:padding": "0mm"}
            style(auto, self.auto[key], "table-cell", {"table-cell": {**border, "style:vertical-align": valign}})
        return self.auto[key]

    def row(self, auto):
        if "row" not in self.auto:
            self.auto["row"] = "Row"
            style(auto, "Row", "table-row", {"table-row": {"fo:keep-together": "always"}})
        return "Row"


def build(rules, styles):
    root = document("styles")
    fonts(root, writer=True)
    office = node(root, "office:styles")
    t = rules["typography"]
    default = node(office, "style:default-style", {"style:family": "paragraph"})
    node(default, "style:text-properties", {"style:font-name": t["fontFamily"], "fo:font-size": f'{t["body"]}pt',
         "fo:language": "vi", "fo:country": "VN", "fo:color": "#000000"})
    for name, (props, text) in sorted(styles.named.items()):
        style(office, name, "paragraph", {"paragraph": props, "text": text})
    style(office, "PageNumber", "paragraph", {"paragraph": {"fo:text-align": "center", "fo:text-indent": "0mm", "fo:margin-bottom": "0pt"},
                                              "text": {"fo:font-size": f'{t["pageNumber"]}pt', "fo:font-weight": "normal", "fo:font-style": "normal"}})
    automatic = node(root, "office:automatic-styles")
    size, margins = rules["pageSizeMm"], rules["defaultMarginsMm"]
    header_mm = rules["pageHeaderMm"]
    layout = node(automatic, "style:page-layout", {"style:name": "Layout"})
    # The body starts at the ND30 top margin: the header is the fixed-height band just above it (same as nd30_page).
    page = {**{f"fo:margin-{side}": f"{value}mm" for side, value in margins.items()}, "fo:margin-top": f'{margins["top"] - header_mm:g}mm'}
    node(layout, "style:page-layout-properties", {"fo:page-width": f'{size["width"]}mm', "fo:page-height": f'{size["height"]}mm',
         "style:print-orientation": "portrait", "style:num-format": "1", **page})
    band = node(layout, "style:header-style")
    node(band, "style:header-footer-properties", {"svg:height": f"{header_mm}mm", "fo:margin-bottom": "0mm", "style:dynamic-spacing": "false"})
    masters = node(root, "office:master-styles")
    master = node(masters, "style:master-page", {"style:name": "Standard", "style:page-layout-name": "Layout"})
    number = paragraph(node(master, "style:header"), name="PageNumber")
    node(number, "text:page-number", {"text:select-page": "current"}, "2")
    paragraph(node(master, "style:header-first"), name="PageNumber")
    return xml(root)
