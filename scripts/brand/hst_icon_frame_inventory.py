#!/usr/bin/env python3
# SPDX-License-Identifier: AGPL-3.0-only
"""Inventory of the HST frame elements that show an icon: what each draws today and who draws it.

Frame elements are the File tab (backstage) navigation and actions, the sidebar tab bar and deck
chrome, the status bar controls and the document tab buttons. Menu items (context and popup
menus) are excluded: they reuse the LibreOffice icons by owner decision of 20/11/2026.

Each element is read from the sources it is drawn by: the HST-patched tree (--patched-tree; files
the HST series touches) over the pristine LibreOffice tree (--lo-tree; every other file). The
backstage navigation, the sidebar decks and the status bar items are parsed from their sources, so
a new item appears here without editing this script; the image of each status bar control and of
the sidebar chrome comes from CONTROLS / CHROME, verified against the source on every run.

For every icon request the script records whether the SVG Colibre of the pristine tree draws it
(and at which native size), whether the HST glyph themes draw it, and whether the default
"Cổ điển" theme (hst_classic) shows the HST glyph instead of Colibre. `needs` then says what phase 08
does about it:
  draw          no LibreOffice icon exists (vector-drawn ad hoc or no image): a new HST frame glyph;
  modern-only   Colibre draws it, Cổ điển keeps Colibre; an HST glyph only completes hst_modern;
  none          Colibre draws it and HST already has a glyph, or the element shows no icon.
Standard library only. --check compares with the committed file instead of writing it.
"""
import argparse
import importlib.util
import json
from pathlib import Path, PurePosixPath
import re
import sys
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[2]
OUTPUT = ROOT / "icon-themes-src/hst-modern/metadata/frame-inventory.json"
sys.path.insert(0, str(Path(__file__).resolve().parent))
import hst_classic_icons as classic  # noqa: E402

BACKSTAGE = "sfx2/source/backstage/hstbackstagewindow.cxx"
BACKSTAGE_UI = "sfx2/uiconfig/ui/hstbackstage.ui"
SIDEBAR_XCU = "officecfg/registry/data/org/openoffice/Office/UI/Sidebar.xcu"
DOCTABS = "framework/source/uielement/documenttabbar.cxx"
STATUSBARS = {"writer": "sw/uiconfig/swriter/statusbar/statusbar.xml",
              "sheets": "sc/uiconfig/scalc/statusbar/statusbar.xml",
              "slides": "sd/uiconfig/simpress/statusbar/statusbar.xml",
              "draw": "sd/uiconfig/sdraw/statusbar/statusbar.xml"}
