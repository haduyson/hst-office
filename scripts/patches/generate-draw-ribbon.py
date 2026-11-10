#!/usr/bin/env python3
# SPDX-License-Identifier: AGPL-3.0-only
"""Generate the HST ribbon of HST Draw (patches/libreoffice/hst-ribbon-draw.patch).

Usage: scripts/patches/generate-draw-ribbon.py --tree DIR [--out PATCH] [--check]

DIR is a LibreOffice tree with the whole series applied (scripts/apply-patches.sh on the 26.8.1.1
tarballs, as the fresh-tree check builds it). HST Draw is what "Chỉnh sửa bằng HST Draw" of HST PDF
opens, so its ribbon is the Slides ribbon (Draw and Slides share the sd code and their commands) with
the slide-only tabs and groups left out and three tabs for editing PDFs:

  Tệp tin, Trang đầu, Chèn, Sắp xếp, Trang, Xem, Xuất/PDF, Xem lại, the contextual tabs, Trợ giúp,
  Phần mở rộng.

- Trang đầu, Chèn, Xem, Xem lại and the contextual tabs are the Slides tabs of the tree (their strings
  keep the TabbedImpress context, so the Vietnamese of sd/messages.po and l10n/ applies unchanged),
  without the slide-only groups and commands named below.
- Sắp xếp copies the arrange groups of the Shape Format tab; Trang takes the page groups of Draw's own
  Layout tab; Xem uses Draw's own view modes and Draw's page pane; Xuất/PDF is new.
- Copies get their own ids (GtkBuilder ids are unique per file), and every reference to them follows.

The patch replaces sd/uiconfig/sdraw/ui/notebookbar.ui, regenerates the button-no-label lines of
solenv/sanitizers/ui/modules/sdraw.suppr for it, makes the ribbon Draw's active UI mode (as
hst-defaults.patch does for the other three apps) and adds the Vietnamese of the new strings to
translations/source/vi/sd/messages.po, where the tarball and an l10n-filled tree agree (PO_ANCHOR).
The output is byte-stable; --check only compares it with the existing patch.
"""
import argparse
import copy
import difflib
import os
import sys
import xml.etree.ElementTree as ET

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
IMPRESS_UI = "sd/uiconfig/simpress/ui/notebookbar.ui"
DRAW_UI = "sd/uiconfig/sdraw/ui/notebookbar.ui"
DRAW_SUPPR = "solenv/sanitizers/ui/modules/sdraw.suppr"
IMPRESS_SUPPR = "solenv/sanitizers/ui/modules/simpress.suppr"
TOOLBAR_MODE = "officecfg/registry/data/org/openoffice/Office/UI/ToolbarMode.xcu"
VI_PO = "translations/source/vi/sd/messages.po"
OPEN_IN_HST_PDF = "org.hst.office.vi:OpenInHstPdf"

# Tab pages in Draw's order: the Slides tabs and the new Arrange, Page and Export.
TAB_ORDER = ["File", "Home Tab", "Insert", "Arrange", "Page", "View", "Export", "Review", "TableDesign",
             "Table", "Image", "ChartDesign", "ChartFormat", "Draw", "Object", "Media", "Form", "Master",
             "3D", "Help Tab", "Extension"]
# Slides-only groups and commands (slides, layouts, transitions, header and footer, interaction).
DROP_GROUPS = {"gdHomeSlide", "gdInsertSlide", "gdViewMode", "gdViewMaster"}
# Draw has no slot for hiding a page: HidePage/ShowPage of its own Layout tab never worked.
DROP_COMMANDS = {".uno:PhotoAlbumDialog", ".uno:AnimationEffects", ".uno:HeaderAndFooter", ".uno:SlideChangeWindow",
                 ".uno:PresentationCurrentSlide", ".uno:HideSlide", ".uno:ShowSlide", ".uno:HidePage", ".uno:ShowPage"}
