# SPDX-License-Identifier: AGPL-3.0-only
"""Native Calc number styles translated from the shared format-code contract."""
import re
from .odf import document, fonts, node, style, xml


def number_styles(parent, formats):
    language, country = formats["locale"].split("-")
    for name, spec in formats["formats"].items():
        kind = {"date": "date", "vnd": "currency", "percent": "percentage"}.get(name, "number")
        attrs = {"style:name": "Format_" + name, "number:language": language,
                 "number:country": country}
        if name == "date":
            attrs["number:automatic-order"] = "false"
        root = node(parent, "number:" + kind + "-style", attrs)
        code = spec["code"]
        if name == "date":
            for token in re.findall(r"DD|MM|YYYY|[^DMY]+", code):
                part = {"DD": "day", "MM": "month", "YYYY": "year"}.get(token)
                if part:
                    node(root, "number:" + part, {"number:style": "long"})
                else:
                    node(root, "number:text", text=token)
        else:
            decimal = re.search(r"\.(0+)", code)
            decimals = spec.get("decimals", len(decimal[1]) if decimal else 0)
            node(root, "number:number", {"number:decimal-places": decimals,
                 "number:min-integer-digits": 1,
                 "number:grouping": str("," in code).lower()})
            if name == "percent":
                node(root, "number:text", text="%")
            if name == "vnd":
                symbol = re.search(r"\[\$(.+?)-[0-9A-Fa-f]+\]", code)
                if not symbol:
                    raise ValueError("Unsupported shared currency format: " + code)
                node(root, "number:text", text=" ")
                node(root, "number:currency-symbol", {"number:language": language,
                     "number:country": country}, symbol[1])


def build(formats):
    root = document("styles")
    fonts(root)
    styles = node(root, "office:styles")
    number_styles(styles, formats)
    for kind in ["text", "integer", "vnd", "date", "percent", "Header", "Title", "Note"]:
        for formula in ([False, True] if kind in formats["formats"] else [False]):
            name = "Cell_" + kind + ("_formula" if formula else "")
            special = kind in {"Header", "Title", "Note"}
            cell = {"fo:padding": "1.5mm", "fo:wrap-option": "wrap",
                    "fo:border": "0.2mm solid #bccbd6", "style:vertical-align": "middle",
                    "style:cell-protect": "protected" if formula else "none"}
            if special:
                cell["fo:background-color"] = "#16324f" if kind != "Note" else "#eef3f6"
            elif formula:
                cell["fo:background-color"] = "#e3f1f8"
            extra = {"style:data-style-name": "Format_" + kind} if not special and kind != "text" else {}
            style(styles, name, "table-cell", {"table-cell": cell, "text": {
                "style:font-name": "Liberation Sans", "fo:font-size": "16pt" if kind == "Title" else "10pt",
                "fo:language": "vi", "fo:country": "VN",
                "fo:color": "#ffffff" if kind in {"Header", "Title"} else "#172e3d",
                "fo:font-weight": "bold" if kind in {"Header", "Title"} else "normal"}}, extra)
    auto = node(root, "office:automatic-styles")
    layout = node(auto, "style:page-layout", {"style:name": "SheetPage"})
    node(layout, "style:page-layout-properties", {"fo:page-width": "297mm",
         "fo:page-height": "210mm", "style:print-orientation": "landscape",
         "fo:margin": "15mm", "style:scale-to-X": "1", "style:scale-to-Y": "0",
         "style:table-centering": "horizontal", "style:print": "objects charts drawings"})
    # Explicit header/footer geometry: without it LibreOffice saves empty header/footer
    # styles, and fit-to-width pages of that saved file then print blank.
    for part, side in [("header", "bottom"), ("footer", "top")]:
        box = node(layout, f"style:{part}-style")
        node(box, "style:header-footer-properties", {"fo:min-height": "5mm", f"fo:margin-{side}": "2mm"})
    masters = node(root, "office:master-styles")
    node(masters, "style:master-page", {"style:name": "Default", "style:page-layout-name": "SheetPage"})
    return xml(root)


def settings(sheet_name):
    root = document("settings")
    settings = node(root, "office:settings")
    view = node(settings, "config:config-item-set", {"config:name": "ooo:view-settings"})
    views = node(view, "config:config-item-map-indexed", {"config:name": "Views"})
    entry = node(views, "config:config-item-map-entry")
    node(entry, "config:config-item", {"config:name": "ViewId", "config:type": "string"}, "view1")
    node(entry, "config:config-item", {"config:name": "ActiveTable", "config:type": "string"}, sheet_name)
    tables = node(entry, "config:config-item-map-named", {"config:name": "Tables"})
    sheet = node(tables, "config:config-item-map-entry", {"config:name": sheet_name})
    for name, value in {"VerticalSplitMode": 2, "VerticalSplitPosition": 4,
                        "PositionBottom": 4, "ActiveSplitRange": 2}.items():
        node(sheet, "config:config-item", {"config:name": name, "config:type": "short" if "Mode" in name or name == "ActiveSplitRange" else "int"}, str(value))
    return xml(root)