# Status bar item -> (control source, bitmap list, image constants). Items not listed draw text only.
CONTROLS = {
    ".uno:ModifiedStatus": ("svx/source/stbctrls/modctrl.cxx", "svx/inc/bitmaps.hlst",
                            ("RID_SVXBMP_DOC_MODIFIED_NO", "RID_SVXBMP_DOC_MODIFIED_YES",
                             "RID_SVXBMP_DOC_MODIFIED_FEEDBACK")),
    ".uno:Signature": ("svx/source/stbctrls/xmlsecctrl.cxx", "svx/inc/bitmaps.hlst",
                       ("RID_SVXBMP_SIGNET", "RID_SVXBMP_SIGNET_BROKEN", "RID_SVXBMP_SIGNET_NOTVALIDATED")),
    ".uno:ZoomSlider": ("svx/source/stbctrls/zoomsliderctrl.cxx", "svx/inc/bitmaps.hlst",
                        ("RID_SVXBMP_SLIDERDECREASE", "RID_SVXBMP_SLIDERINCREASE", "RID_SVXBMP_SLIDERBUTTON")),
    ".uno:ZoomPage": ("svx/source/stbctrls/zoomctrl.cxx", "svx/inc/bitmaps.hlst", ("RID_SVXBMP_ZOOM_PAGE",)),
    ".uno:SelectionMode": ("svx/source/stbctrls/selctrl.cxx", "svx/inc/bitmaps.hlst",
                           ("RID_SVXBMP_STANDARD_SELECTION", "RID_SVXBMP_EXTENDING_SELECTION",
                            "RID_SVXBMP_ADDING_SELECTION", "RID_SVXBMP_BLOCK_SELECTION")),
    ".uno:StatusSelectionMode": ("svx/source/stbctrls/selctrl.cxx", "svx/inc/bitmaps.hlst",
                                 ("RID_SVXBMP_STANDARD_SELECTION", "RID_SVXBMP_EXTENDING_SELECTION",
                                  "RID_SVXBMP_ADDING_SELECTION", "RID_SVXBMP_BLOCK_SELECTION")),
    ".uno:Size": ("svx/source/stbctrls/pszctrl.cxx", "svx/inc/bitmaps.hlst", ("RID_SVXBMP_POSITION", "RID_SVXBMP_SIZE")),
    ".uno:StateAccessibilityCheck": ("sw/source/uibase/utlui/AccessibilityStatusBarControl.cxx", "sw/inc/bitmaps.hlst",
                                     ("RID_BMP_A11Y_CHECK_ISSUES_NOT_FOUND", "RID_BMP_A11Y_CHECK_ISSUES_FOUND")),
    ".uno:ViewLayout": ("sw/source/uibase/utlui/viewlayoutctrl.cxx", "sw/inc/bitmaps.hlst",
                        ("RID_BMP_VIEWLAYOUT_SINGLECOLUMN", "RID_BMP_VIEWLAYOUT_SINGLECOLUMN_ACTIVE",
                         "RID_BMP_VIEWLAYOUT_AUTOMATIC", "RID_BMP_VIEWLAYOUT_AUTOMATIC_ACTIVE",
                         "RID_BMP_VIEWLAYOUT_BOOKMODE", "RID_BMP_VIEWLAYOUT_BOOKMODE_ACTIVE")),
}
# Sidebar chrome: id -> (source, literal image request or constant in a bitmap list, label).
CHROME = {
    "sidebar-tabbar-menu": ("sfx2/uiconfig/ui/tabbarcontents.ui", "open-menu-symbolic", "vcl/inc/bitmaps.hlst",
                            "IMG_MENU", "Sidebar settings menu"),
    "sidebar-deck-close": ("sfx2/source/sidebar/DeckTitleBar.cxx", "sfx2/res/closedoc.png", None, None, "Close deck"),
    "sidebar-deck-grip": ("sfx2/source/sidebar/DeckTitleBar.cxx", "sfx2/res/grip.png", None, None,
                          "Deck grip (floating sidebar)"),
    "sidebar-panel-more": ("sfx2/uiconfig/ui/panel.ui", "sfx2/res/symphony/morebutton.png", None, None,
                           "Panel more options"),
    "sidebar-collapsed-indicator": ("sfx2/source/sidebar/SidebarController.cxx", "SIDEBAR_CLOSE_INDICATOR",
                                    "sfx2/inc/bitmaps.hlst", "SIDEBAR_CLOSE_INDICATOR", "Collapsed sidebar indicator"),
}
OWNER = {"backstage": "03", "sidebar": "04", "statusbar": "05", "doctabs": "07"}


class Trees:
    """Reads a source file from the HST-patched tree when the series touches it, else pristine."""

    def __init__(self, pristine, patched):
        self.pristine, self.patched = Path(pristine), Path(patched) if patched else None

    def path(self, relative):
        if self.patched and (self.patched / relative).is_file():
            return self.patched / relative, "patched"
        if (self.pristine / relative).is_file():
            return self.pristine / relative, "pristine"
        raise ValueError(f"{relative}: in neither tree")

    def text(self, relative):
        return self.path(relative)[0].read_text(encoding="utf-8")

    def line_of(self, relative, needle):
        """`relative:line` of the first line containing needle; a missing needle is an error."""
        for number, line in enumerate(self.text(relative).splitlines(), 1):
            if needle in line:
                return f"{relative}:{number}"
        raise ValueError(f"{relative}: {needle!r} not found; the source changed, update the inventory")


def constant(trees, hlst, name):
    match = re.search(rf'\b{re.escape(name)}\b\s*=\s*u?"([^"]+)"|#define\s+{re.escape(name)}\s+"([^"]+)"',
                      trees.text(hlst))
    if not match:
        raise ValueError(f"{hlst}: no constant {name}")
    return match.group(1) or match.group(2)


