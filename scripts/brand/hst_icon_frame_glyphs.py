# SPDX-License-Identifier: LicenseRef-HST-Proprietary
# Copyright (C) 2026 HASON TECH
"""Which HST frame glyphs exist, at which sizes they are shown, and the Colibre icons beside them.

Two kinds of masters live under icon-themes-src/hst-modern/glyphs/stage-frame/:
  <name>.svg (+ 16/<name>.svg)   square 24-unit masters, shipped at the sizes of SIZES (default 16/24/32)
                                 by the pixel-snapping pipeline (hst_icon_frame_sheet.shipped);
  native/<name>.svg, native/<name>@150.svg, native/<name>@250.svg
                                 hand-tuned masters at the native pixel size of a LibreOffice frame image
                                 that is not a square 16/24/32 icon (status bar controls, sidebar chrome),
                                 shipped as drawn: VCL draws such images at their own size.
NEIGHBOURS lists, per glyph, 2-3 Colibre requests that stand beside it on the same surface (the first
is usually the Colibre icon the glyph replaces in the Hiện đại style); hst_icon_frame_compare measures
the glyph against them. NATIVE maps a native glyph to the LibreOffice image it draws.
"""
from pathlib import Path

STATUS = ["svx/res/zoom_page_statusbar", "svx/res/doc_modified_no"]
DECKS = ["cmd/sc_inspectordeck", "cmd/sc_showannotations"]