# Slide commands of the Slides menus and groups, as Draw names them for pages.
SWAP_COMMANDS = {".uno:LeftPaneImpress": ".uno:LeftPaneDraw", ".uno:InsertSlide": ".uno:InsertPage",
                 ".uno:DuplicateSlide": ".uno:DuplicatePage", ".uno:DeleteSlide": ".uno:DeletePage",
                 ".uno:RenameSlide": ".uno:RenamePage", ".uno:MoveSlideUp": ".uno:MovePageUp",
                 ".uno:MoveSlideDown": ".uno:MovePageDown", ".uno:SlideSetup": ".uno:PageSetup",
                 ".uno:SlideMasterPage": ".uno:MasterPage", ".uno:InsertSlideField": ".uno:InsertPageField",
                 ".uno:InsertSlidesField": ".uno:InsertPagesField", ".uno:ImportSlideFromFile": ".uno:ImportFromFile",
                 ".uno:InsertSlideTitleField": ".uno:InsertPageTitleField"}
# Sắp xếp: the arrange groups of Shape Format, in Office's order (arrange and align, group, rotate).
ARRANGE_GROUPS = ["gdDrawPositioning", "gdDrawGrouping", "gdDraw", "gdDrawCombination"]
ARRANGE_DROP_COMMANDS = {".uno:FontworkGalleryFloater"}
# Trang: Draw's page groups (pages first, then page setup and background).
PAGE_GROUPS = [("gdHomePage", "gdPagePages"), ("gdLayoutFormat", "gdPageSetup"), ("gdLayoutPage", "gdPageOrder")]
PAGE_DROP_COMMANDS = {".uno:DrawingLayout"}

# New strings: (msgctxt, English msgid, Vietnamese msgstr).
STRINGS = [
    ("TabbedDraw|ArrangeTabLabel", "~Arrange", "~Sắp xếp"),
    ("TabbedDraw|PageTabLabel", "~Page", "Tra~ng"),
    ("TabbedDraw|ExportTabLabel", "Export/~PDF", "Xuất/P~DF"),
    ("TabbedDraw|labelPagePages", "Pages", "Trang"),
    ("TabbedDraw|labelPageSetup", "Page Setup", "Thiết lập trang"),
    ("TabbedDraw|labelPageOrder", "Order", "Thứ tự"),
    ("TabbedDraw|labelExportPdf", "PDF", "PDF"),
    ("TabbedDraw|labelExportSign", "Sign", "Ký số"),
    ("TabbedDraw|labelExportHstPdf", "HST PDF", "HST PDF"),
]
BUTTON_CLASSES = ("GtkToolButton", "GtkMenuToolButton", "GtkToggleToolButton", "GtkMenuItem", "GtkRadioMenuItem",
                  "GtkCheckMenuItem")


class DrawRibbonError(Exception):
    pass


def parse(path):
    parser = ET.XMLParser(target=ET.TreeBuilder(insert_comments=True))
    return ET.parse(path, parser=parser).getroot()


def find(root, oid):
    for o in root.iter("object"):
        if o.get("id") == oid:
            return o
    raise DrawRibbonError(f"no object {oid!r}")


def parent_map(root):
    return {child: parent for parent in root.iter() for child in parent}


def child_of(parents, obj):
    """The <child> element that holds obj."""
    holder = parents[obj]
    if holder.tag != "child":
        raise DrawRibbonError(f"{obj.get('id')!r} is not held by a <child>")
    return holder


def ids(root):
    return {o.get("id") for o in root.iter("object") if o.get("id")}


def remove_child(root, obj):
    parents = parent_map(root)
    holder = child_of(parents, obj)
    parents[holder].remove(holder)


def remove_commands(root, commands):
    """Remove the buttons of these commands, and toolboxes that end up empty."""
    for _ in range(2):  # the second pass removes the toolboxes the first one emptied
        parents = parent_map(root)
        for obj in list(root.iter("object")):
            action = next((p.text for p in obj.findall("property") if p.get("name") == "action-name"), None)
            empty_box = obj.get("class") == "sfxlo-NotebookbarToolBox" and not obj.findall("child")
            if action in commands or empty_box:
                holder = parents.get(obj)
                if holder is not None and holder.tag == "child" and holder in parents:
                    parents[holder].remove(holder)


def swap_commands(root, swaps):
    for prop in root.iter("property"):
        if prop.get("name") == "action-name" and prop.text in swaps:
            prop.text = swaps[prop.text]