class Resolver:
    """What the SVG Colibre, the HST glyph theme and the Cổ điển overlay serve for an icon request."""

    def __init__(self, icon_themes):
        self.icon_themes = Path(icon_themes)
        self.colibre = classic.Coverage(self.icon_themes, "colibre_svg")
        spec = importlib.util.spec_from_file_location("hst_theme", ROOT / "scripts/brand/build-hst-icon-theme.py")
        builder = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(builder)
        # archive files and {request: target} links of the HST glyph theme and of the Cổ điển overlay
        self.hst_files = builder.resources("hst")
        self.hst_links = classic.parse_links(self.hst_files["links.txt"].decode("utf-8"))
        self.hst = set(self.hst_files) | set(self.hst_links)
        self.classic_files = builder.resources("hst_classic", self.icon_themes)
        self.classic_links = classic.parse_links(self.classic_files["links.txt"].decode("utf-8"))
        self.classic = set(self.classic_links)

    def colibre_file(self, request):
        stem = str(PurePosixPath(request).with_suffix(""))
        real = self.colibre.links.get(stem + ".png") or self.colibre.links.get(stem + ".svg") or request
        real = str(PurePosixPath(real).with_suffix(".svg"))
        path = self.icon_themes / "colibre_svg" / real
        return real if path.is_file() else None

    def native_size(self, real):
        root = ET.parse(self.icon_themes / "colibre_svg" / real).getroot()
        width, height = root.get("width", ""), root.get("height", "")
        number = re.compile(r"^\s*(\d+(?:\.\d+)?)(?:px)?\s*$")
        if number.match(width) and number.match(height):
            return [round(float(number.match(width).group(1))), round(float(number.match(height).group(1)))]
        box = (root.get("viewBox") or "").split()
        return [round(float(box[2])), round(float(box[3]))] if len(box) == 4 else None

    def describe(self, request):
        real = self.colibre_file(request)
        png, svg = (str(PurePosixPath(request).with_suffix(ext)) for ext in (".png", ".svg"))
        return {"request": request,
                "colibre_svg": real,
                "colibre_size": self.native_size(real) if real else None,
                "hst_glyph": png in self.hst or svg in self.hst,
                "classic_shows_hst": png in self.classic or svg in self.classic}


def needs(images, drawn_by):
    if drawn_by in ("vector", "none"):
        return "draw" if drawn_by == "vector" else "none"
    if any(not image["colibre_svg"] for image in images):
        return "draw"
    return "none" if all(image["hst_glyph"] for image in images) else "modern-only"


def command_request(command, size):
    """Icon request of a command: .uno:Save -> cmd/sc_save.png; org.hst.office.vi:SetupUsbToken -> cmd/sc_setupusbtoken.png
    (the name the HST .ui files give the extension commands' icons)."""
    return ("cmd/sc_" if size == 16 else "cmd/lc_") + command.rpartition(":")[2].lower() + ".png"


def backstage(trees, resolver):
    source = trees.text(BACKSTAGE)
    body = re.search(r"OUString lcl_navIconCommand\(.*?\n}\n", source, re.S)
    if not body:
        raise ValueError(f"{BACKSTAGE}: lcl_navIconCommand not found")
    nav = re.findall(r'rId == u"(nav\w+)"\)\s*return u"(\.uno:\w+)"', body.group())
    ui = trees.text(BACKSTAGE_UI)
    labels = dict(re.findall(r'context="hstbackstage\|(nav\w+)">([^<]+)<', ui))
    items = [{"id": "backstage-navhome", "label": labels.get("navhome", "Home"), "command": None,
              "source": trees.line_of(BACKSTAGE, "lcl_drawHouse(*xDev"), "drawn_by": "vector",
              "images": [], "note": "house outline drawn with polylines; the icon themes have no Home icon"}]
    for nav_id, command in nav:
        items.append({"id": f"backstage-{nav_id}", "label": labels.get(nav_id, nav_id), "command": command,
                      "source": trees.line_of(BACKSTAGE, f'u"{nav_id}"'), "drawn_by": "command-icon",
                      "images": [resolver.describe(command_request(command, 16))],
                      "note": "vcl::CommandInfoProvider::GetImageForCommand, small (16 px) icon of the frame's theme"})
    items.append({"id": "backstage-recent-pin", "label": "Pinned recent document", "command": None,
                  "source": trees.line_of(BACKSTAGE, "res/recentdoc_pin.png"), "drawn_by": "image",
                  "images": [resolver.describe("res/recentdoc_pin.png")], "note": "tree view image column"})
    # Page actions: buttons with text only today; listed so phase 03 reuses the LibreOffice icon of
    # the command if it adds icons.
    for widget, command in re.findall(r"&rButton == m_x(\w+)\.get\(\)\)[^\n]*\n\s*CloseAndDispatch\(u\"([^\"]+)\"",
                                      source):
        items.append({"id": f"backstage-action-{widget.lower()}", "label": widget, "command": command,
                      "source": trees.line_of(BACKSTAGE, f"m_x{widget}.get()"), "drawn_by": "none",
                      "images": [resolver.describe(command_request(command, 16))],
                      "note": "text button, no icon today"})
    return items


