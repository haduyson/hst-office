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
        self.attached = False

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

    def rule(self, side_mm, after_pt=0):
        name = "Rule%d_%d" % (round(side_mm * 100), after_pt)
        self.named[name] = ({"fo:margin-left": f"{side_mm:g}mm", "fo:margin-right": f"{side_mm:g}mm", "fo:margin-top": "2pt", "fo:margin-bottom": f"{after_pt:g}pt",
                             "fo:text-indent": "0mm", "fo:line-height": "100%", "fo:border-bottom": RULE_WIDTH, "fo:padding": "0mm"}, {"fo:font-size": "1pt"})
        return name

    def document_end(self):
        self.named["DocumentEnd"] = ({"fo:margin-top": "0pt", "fo:margin-bottom": "0pt", "fo:text-indent": "0mm", "fo:line-height": "100%"}, {"fo:font-size": "1pt"})
        return "DocumentEnd"

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

    def cell(self, auto, valign, borders, first_row=True):
        """A ruled cell draws the line above it only in the first row: below that the row above already draws it. Writer
        can lay two adjacent lines out as one while rows are added to an open document, and as two after reloading, so a
        filled form moved by one line width per row when it was saved and reopened."""
        top = first_row or not borders
        key = ("cell", valign, borders, top)
        if key not in self.auto:
            self.auto[key] = "Cell%d" % (len(self.auto) + 1)
            border = {"fo:border": RULE_WIDTH, "fo:padding": "0.5mm"} if borders else {"fo:border": "none", "fo:padding": "0mm"}
            if not top:
                border = {"fo:border-left": RULE_WIDTH, "fo:border-right": RULE_WIDTH, "fo:border-top": "none",
                          "fo:border-bottom": RULE_WIDTH, "fo:padding": "0.5mm"}
            style(auto, self.auto[key], "table-cell", {"table-cell": {**border, "style:vertical-align": valign}})
        return self.auto[key]

    def section(self, para, auto):
        """A paragraph that starts a new page and restarts the page numbers (an annex in the body of a circular)."""
        name = "Section%d" % (len(self.auto) + 1)
        self.auto[name] = name
        self.attached = True
        style(auto, name, "paragraph", {"paragraph": {**_props(para), "style:page-number": "1"}, "text": _text_props(para["runs"][0])},
              {"style:parent-style-name": "Standard", "style:master-page-name": "Attached"})
        return name

    def row(self, auto, height=None):
        key = ("row", height)
        if key not in self.auto:
            self.auto[key] = "Row%d" % (len(self.auto) + 1)
            props = {"fo:keep-together": "always"}
            if height:
                props["style:min-row-height"] = f"{height:g}mm"
            style(auto, self.auto[key], "table-row", {"table-row": props})
        return self.auto[key]


def _page_layout(automatic, rules, page, footer=False):
    size, margins = rules["pageSizeMm"], rules["defaultMarginsMm"]
    header_mm = rules["pageHeaderMm"]
    layout = node(automatic, "style:page-layout", {"style:name": "Layout"})
    if page:  # the envelope: its own size, no page number
        node(layout, "style:page-layout-properties", {"fo:page-width": f'{page["width"]}mm', "fo:page-height": f'{page["height"]}mm', "style:print-orientation": "landscape",
             **{f"fo:margin-{side}": f"{page[side]}mm" for side in ("top", "bottom", "left", "right")}})
        return
    # The body starts at the top margin: the header is the fixed-height band just above it (same as nd30_page).
    edges = {**{f"fo:margin-{side}": f"{value}mm" for side, value in margins.items()}, "fo:margin-top": f'{margins["top"] - header_mm:g}mm'}
    if footer:  # the first-page footer band sits in the bottom margin, the body still ends at the bottom margin
        edges["fo:margin-bottom"] = f'{margins["bottom"] - header_mm:g}mm'
    node(layout, "style:page-layout-properties", {"fo:page-width": f'{size["width"]}mm', "fo:page-height": f'{size["height"]}mm',
         "style:print-orientation": "portrait", "style:num-format": "1", **edges})
    band = node(layout, "style:header-style")
    node(band, "style:header-footer-properties", {"svg:height": f"{header_mm}mm", "fo:margin-bottom": "0mm", "style:dynamic-spacing": "false"})
    if footer:
        band = node(layout, "style:footer-style")
        node(band, "style:header-footer-properties", {"fo:min-height": f"{header_mm}mm", "fo:margin-top": "0mm", "style:dynamic-spacing": "false"})


def _master(masters, name, numbered, band=False, footer=()):
    master = node(masters, "style:master-page", {"style:name": name, "style:page-layout-name": "Layout"})
    if numbered:
        number = paragraph(node(master, "style:header"), name="PageNumber")
        node(number, "text:page-number", {"text:select-page": "current"}, "2")
        paragraph(node(master, "style:header-first"), name="PageNumber")
    if band:  # pages after the first keep an empty footer band; the first page shows the contact details
        paragraph(node(master, "style:footer"), name="DocumentEnd")
        first = node(master, "style:footer-first") if footer else None
        for style_name, block in footer:
            paragraph(first, block["runs"][0]["text"], name=style_name)


def build(rules, styles, page=None, footer=(), footer_styles=()):
    root = document("styles")
    fonts(root, writer=True)
    office = node(root, "office:styles")
    t = rules["typography"]
    default = node(office, "style:default-style", {"style:family": "paragraph"})
    # The East Asian font is the text font as well: otherwise Word stores every Vietnamese letter of
    # U+1E00-U+1EFF in a run of its own when it saves the .docx (hst-writer-cjk-default-font.patch).
    node(default, "style:text-properties", {"style:font-name": t["fontFamily"], "style:font-name-asian": t["fontFamily"],
         "fo:font-size": f'{t["body"]}pt', "fo:language": "vi", "fo:country": "VN", "fo:color": "#000000"})
    style(office, "Standard", "paragraph", {"paragraph": {"fo:margin-bottom": "0pt"}})
    for name, (props, text) in sorted(styles.named.items()):
        style(office, name, "paragraph", {"paragraph": props, "text": text})
    style(office, "PageNumber", "paragraph", {"paragraph": {"fo:text-align": "center", "fo:text-indent": "0mm", "fo:margin-bottom": "0pt"},
                                              "text": {"fo:font-size": f'{t["pageNumber"]}pt', "fo:font-weight": "normal", "fo:font-style": "normal"}})
    _page_layout(node(root, "office:automatic-styles"), rules, page, bool(footer))
    masters = node(root, "office:master-styles")
    _master(masters, "Standard", not page, bool(footer), list(zip(footer_styles, footer)))
    if styles.attached:
        _master(masters, "Attached", True, bool(footer))
    return xml(root)
