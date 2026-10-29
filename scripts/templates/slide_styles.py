# SPDX-License-Identifier: AGPL-3.0-only
"""Presentation masters and editable layout definitions."""
from .odf import document, fonts, node, style, xml


def build(theme):
    root = document("styles")
    fonts(root)
    styles = node(root, "office:styles")
    for name, size, color in [("Title", 32, theme["accent"]), ("Body", 22, "#243543"),
                              ("Small", 16, "#243543"), ("Notes", 12, "#243543")]:
        style(styles, name, "paragraph", {"paragraph": {"fo:margin-bottom": "6mm"},
              "text": {"style:font-name": "Liberation Sans", "fo:font-size": f"{size}pt",
                       "fo:language": "vi", "fo:country": "VN", "fo:color": color,
                       "fo:font-weight": "bold" if name == "Title" else "normal"}})
    style(styles, "TextBox", "graphic", {"graphic": {"draw:fill": "none", "draw:stroke": "none",
          "fo:padding": "0mm", "draw:auto-grow-height": "false", "fo:wrap-option": "wrap"}})
    style(styles, "Accent", "graphic", {"graphic": {"draw:fill": "solid",
          "draw:fill-color": theme["accent"], "draw:stroke": "none"}})
    style(styles, "TableCell", "table-cell", {"table-cell": {"fo:padding": "4mm",
          "fo:border": "0.2mm solid #b8c8d4", "fo:background-color": theme["tint"]}})
    for name in ["title", "content", "section", "table", "chart"]:
        layout = node(styles, "style:presentation-page-layout", {"style:name": name})
        node(layout, "presentation:placeholder", {"presentation:object": "title",
             "svg:x": "20mm", "svg:y": "18mm", "svg:width": "280mm", "svg:height": "32mm"})
        node(layout, "presentation:placeholder", {"presentation:object": {
             "title": "subtitle", "content": "outline", "section": "subtitle",
             "table": "table", "chart": "chart"}[name],
             "svg:x": "20mm", "svg:y": "60mm", "svg:width": "280mm", "svg:height": "95mm"})
    auto = node(root, "office:automatic-styles")
    for name, width, height in [("Wide", 320, 180), ("NotesPage", 210, 297)]:
        layout = node(auto, "style:page-layout", {"style:name": name})
        node(layout, "style:page-layout-properties", {"fo:page-width": f"{width}mm",
             "fo:page-height": f"{height}mm", "style:print-orientation": "landscape" if width > height else "portrait",
             "fo:margin": "0mm"})
    for name, color in [("Light", "#ffffff"), ("Tint", theme["tint"])]:
        style(auto, name, "drawing-page", {"drawing-page": {
            "draw:fill": "solid", "draw:fill-color": color,
            "presentation:background-visible": "true", "presentation:background-objects-visible": "true"}})
    masters = node(root, "office:master-styles")
    layers = node(masters, "draw:layer-set")
    node(layers, "draw:layer", {"draw:name": "layout"})
    for name, page in [("HST", "Light"), ("Section", "Tint")]:
        master = node(masters, "style:master-page", {"style:name": name,
                      "style:page-layout-name": "Wide", "draw:style-name": page})
        node(master, "draw:rect", {"draw:style-name": "Accent", "draw:layer": "layout",
             "svg:x": "0mm", "svg:y": "0mm", "svg:width": "320mm", "svg:height": "4mm"})
        node(master, "presentation:notes", {"style:page-layout-name": "NotesPage"})
    return xml(root)