NEIGHBOURS = {
    # 16 px File tab and document tab glyphs
    "home": ["cmd/sc_adddirect", "cmd/sc_open", "cmd/sc_setdocumentproperties"],
    "saveas": ["cmd/sc_save", "cmd/sc_print", "cmd/sc_open"],
    "about": ["cmd/sc_about", "cmd/sc_optionstreedialog", "cmd/sc_closedoc"],
    "setupusbtoken": ["cmd/sc_signature", "cmd/sc_setdocumentproperties", "cmd/sc_versiondialog"],
    "previousversions": ["cmd/sc_signature", "cmd/sc_setdocumentproperties", "cmd/sc_versiondialog"],
    "unsaveddocuments": ["cmd/sc_signature", "cmd/sc_setdocumentproperties", "cmd/sc_versiondialog"],
    "toggleduplex": ["cmd/sc_print", "cmd/sc_printpreview", "cmd/sc_exporttopdf"],
    # the tab marks stand beside LibreOffice's own close-button marks (vcl/res/closedoc is the × of its
    # close buttons), not beside document icons
    "tabclose": ["vcl/res/closedoc", "cmd/sc_closewin", "cmd/sc_delete"],
    "tabnew": ["vcl/res/closedoc", "cmd/sc_closewin", "cmd/sc_delete"],
    # 24 px: the recent-documents pin and the sidebar tab bar
    "recent-pin": ["res/recentdoc_pin", "cmd/sc_open", "cmd/sc_adddirect"],
    "sidebar-property": ["cmd/sc_inspectordeck", "cmd/sc_basicshapes", "cmd/sc_showannotations"],
    "sidebar-style": ["cmd/sc_inspectordeck", "cmd/sc_basicshapes", "cmd/sc_showannotations"],
    "sidebar-navigator": ["cmd/sc_inspectordeck", "cmd/sc_basicshapes", "cmd/sc_showannotations"],
    "sidebar-inspector": ["cmd/sc_inspectordeck", "cmd/sc_basicshapes", "cmd/sc_showannotations"],
    "sidebar-a11y": ["sfx2/res/symphony/sidebar-a11y-large"] + DECKS,
    "sidebar-gallery": ["sfx2/res/symphony/sidebar-gallery-large"] + DECKS,
    "sidebar-template": ["sfx2/res/symphony/sidebar-template-large"] + DECKS,
    "sidebar-animation": ["sfx2/res/symphony/sidebar-animation-large"] + DECKS,
    "sidebar-transition": ["sfx2/res/symphony/sidebar-transition-large"] + DECKS,
    "sidebar-functions": ["sfx2/res/symphony/sidebar-functions-large"] + DECKS,
    "sidebar-trackchanges": ["cmd/sc_trackchangesbar"] + DECKS,
    "sidebar-design": ["cmd/sc_designerdialog"] + DECKS,
    "sidebar-elements": ["sfx2/res/symphony/sidebar-elements-large"] + DECKS,
    # 16 px status bar icons
    "signature-status": ["svx/res/doc_modified_no", "svx/res/zoom_page_statusbar",
                         "svx/res/a11y_check_issues_not_found"],
    "signature-broken": ["svx/res/caution_11x16"] + STATUS,
    "signature-notvalidated": ["svx/res/notcertificate_16"] + STATUS,
    "doc-modified-no": ["svx/res/doc_modified_no", "svx/res/zoom_page_statusbar",
                        "svx/res/a11y_check_issues_not_found"],
    "doc-modified-yes": ["svx/res/doc_modified_yes"] + STATUS,
    "doc-modified-feedback": ["svx/res/doc_modified_feedback"] + STATUS,
    "a11y-check-ok": ["svx/res/a11y_check_issues_not_found"] + STATUS,
    "a11y-check-issues": ["svx/res/a11y_check_issues_found"] + STATUS,
    # native-size masters: the image itself, then neighbours on the same bar
    "sidebar-menu": ["sfx2/res/menu", "sfx2/res/symphony/morebutton"],
    "deck-close": ["vcl/res/closedoc", "sfx2/res/symphony/morebutton"],
    "deck-grip": ["sfx2/res/grip", "sfx2/res/symphony/morebutton"],
    "selection-standard": ["svx/res/standard-selection", "svx/res/extending-selection"],
    "selection-extending": ["svx/res/extending-selection", "svx/res/standard-selection"],
    "selection-adding": ["svx/res/adding-selection", "svx/res/standard-selection"],
    "selection-block": ["svx/res/block-selection", "svx/res/standard-selection"],
    "position": ["res/sc10223", "res/sc10224"],
    "size": ["res/sc10224", "res/sc10223"],
    "viewlayout-single": ["sw/res/emptypage", "sw/res/twopages", "sw/res/doublepage"],
    "viewlayout-single-active": ["sw/res/emptypage_a", "sw/res/twopages_a", "sw/res/doublepage_a"],
    "viewlayout-auto": ["sw/res/twopages", "sw/res/emptypage", "sw/res/doublepage"],
    "viewlayout-auto-active": ["sw/res/twopages_a", "sw/res/emptypage_a", "sw/res/doublepage_a"],
    "viewlayout-book": ["sw/res/doublepage", "sw/res/twopages", "sw/res/emptypage"],
    "viewlayout-book-active": ["sw/res/doublepage_a", "sw/res/twopages_a", "sw/res/emptypage_a"],
    "zoom-out": ["svx/res/slidezoomout_10", "svx/res/slidezoomin_10", "svx/res/slidezoombutton_10"],
    "zoom-in": ["svx/res/slidezoomin_10", "svx/res/slidezoomout_10", "svx/res/slidezoombutton_10"],
    "zoom-thumb": ["svx/res/slidezoombutton_10", "svx/res/slidezoomin_10", "svx/res/slidezoomout_10"],
    "zoom-page": ["svx/res/zoom_page_statusbar", "svx/res/doc_modified_no"],
}
# Native glyph -> the LibreOffice image request it draws (its pixel size is that image's).
NATIVE = {
    "sidebar-menu": "sfx2/res/menu", "deck-close": "sfx2/res/closedoc", "deck-grip": "sfx2/res/grip",
    "selection-standard": "svx/res/standard-selection", "selection-extending": "svx/res/extending-selection",
    "selection-adding": "svx/res/adding-selection", "selection-block": "svx/res/block-selection",
    "position": "res/sc10223", "size": "res/sc10224",
    "viewlayout-single": "sw/res/emptypage", "viewlayout-single-active": "sw/res/emptypage_a",
    "viewlayout-auto": "sw/res/twopages", "viewlayout-auto-active": "sw/res/twopages_a",
    "viewlayout-book": "sw/res/doublepage", "viewlayout-book-active": "sw/res/doublepage_a",
    "zoom-out": "svx/res/slidezoomout_10", "zoom-in": "svx/res/slidezoomin_10",
    "zoom-thumb": "svx/res/slidezoombutton_10", "zoom-page": "svx/res/zoom_page_statusbar",
}
# Square glyphs not shown at all of 16/24/32 px.
SIZES = {"recent-pin": (24,), "signature-broken": (16,), "signature-notvalidated": (16,),
         "doc-modified-no": (16,), "doc-modified-yes": (16,), "doc-modified-feedback": (16,),
         "a11y-check-ok": (16,), "a11y-check-issues": (16,), "about": (16,)}
# Glyphs shown at 16 px whose 16 px file is snapped from the 24-unit master instead of a hand-tuned one.
SNAPPED_AT_16 = set()


def sizes_of(name):
    if name in SIZES:
        return SIZES[name]
    return (24, 32) if name.startswith("sidebar-") else (16, 24, 32)


def square_masters(stage):
    return sorted(p.stem for p in Path(stage).glob("*.svg"))


def native_masters(stage):
    return sorted(p.stem for p in (Path(stage) / "native").glob("*.svg") if "@" not in p.stem)