def rename_ids(element, rename, taken):
    """Give every object of the copy a new id; references inside the copy follow."""
    mapping = {}
    for obj in element.iter("object"):
        old = obj.get("id")
        if not old:
            continue
        name, colon, menu = old.partition(":")  # "button:Menu X" names the menu the button opens
        new = rename(name)
        while new + colon + menu in taken or new + colon + menu in mapping.values():
            new += "X"
        mapping[old] = new + colon + menu
        obj.set("id", mapping[old])
    for node in element.iter():
        for attribute in ("target",):
            if node.get(attribute) in mapping:
                node.set(attribute, mapping[node.get(attribute)])
        if node.tag == "property" and node.text in mapping:
            node.text = mapping[node.text]
    taken.update(mapping.values())
    return mapping


def set_label(label, context, text):
    for prop in label.findall("property"):
        if prop.get("name") == "label":
            prop.set("context", context)
            prop.set("translatable", "yes")
            prop.text = text
            return
    raise DrawRibbonError(f"label {label.get('id')!r} has no text")


def merged_box(page):
    boxes = [o for o in page.iter("object") if o.get("class") == "sfxlo-PriorityMergedHBox"]
    if not boxes:
        raise DrawRibbonError(f"tab page {page.get('id')!r} has no merged group box")
    return boxes[0]


def keep_groups(box, wanted):
    """Keep exactly these groups of a merged box, in this order."""
    holders = {c.find("object").get("id"): c for c in box.findall("child") if c.find("object") is not None}
    missing = [g for g in wanted if g not in holders]
    if missing:
        raise DrawRibbonError(f"{box.get('id')!r} lacks {missing}")
    for child in box.findall("child"):  # the box's own properties (visible, valign) stay
        box.remove(child)
    for gid in wanted:
        box.append(holders[gid])


def tab_pages(container):
    """[(page id, page <child>, tab <child>)] of the tab control."""
    kids = [c for c in container if c.tag == "child"]
    pages = []
    for i, child in enumerate(kids):
        if child.get("type") == "tab":
            continue
        tab = kids[i + 1] if i + 1 < len(kids) and kids[i + 1].get("type") == "tab" else None
        if tab is None:
            raise DrawRibbonError(f"tab page {child.find('object').get('id')!r} has no tab label")
        pages.append((child.find("object").get("id"), child, tab))
    return pages


def tab_label(tab):
    return next(o for o in tab.iter("object") if o.get("class") == "GtkLabel")


def new_tab(template, label_id, context, text, taken):
    """A tab label like Insert's: shown in every context, never the one selected for a context."""
    tab = copy.deepcopy(template)
    label = tab_label(tab)
    if label_id in taken:
        raise DrawRibbonError(f"tab label id {label_id!r} is taken")
    label.set("id", label_id)
    taken.add(label_id)
    set_label(label, context, text)
    return tab


def tool_button(bid, command, big):
    """A toolbox holding one button: big (icon over caption, two rows) or small (icon and caption)."""
    box = ET.Element("object", {"class": "sfxlo-NotebookbarToolBox", "id": "bx" + bid[3:]})
    for name, value in (("visible", "True"), ("can-focus", "False")):
        ET.SubElement(box, "property", {"name": name}).text = value
    if big:
        for name, value in (("valign", "center"), ("vexpand", "True"), ("toolbar-style", "both"),
                            ("show-arrow", "False"), ("icon_size", "3")):
            ET.SubElement(box, "property", {"name": name}).text = value
    else:
        for name, value in (("toolbar-style", "both-horiz"), ("show-arrow", "False")):
            ET.SubElement(box, "property", {"name": name}).text = value
    holder = ET.SubElement(box, "child")
    button = ET.SubElement(holder, "object", {"class": "GtkToolButton", "id": bid})
    props = [("visible", "True"), ("can-focus", "False")]
    if command == OPEN_IN_HST_PDF:  # an extension command: its caption, tip and icon are given here
        props += [("label", "Mở trong\nHST PDF" if big else "Mở trong HST PDF"),
                  ("tooltip-text", "Mở bản PDF của bản vẽ trong HST PDF để xem và ký số"),
                  ("action-name", command), ("icon-name", "cmd/32/openinhstpdf.png" if big else "cmd/sc_openinhstpdf.png")]
    else:
        props += [("action-name", command), ("use-underline", "True")]
    for name, value in props:
        ET.SubElement(button, "property", {"name": name}).text = value
    packing = ET.SubElement(holder, "packing")
    ET.SubElement(packing, "property", {"name": "expand"}).text = "False"
    ET.SubElement(packing, "property", {"name": "homogeneous"}).text = "True"
    return box


