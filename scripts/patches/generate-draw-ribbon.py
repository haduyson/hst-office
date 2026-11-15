#!/usr/bin/env python3
# SPDX-License-Identifier: AGPL-3.0-only
"""Generate the HST ribbon of HST Draw (patches/libreoffice/hst-ribbon-draw.patch).

Usage: scripts/patches/generate-draw-ribbon.py --tree DIR [--out PATCH] [--check]

DIR is a LibreOffice tree with the whole series applied (scripts/apply-patches.sh on the 26.8.1.1
tarballs, as the fresh-tree check builds it). HST Draw is what "Chỉnh sửa bằng HST Draw" of HST PDF
opens, so its ribbon is the Slides ribbon (Draw and Slides share the sd code and their commands) with
the slide-only tabs and groups left out and three tabs for editing PDFs:

  Tệp tin, Trang đầu, Chèn, Sắp xếp, Trang, Xuất/PDF, Xem lại, Xem, Trợ giúp, Phần mở rộng, then the
  contextual tabs. No tab has the right-hand "<tab> ▾" block, except Phần mở rộng's extension menus.

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
import os
import sys
import xml.etree.ElementTree as ET

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
# the generator's parts, re-exported for its tests
from draw_ribbon_data import *  # noqa: E402,F401,F403
from draw_ribbon_files import file_diff, po, po_entry, suppr, toolbar_mode, PO_ANCHOR  # noqa: E402,F401
from draw_ribbon_layout import (caption_of, claim_ids, drop_tab_blocks, group, hst_group_look,  # noqa: E402,F401
                                order_by_position, place_groups, tool_button)
from draw_ribbon_xml import (check_unique, child_of, find, ids, keep_groups, merged_box, new_tab,  # noqa: E402,F401
                             parent_map, parse, remove_child, remove_commands, rename_ids, serialize, set_label,
                             swap_commands, tab_label, tab_pages)


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
    drop_tab_blocks(impress)
    place_groups(impress, ids(impress))
    order_by_position(impress)
    master_page = find(impress, MASTER_PAGE_GROUP)
    set_label(caption_of(master_page), *STRINGS[4][:2])
    set_label(caption_of(find(impress, ARRANGE_ROTATE_GROUP)), *STRINGS[10][:2])
    set_label(caption_of(find(impress, INSERT_MEDIA_GROUP)), *STRINGS[11][:2])
    hst_group_look(impress)
    check_unique(impress)
    return impress



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
