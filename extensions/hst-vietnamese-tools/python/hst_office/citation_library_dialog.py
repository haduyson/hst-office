# SPDX-License-Identifier: AGPL-3.0-only
""""Quản lý tài liệu tham khảo": the user's library (<profile>/hst-citations/library.json, never sent anywhere).
Search (accents and case ignored), sort by author, year, title or newest, add and edit sources in the source form
(with online lookup), delete, import files, export, and copy the sources this document cites into the library."""
from . import citation_lists as lists
from . import citation_ui as ui
from .dialogs import Dialog

W, H = 400, 290


def sort_items(items, key_index):
    """Items for the list: by first author (Vietnamese by given name), year, title, or newest first."""
    from .citation_model import modified, year
    from .citation_names import collation_key, name_sort_key

    def author(item):
        names = item.get("author") or item.get("editor") or []
        return (name_sort_key(names[0]) if names else collation_key(item.get("title", "")), year(item) or 0)
    keys = (author, lambda i: (year(i) or 0, collation_key(i.get("title", ""))),
            lambda i: collation_key(i.get("title", "")))
    if key_index == 3:
        return sorted(items, key=modified, reverse=True)
    return sorted(items, key=keys[max(0, key_index)])


def run(ctx, peer, texts, doc_items, style, language=None):
    from . import citation_transfer_actions as transfer
    from .citation_entry_dialog import run as entry
    t = texts["library"]
    library = ui.open_library(ctx, peer, texts)
    shown = []
    dialog = Dialog(ctx, t["title"], W, H)
    dialog.label("lSearch", t["search"], 8, 10, 30)
    dialog.edit("search", 40, 8, 220, help_text=t["search"])
    dialog.label("lSort", t["sort"], 268, 10, 44)
    dialog.listbox("sort", 312, 8, W - 320, t["sortKeys"], 0, help_text=t["sort"])
    lists.multi_list(dialog, "list", 8, 26, W - 16, 190, t["title"])
    dialog.label("count", "", 8, 220, W - 16)
    buttons = (("add", t["add"], lambda: add()), ("edit", t["edit"], lambda: edit()),
               ("delete", t["delete"], lambda: delete()), ("import", t["import"], lambda: do_import()),
               ("export", t["export"], lambda: do_export()), ("fromDoc", t["fromDocument"], lambda: from_document()))
    for index, (name, label, callback) in enumerate(buttons):
        dialog.button(name, label, 8 + (index % 3) * 130, 234 + (index // 3) * 18, 124, callback=callback)
    dialog.button("close", texts["common"]["close"], W - 80, H - 20, 72, kind=1, default=True)

    def peer_now():
        return dialog.dialog.getPeer()

    def refill():
        text = dialog.get("search")
        pool = library.search(text, limit=lists.MAX_ROWS * 4) if text.strip() else library.items
        found, hidden = lists.filter_items(sort_items(pool, dialog.get("sort")), "", ui.short_label)
        shown[:] = found
        lists.set_rows(dialog, "list", [ui.short_label(i) for i in found])
        count = t["count"] % len(library)
        dialog.set_text("count", count + ("  " + texts["insert"]["more"] % hidden if hidden else ""))
        dialog.model.getByName("fromDoc").Enabled = bool(doc_items) and not library.read_only
        for name in ("add", "edit", "delete", "import"):
            dialog.model.getByName(name).Enabled = not library.read_only

    def selected():
        return [shown[r] for r in lists.selected_rows(dialog, "list")]

    def add():
        if entry(ctx, peer_now(), texts, None, library, style, language=language) is not None:
            refill()

    def edit():
        items = selected()
        if items and entry(ctx, peer_now(), texts, items[0], library, style, language=language) is not None:
            refill()

    def delete():
        items = selected()
        if items and ui.ask(ctx, peer_now(), texts, t["confirmDelete"] % len(items)):
            library.remove([i["id"] for i in items])
            if ui.save_library(ctx, peer_now(), texts, library):
                ui.inform(ctx, peer_now(), texts, texts["done"]["deleted"] % len(items))
            refill()

    def do_import():
        if transfer.import_into(ctx, peer_now(), texts, library):
            refill()

    def do_export():
        transfer.export(ctx, peer_now(), texts, [selected(), library.items, list(doc_items.values())])

    def from_document():
        added, duplicates = library.add(list(doc_items.values()))
        for item, existing_id in duplicates:  # the library's own values win; missing fields are filled in
            library.merge(existing_id, item)
        if ui.save_library(ctx, peer_now(), texts, library):
            ui.inform(ctx, peer_now(), texts, texts["done"]["addedFromDocument"] % len(added))
        refill()

    dialog.on_change(["search", "sort"], refill)
    dialog.on_ready = refill
    if library.read_only:
        dialog.on_ready = lambda: (refill(), ui.inform(ctx, peer_now(), texts, texts["blockers"]["libraryReadOnly"]))
    dialog.execute(peer)