def group(gid, label_id, context, caption, big, smalls):
    """A captioned group: one big button, small buttons in a column beside it, its caption below."""
    grid = ET.Element("object", {"class": "GtkGrid", "id": gid})
    for name, value in (("visible", "True"), ("can-focus", "False"), ("margin-start", "3"), ("margin-end", "6"),
                        ("margin-top", "6"), ("margin-bottom", "6"), ("row-spacing", "3"), ("column-spacing", "3")):
        ET.SubElement(grid, "property", {"name": name}).text = value

    def place(obj, left, top, width=1, height=1):
        holder = ET.SubElement(grid, "child")
        holder.append(obj)
        packing = ET.SubElement(holder, "packing")
        for name, value in (("left-attach", left), ("top-attach", top), ("width", width), ("height", height)):
            if name in ("left-attach", "top-attach") or value != 1:
                ET.SubElement(packing, "property", {"name": name}).text = str(value)

    command, bid = big
    place(tool_button(bid, command, True), 0, 0, height=2)
    columns = 1
    for i, (command, bid) in enumerate(smalls):
        place(tool_button(bid, command, False), 1 + i // 2, i % 2)
        columns = max(columns, 2 + i // 2)
    separator = ET.Element("object", {"class": "GtkSeparator"})
    for name, value in (("visible", "True"), ("can-focus", "False"), ("orientation", "vertical")):
        ET.SubElement(separator, "property", {"name": name}).text = value
    place(separator, columns, 0, height=3)
    label = ET.Element("object", {"class": "GtkLabel", "id": label_id})
    for name, value in (("visible", "True"), ("can-focus", "False"), ("valign", "end"), ("vexpand", "True")):
        ET.SubElement(label, "property", {"name": name}).text = value
    ET.SubElement(label, "property", {"name": "label", "translatable": "yes", "context": context}).text = caption
    attributes = ET.SubElement(label, "attributes")
    ET.SubElement(attributes, "attribute", {"name": "style", "value": "italic"})
    ET.SubElement(attributes, "attribute", {"name": "scale", "value": "0.9"})
    ET.SubElement(ET.SubElement(label, "accessibility"), "relation", {"type": "label-for", "target": gid})
    place(label, 0, 2, width=columns + 1)
    ET.SubElement(ET.SubElement(grid, "accessibility"), "relation", {"type": "labelled-by", "target": label_id})
    return grid


def build_ui(tree):
    impress = parse(os.path.join(tree, IMPRESS_UI))
    draw = parse(os.path.join(tree, DRAW_UI))
    container = find(impress, "ContextContainer")
    pages = {pid: (page, tab) for pid, page, tab in tab_pages(container)}
    draw_pages = {pid: (page, tab) for pid, page, tab in tab_pages(find(draw, "ContextContainer"))}
    taken = ids(impress)
    insert_tab = pages["Insert"][1]

    # Sắp xếp: the arrange groups of Shape Format.
    arrange_page = copy.deepcopy(pages["Draw"][0])
    rename_ids(arrange_page, lambda old: old.replace("Draw", "Arrange", 1) if "Draw" in old else old + "Arrange", taken)
    arrange_page.find("object").set("id", "Arrange")
    box = merged_box(arrange_page)
    box.set("id", "pmhbArrange")
    keep_groups(box, [g.replace("Draw", "Arrange", 1) for g in ARRANGE_GROUPS])
    remove_commands(arrange_page, ARRANGE_DROP_COMMANDS)
    arrange_tab = new_tab(insert_tab, "ArrangeLabel", *STRINGS[0][:2], taken)

    # Trang: Draw's page groups, in a copy of Draw's Layout tab page.
    page_page = copy.deepcopy(draw_pages["Layout"][0])
    page_box = merged_box(page_page)
    home_page_group = next(c for c in merged_box(draw_pages["Home"][0]).findall("child")
                           if c.find("object").get("id") == "gdHomePage")
    page_box.append(copy.deepcopy(home_page_group))
    keep_groups(page_box, [old for old, _new in PAGE_GROUPS])
    renames = dict(PAGE_GROUPS)
    rename_ids(page_page, lambda old: renames.get(old, old if old not in taken else old + "Page"), taken)
    page_page.find("object").set("id", "Page")
    page_box.set("id", "pmhbPage")
    remove_commands(page_page, PAGE_DROP_COMMANDS)
    for (_old, new), (context, msgid, _vi) in zip(PAGE_GROUPS, STRINGS[3:6]):
        grid = find(page_page, new)
        caption = next(o for o in grid.iter("object") if o.get("class") == "GtkLabel")
        set_label(caption, context, msgid)
    page_tab = new_tab(insert_tab, "LayoutLabel", *STRINGS[1][:2], taken)

    # Xem: Draw's own view modes in place of the slide modes.
    view_box = merged_box(pages["View"][0])
    draw_view_mode = copy.deepcopy(next(c for c in merged_box(draw_pages["View"][0]).findall("child")
                                        if c.find("object").get("id") == "gdViewMode"))

    # Xuất/PDF: a new tab from a copy of the File tab page.
    export_page = copy.deepcopy(pages["File"][0])
    export_box = merged_box(export_page)
    for child in export_box.findall("child"):
        export_box.remove(child)
    rename_ids(export_page, lambda old: old.replace("File", "Export", 1) if "File" in old else old + "Export", taken)
    export_page.find("object").set("id", "Export")
    export_box.set("id", "pmhbExport")
    for grid in (group("gdExportPdf", "lbExportPdf", *STRINGS[6][:2], (".uno:ExportToPDF", "btnExportToPDF"),
                       [(".uno:ExportDirectToPDF", "btnExportDirectToPDF"), (".uno:ExportTo", "btnExportExportTo")]),
                 group("gdExportSign", "lbExportSign", *STRINGS[7][:2], (".uno:SignPDF", "btnExportSignPDF"),
                       [(".uno:Signature", "btnExportSignature")]),
                 group("gdExportHstPdf", "lbExportHstPdf", *STRINGS[8][:2], (OPEN_IN_HST_PDF, "btnExportOpenInHstPdf"),
                       [])):
        for oid in [o.get("id") for o in grid.iter("object") if o.get("id")]:
            if oid in taken:
                raise DrawRibbonError(f"new id {oid!r} is taken")
            taken.add(oid)
        holder = ET.SubElement(export_box, "child")
        holder.append(grid)
    export_tab = new_tab(insert_tab, "ExportLabel", *STRINGS[2][:2], taken)

    # Assemble the tab control in Draw's order.
    for child in list(container):
        if child.tag == "child":
            container.remove(child)
    new_pages = {"Arrange": (arrange_page, arrange_tab), "Page": (page_page, page_tab),
                 "Export": (export_page, export_tab)}
    for pid in TAB_ORDER:
        page, tab = new_pages.get(pid) or pages[pid]
        container.append(page)
        container.append(tab)
    for pid in pages:
        if pid not in TAB_ORDER and pid not in ("Design", "Transitions", "Animations", "SlideShow", "Outline"):
            raise DrawRibbonError(f"Slides tab {pid!r} has no place in Draw's ribbon")

    for gid in DROP_GROUPS:
        remove_child(impress, find(impress, gid))
    # Draw's view modes take the first place of the View tab; their ids are free once the slide modes left.
    taken = ids(impress)
    rename_ids(draw_view_mode, lambda old: old if old not in taken else old + "Draw", taken)
    # before the first group, after the box's properties: VclBuilder makes the widget at its first child
    view_box.insert(list(view_box).index(view_box.find("child")), draw_view_mode)

    # Objects the copied Draw groups refer to (menus, images) come along when Slides lacks them.
    top = {o.get("id"): o for o in draw.findall("object")}
    present = {o.get("id") for o in impress.findall("object")}
    wanted = [p.text for p in impress.iter("property")]
    wanted += [o.get("id").partition(":")[2] for o in impress.iter("object") if ":" in (o.get("id") or "")]
    taken = ids(impress)
    for ref in wanted:
        if ref in top and ref not in present:
            menu = copy.deepcopy(top[ref])
            rename_ids(menu, lambda old: old if old not in taken else old + "Draw", taken)
            menu.set("id", ref)
            impress.insert(len(impress) - 1, menu)
            present.add(ref)
    remove_commands(impress, DROP_COMMANDS)
    swap_commands(impress, SWAP_COMMANDS)
    check_unique(impress)
    return impress


def check_unique(root):
    seen = set()
    for obj in root.iter("object"):
        oid = obj.get("id")
        if oid and oid in seen:
            raise DrawRibbonError(f"duplicate id {oid!r}")
        seen.add(oid)
    for node in root.iter("relation"):
        if node.get("target") not in seen:
            raise DrawRibbonError(f"relation to a missing object {node.get('target')!r}")
    for obj in root.iter("object"):  # VclBuilder makes a widget at its first child: later properties are lost
        kinds = [c.tag for c in obj if c.tag in ("property", "child")]
        if "child" in kinds and "property" in kinds[kinds.index("child"):]:
            raise DrawRibbonError(f"{obj.get('id')!r} has a property after a child")


def serialize(root):
    ET.indent(root, space="  ")
    text = ET.tostring(root, encoding="unicode")
    head = ('<?xml version="1.0" encoding="UTF-8"?>\n'
            "<!-- HST Office: HST Draw ribbon, generated by scripts/patches/generate-draw-ribbon.py -->\n")
    return head + text + "\n"


def suppr(tree, ui_text):
    """sdraw.suppr: other files' lines as they are, this file's lines for its unlabelled buttons."""
    root = ET.fromstring(ui_text)
    lines = []
    for obj in root.iter("object"):
        if obj.get("class") in BUTTON_CLASSES and obj.get("id") \
                and not any(p.get("name") == "label" for p in obj.findall("property")):
            lines.append(f"{DRAW_UI}://{obj.get('class')}[@id='{obj.get('id')}'] button-no-label\n")
    with open(os.path.join(tree, DRAW_SUPPR), encoding="utf-8") as handle:
        old = handle.readlines()
    first = next(i for i, line in enumerate(old) if line.startswith(DRAW_UI + ":"))
    rest = [line for line in old if not line.startswith(DRAW_UI + ":")]
    return "".join(rest[:first] + lines + rest[first:])


def toolbar_mode(tree):
    with open(os.path.join(tree, TOOLBAR_MODE), encoding="utf-8") as handle:
        text = handle.read()
    old = '    <node oor:name="Draw" oor:op="replace">\n      <prop oor:name="Active">\n        <value>Default</value>'
    if text.count(old) != 1:
        raise DrawRibbonError("ToolbarMode.xcu: Draw's active mode is not the tarball's")
    text = text.replace(old, old.replace("Default", "notebookbar.ui"))
    # Draw's Tabbed mode keeps the menu bar upstream; the other apps' Tabbed modes have none
    draw = text.index('    <node oor:name="Draw" oor:op="replace">')
    tabbed = text.index('        <node oor:name="Tabbed" oor:op="replace">', draw)
    end = text.index("\n        </node>", tabbed)
    menubar = '          <prop oor:name="HasMenubar">\n            <value>true</value>'
    at = text.find(menubar, tabbed, end)
    if at < 0:
        raise DrawRibbonError("ToolbarMode.xcu: Draw's Tabbed mode has no menu bar setting to turn off")
    return text[:at] + menubar.replace("true", "false") + text[at + len(menubar):]


def po_entry(context, msgid, msgstr):
    return (f'#. hstDR\n#: {DRAW_UI}\nmsgctxt "{context}"\nmsgid "{msgid}"\nmsgstr "{msgstr}"\n\n')


# The new strings go before this entry: it and the eight lines around it are the same in the tarball's
# sd/messages.po and in a tree whose Vietnamese l10n/ already filled (the TabbedDraw entries are not).
PO_ANCHOR = 'msgctxt "insertslidesdialog|links"'


def po(tree):
    """New entries before PO_ANCHOR's entry of sd/messages.po."""
    with open(os.path.join(tree, VI_PO), encoding="utf-8") as handle:
        text = handle.read()
    at = text.find(PO_ANCHOR)
    start = text.rfind("\n\n", 0, at) + 2 if at >= 0 else -1
    if at < 0 or text.count(PO_ANCHOR) != 1 or not text.startswith("#. ", start):
        raise DrawRibbonError("sd/messages.po: the anchor entry for the new strings is missing")
    entries = "".join(po_entry(*s) for s in STRINGS)
    return text[:start] + entries + text[start:]


def file_diff(tree, path, new, context):
    with open(os.path.join(tree, path), encoding="utf-8") as handle:
        old = handle.read()
    lines = list(difflib.unified_diff(old.splitlines(keepends=True), new.splitlines(keepends=True),
                                      fromfile=f"a/{path}", tofile=f"b/{path}", n=context))
    if not lines:
        raise DrawRibbonError(f"{path}: no change")
    return "".join(lines)


DESCRIPTION = """HST Office: HST Draw gets the HST ribbon, like Writer, Sheets and Slides (generated).

HST Draw is what "Chỉnh sửa bằng HST Draw" of HST PDF opens, so its ribbon is laid out for editing PDFs:
Tệp tin, Trang đầu, Chèn, Sắp xếp, Trang, Xem, Xuất/PDF, Xem lại, the contextual tabs, Trợ giúp and
Phần mở rộng. Generated by scripts/patches/generate-draw-ribbon.py from the Slides ribbon of the series
(Draw and Slides share the sd code): the slide-only tabs (Thiết kế, Chuyển tiếp, Hoạt hình, Trình chiếu,
Dàn ý), groups and commands are left out; Sắp xếp copies the arrange groups of Shape Format; Trang takes
Draw's own page groups; Xem uses Draw's view modes and page pane; Xuất/PDF holds Export as PDF, the PDF
signature and "Mở trong HST PDF" (org.hst.office.vi:OpenInHstPdf, hst-vietnamese-tools). The whole HST
engine (ladders, compact banner, tab search, keytips, launchers, accessibility groups) applies as is.

- sd/uiconfig/sdraw/ui/notebookbar.ui: the new ribbon; solenv sdraw.suppr: its unlabelled buttons take
  their accessible name from their command.
- ToolbarMode.xcu: the ribbon is Draw's active UI mode, as hst-defaults.patch sets it for the other apps, and
  without the menu bar that upstream keeps in Draw's Tabbed mode only.
- translations/source/vi/sd/messages.po: the new strings.

License: these upstream files remain under their original license (MPL-2.0).
---
"""


def patch_text(tree):
    ui = serialize(build_ui(tree))
    return (DESCRIPTION
            + file_diff(tree, DRAW_UI, ui, 8)
            + file_diff(tree, DRAW_SUPPR, suppr(tree, ui), 8)
            + file_diff(tree, TOOLBAR_MODE, toolbar_mode(tree), 8)
            + file_diff(tree, VI_PO, po(tree), 8))


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--tree", required=True)
    parser.add_argument("--out", default=os.path.join(ROOT, "patches/libreoffice/hst-ribbon-draw.patch"))
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    try:
        text = patch_text(args.tree)
    except (DrawRibbonError, OSError, StopIteration, KeyError) as error:
        print(f"cannot generate the Draw ribbon: {error!r}", file=sys.stderr)
        return 2
    if args.check:
        current = open(args.out, encoding="utf-8").read() if os.path.exists(args.out) else ""
        if current != text:
            print(f"{os.path.relpath(args.out, ROOT)} is out of date", file=sys.stderr)
            return 1
        print("up to date")
        return 0
    with open(args.out, "w", encoding="utf-8") as handle:
        handle.write(text)
    print(f"wrote {os.path.relpath(args.out, ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
