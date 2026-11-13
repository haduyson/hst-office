# SPDX-License-Identifier: AGPL-3.0-only
"""The "Chèn trích dẫn" dialog (also "Sửa trích dẫn" for the citation under the cursor).

Search the user's library or the sources this document already cites (the copies carried in its citations, so a
document from someone else works without their library), move sources into the citation, give a page, text before
and after, or the narrative form "Nguyễn Văn An (2010)"; the preview shows the citation in the document's style.
"Nguồn mới…" opens the source form (with online lookup). Returns (cluster, {id: itemData}) or None.
"""
from . import citation_lists as lists
from . import citation_ui as ui
from .dialogs import Dialog

W = 340


def run(ctx, peer, texts, settings, plan, existing=None, language=None):
    from . import citation_model, citation_refresh
    t = texts["insert"]
    library = ui.open_library(ctx, peer, texts)
    doc_items = dict(plan["items"]) if plan else {}
    chosen_ids, known = [], dict(doc_items)
    cluster0 = existing[0] if existing else None
    if existing:
        known.update(existing[1])
        chosen_ids = [c["id"] for c in cluster0["items"]]
    style = citation_refresh.engine().load_style(settings["style"], settings.get("opts") or {}, settings.get("preset"))
    shown, result = [], {}
    dialog = Dialog(ctx, t["editTitle"] if existing else t["title"], W, 262)
    dialog.label("lSearch", t["search"], 8, 8, 190)
    dialog.edit("search", 8, 19, 200, help_text=t["search"])
    dialog.listbox("source", 214, 19, W - 222, [t["fromLibrary"], t["fromDocument"]],
                   1 if doc_items and (existing or not len(library)) else 0, help_text=t["fromLibrary"])
    dialog.label("lResults", t["results"], 8, 36, 200)
    lists.multi_list(dialog, "results", 8, 46, W - 16, 70, t["results"])
    dialog.label("more", "", 8, 118, 200)
    dialog.button("add", t["add"], 8, 128, 60, callback=lambda: add())
    dialog.button("remove", t["remove"], 72, 128, 60, callback=lambda: remove())
    dialog.button("new", t["newSource"], W - 88, 128, 80, callback=lambda: new_source())
    dialog.label("lChosen", t["chosen"], 8, 146, 200)
    lists.multi_list(dialog, "chosen", 8, 156, W - 16, 34, t["chosen"])
    last = cluster0["items"][-1] if cluster0 else {}
    first = cluster0["items"][0] if cluster0 else {}
    dialog.label("lLocator", t["locator"], 8, 196, 40)
    dialog.edit("locator", 50, 194, 60, text=last.get("locator", ""), help_text=t["locator"])
    dialog.label("lPrefix", t["prefix"], 116, 196, 46)
    dialog.edit("prefix", 162, 194, 70, text=first.get("prefix", ""), help_text=t["prefix"])
    dialog.label("lSuffix", t["suffix"], 238, 196, 40)
    dialog.edit("suffix", 278, 194, W - 286, text=last.get("suffix", ""), help_text=t["suffix"])
    dialog.check("narrative", t["narrative"], 8, 210, W - 16, state=bool(cluster0 and cluster0["mode"] == "narrative"))
    dialog.label("lPreview", t["preview"], 8, 224, 50)
    dialog.label("preview", "", 58, 224, W - 66, 14, wrap=True)
    dialog.button("ok", t["update"] if existing else t["insert"], W - 156, 242, 72, default=True,
                  callback=lambda: finish())
    dialog.button("cancel", texts["common"]["cancel"], W - 80, 242, 72, kind=2)

    def pool():
        if dialog.get("source") == 1:
            return list(doc_items.values())
        return library.search(dialog.get("search"), limit=lists.MAX_ROWS * 2) if dialog.get("search").strip() \
            else library.items

    def fill_results():
        found, hidden = lists.filter_items(pool(), dialog.get("search"), ui.short_label)
        shown[:] = found
        lists.set_rows(dialog, "results", [ui.short_label(i) for i in found])
        dialog.set_text("more", t["more"] % hidden if hidden else "")

    def fill_chosen():
        lists.set_rows(dialog, "chosen", [ui.short_label(known[i]) for i in chosen_ids])
        update_preview()

    def add():
        for row in lists.selected_rows(dialog, "results"):
            item = shown[row]
            known[item["id"]] = item
            if item["id"] not in chosen_ids:
                chosen_ids.append(item["id"])
        fill_chosen()

    def remove():
        for row in sorted(lists.selected_rows(dialog, "chosen"), reverse=True):
            del chosen_ids[row]
        fill_chosen()

    def new_source():
        from .citation_entry_dialog import run as entry
        item = entry(ctx, dialog.dialog.getPeer(), texts, None, library, style, language=language)
        if item is not None:
            known[item["id"]] = item
            chosen_ids.append(item["id"])
            fill_chosen()

    def build():
        cites = [{"id": i} for i in chosen_ids]
        if cites:
            for key, target in (("locator", cites[-1]), ("suffix", cites[-1]), ("prefix", cites[0])):
                if dialog.get(key).strip():
                    target[key] = dialog.get(key).strip()
            if "locator" in cites[-1]:
                cites[-1]["label"] = last.get("label", "page") if cluster0 else "page"
        mode = "narrative" if dialog.get("narrative") else "normal"
        return {"citationID": "", "items": cites, "mode": mode}

    def update_preview():
        from .citation_engine import process
        cluster = build()
        if not cluster["items"]:
            return dialog.set_text("preview", "")
        try:
            text = process(style, {i: known[i] for i in chosen_ids}, [cluster],
                           document_language=language)["citations"][0]["text"]
        except Exception as exc:  # noqa: BLE001 - a preview never stops the dialog
            text = str(exc)
        dialog.set_text("preview", text)

    def finish():
        if not chosen_ids:
            return ui.inform(ctx, dialog.dialog.getPeer(), texts, texts["blockers"]["noSelection"])
        result["cluster"] = build()  # read while the dialog still exists
        dialog.end(1)

    dialog.on_change(["search", "source"], fill_results)
    dialog.on_change(["locator", "prefix", "suffix", "narrative"], update_preview)
    dialog.on_ready = lambda: (fill_results(), fill_chosen())
    if dialog.execute(peer) != 1:
        return None
    cluster = result["cluster"]
    return cluster, {i: citation_model.for_embedding(known[i]) for i in chosen_ids}