def sidebar(trees, resolver):
    text = trees.text(SIDEBAR_XCU)
    decks = text.split('<node oor:name="PanelList">')[0]
    items = []
    for match in re.finditer(r'<prop oor:name="Id"[^>]*>\s*<value>(\w+)</value>.*?'
                             r'<prop oor:name="IconURL"[^>]*>\s*<value>([^<]+)</value>', decks, re.S):
        deck, url = match.groups()
        request = url.removeprefix("private:graphicrepository/")
        items.append({"id": f"sidebar-deck-{deck}", "label": deck, "command": None,
                      "source": trees.line_of(SIDEBAR_XCU, f"<value>{deck}</value>"), "drawn_by": "image",
                      "images": [resolver.describe(request)], "note": "tab bar button, IconURL of the deck"})
    for element, (source, literal, hlst, name, label) in CHROME.items():
        request = constant(trees, hlst, name) if hlst else literal
        items.append({"id": element, "label": label, "command": None, "source": trees.line_of(source, literal),
                      "drawn_by": "image", "images": [resolver.describe(request)], "note": ""})
    return items


def statusbar(trees, resolver):
    apps = {}
    for app, path in STATUSBARS.items():
        for command in re.findall(r'xlink:href="(\.uno:\w+)"', trees.text(path)):
            apps.setdefault(command, []).append(app)
    items = []
    for command, used in apps.items():
        control = CONTROLS.get(command)
        if control is None:
            items.append({"id": f"statusbar-{command[5:].lower()}", "label": command[5:], "command": command,
                          "apps": used, "source": trees.line_of(STATUSBARS[used[0]], command), "drawn_by": "none",
                          "images": [], "note": "text field"})
            continue
        source, hlst, names = control
        for name in names:
            trees.line_of(source, name)  # the control still loads this image
        images = [resolver.describe(constant(trees, hlst, name)) for name in names]
        items.append({"id": f"statusbar-{command[5:].lower()}", "label": command[5:], "command": command,
                      "apps": used, "source": trees.line_of(source, names[0]), "drawn_by": "image",
                      "images": images, "note": f"Image(StockImage::Yes, ...) of {', '.join(names)}"})
    return items


def doctabs(trees):
    return [
        {"id": "doctabs-close", "label": "Close Tab", "command": None,
         "source": trees.line_of(DOCTABS, "// close button"), "drawn_by": "vector", "images": [],
         "note": "two DrawLine strokes in a 16 px box (CLOSE_SIZE)"},
        {"id": "doctabs-new", "label": "Open in New Tab", "command": None,
         "source": trees.line_of(DOCTABS, "const Point aPC = m_aPlusRect.Center()"), "drawn_by": "vector",
         "images": [], "note": "plus drawn with lines; opens a popup menu (menu items keep LibreOffice icons)"},
    ]


def inventory(trees, resolver):
    groups = {"backstage": backstage(trees, resolver), "sidebar": sidebar(trees, resolver),
              "statusbar": statusbar(trees, resolver), "doctabs": doctabs(trees)}
    elements = []
    for group, items in groups.items():
        for item in items:
            item = {"group": group, "owner_phase": OWNER[group], **item}
            item["needs"] = needs(item["images"], item["drawn_by"])
            if item["drawn_by"] == "none" and item["images"]:
                item["needs_if_given_an_icon"] = needs(item["images"], "command-icon")
            elements.append(item)
    counts = {}
    for element in elements:
        counts[element["needs"]] = counts.get(element["needs"], 0) + 1
    return {
        "comment": "Generated by scripts/brand/hst_icon_frame_inventory.py; do not edit. Frame elements with an "
                   "icon (menu items excluded: they keep the LibreOffice icons). needs: draw = no LibreOffice "
                   "icon, a new HST frame glyph; modern-only = Colibre draws it (the Cổ điển default keeps it), an "
                   "HST glyph only completes hst_modern; none = nothing to draw.",
        "counts": dict(sorted(counts.items())),
        "elements": elements,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--lo-tree", type=Path, required=True, help="pristine LibreOffice source tree")
    parser.add_argument("--patched-tree", type=Path, help="HST-patched tree (only the files the series touches)")
    parser.add_argument("--output", type=Path, default=OUTPUT)
    parser.add_argument("--check", action="store_true", help="fail when the committed inventory is stale")
    args = parser.parse_args()
    trees = Trees(args.lo_tree, args.patched_tree)
    data = inventory(trees, Resolver(args.lo_tree / "icon-themes"))
    text = json.dumps(data, indent=1, ensure_ascii=False) + "\n"
    if args.check:
        if not args.output.is_file() or args.output.read_text(encoding="utf-8") != text:
            sys.exit(f"{args.output} is stale; rerun without --check")
        print(f"{args.output}: up to date")
        return
    args.output.write_text(text, encoding="utf-8")
    print(f"{args.output}: {len(data['elements'])} elements, {data['counts']}")


if __name__ == "__main__":
    try:
        main()
    except ValueError as error:
        sys.exit(str(error))
