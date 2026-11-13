# SPDX-License-Identifier: AGPL-3.0-only
"""The source form ("Nguồn tài liệu mới" / "Sửa nguồn tài liệu"): type, authors, the fields of that type, online
lookup by DOI/ISBN/PMID/arXiv (on click only), splitting a pasted formatted reference into fields (offline), and a
preview of the bibliography entry. Saving also stores the source in the user's library unless unticked.
Returns the saved item or None. Field logic: citation_entry_form (pure)."""
from . import citation_entry_form as form
from . import citation_ui as ui
from .citation_lists import set_label
from .citation_refresh_plan import term_language
from .dialogs import Dialog

W, H = 420, 316
GRID_Y, ROW = 106, 16


def run(ctx, peer, texts, item, library, style, save_default=True, language=None):
    from .citation_model import TYPE_LABELS
    t, labels = texts["entry"], texts["fields"]
    types = [k for k, _v in TYPE_LABELS]
    state = {"base": item}
    current_type = (item or {}).get("type") or "book"
    if current_type not in types:
        types.append(current_type)
    dialog = Dialog(ctx, t["titleEdit"] if item else t["titleNew"], W, H)
    dialog.label("lType", t["type"], 8, 10, 90)
    dialog.listbox("type", 102, 8, 150, [texts["types"].get(k, k) for k in types], types.index(current_type),
                   help_text=t["type"])
    dialog.label("lLookup", t["lookup"], 8, 28, 120)
    dialog.edit("lookupText", 130, 26, 186, help_text=t["lookup"])
    dialog.button("lookup", t["lookupButton"], 320, 25, W - 328, callback=lambda: do_lookup())
    dialog.label("lPaste", t["paste"], 8, 46, 120)
    dialog.edit("pasteText", 130, 44, 186, help_text=t["paste"])
    dialog.button("paste", t["pasteButton"], 320, 43, W - 328, callback=lambda: do_paste())
    dialog.label("lAuthors", t["authors"], 8, 62, 200)
    dialog.edit("authors", 8, 72, 196, h=30, multiline=True, help_text=t["authorsHelp"])
    dialog.label("lEditors", t["editors"], 212, 62, 200)
    dialog.edit("editors", 212, 72, W - 220, h=30, multiline=True, help_text=t["authorsHelp"])
    for index, field in enumerate(form.FIELDS):
        column, row = index % 2, index // 2
        x, y = 8 + column * 206, GRID_Y + row * ROW
        dialog.label("l_" + field, labels[field], x, y + 2, 92)
        dialog.edit("f_" + field, x + 94, y, 106, help_text=labels[field])
    y = GRID_Y + (len(form.FIELDS) + 1) // 2 * ROW + 4
    dialog.label("help", t["authorsHelp"], 8, y, W - 16, 10)
    dialog.check("library", t["saveToLibrary"], 8, y + 12, 200, state=save_default and not library.read_only)
    dialog.label("lPreview", t["preview"], 8, y + 26, 50)
    dialog.label("preview", "", 58, y + 26, W - 66, 18, wrap=True)
    dialog.button("ok", t["save"], W - 156, H - 20, 72, default=True, callback=lambda: save())
    dialog.button("cancel", texts["common"]["cancel"], W - 80, H - 20, 72, kind=2)

    def chosen_type():
        return types[max(0, dialog.get("type"))]

    def values():
        found = {f: dialog.get("f_" + f) for f in form.FIELDS}
        found["authors"], found["editors"] = dialog.get("authors"), dialog.get("editors")
        return found

    def fill(source):
        for key, value in form.values_of(source).items():
            dialog.set_text("f_" + key if key in form.FIELDS else key, value)
        if source.get("type") in types:
            dialog.select("type", types.index(source["type"]))
        on_type()

    def on_type():
        kind = chosen_type()
        shown = form.visible_fields(kind)
        for field in form.FIELDS:
            dialog.model.getByName("f_" + field).Enabled = field in shown
            dialog.model.getByName("l_" + field).Enabled = field in shown
        dialog.model.getByName("l_container-title").Label = texts["containerLabels"].get(kind, labels["container-title"])
        dialog.model.getByName("editors").Enabled = kind in form.EDITOR_TYPES
        preview()

    def preview():
        from .citation_engine import preview as render
        try:
            built, _warnings = form.item_of(values(), chosen_type(), state["base"])
            entry = render(style, built, document_language=term_language(style, language))["entry"]
            set_label(dialog, "preview", entry.get("text", ""))
        except Exception:  # noqa: BLE001 - half-typed fields: no preview yet
            set_label(dialog, "preview", "")

    def do_lookup():
        from .citation_lookup_action import lookup
        text = dialog.get("lookupText").strip()
        if not text:
            return
        set_label(dialog, "preview", t["lookupRunning"])
        found = lookup(ctx, dialog.dialog.getPeer(), texts, text)
        if found is not None:
            if state["base"] is None:
                state["base"] = found
            fill(found)
            ui.inform(ctx, dialog.dialog.getPeer(), texts, t["lookupFound"] % text)
        else:
            preview()

    def do_paste():
        from .citation_paste_parse import parse_reference
        text = dialog.get("pasteText").strip()
        if not text:
            return
        found, info = parse_reference(text)
        fill(found)
        message = t["pasteDone"] % (len(info.get("found", [])), round(100 * info.get("confidence", 0)))
        ui.inform(ctx, dialog.dialog.getPeer(), texts, ui.with_warnings(texts, message, info.get("warnings")))

    def save():
        found = values()
        if not found["title"].strip() and not found["authors"].strip():
            return ui.inform(ctx, dialog.dialog.getPeer(), texts, texts["blockers"]["noTitle"])
        state.update(values=found, type=chosen_type(), library=bool(dialog.get("library")) and not library.read_only)
        dialog.end(1)

    dialog.on_change(["type"], on_type)
    dialog.on_change(["authors", "editors"] + ["f_" + f for f in form.FIELDS], preview)
    dialog.on_ready = lambda: fill(item) if item else on_type()
    if dialog.execute(peer) != 1:
        return None
    built, _warnings = form.item_of(state["values"], state["type"], state["base"])  # read before the dialog closed
    if state["library"]:
        built = store(ctx, peer, texts, library, built, editing=item is not None)
    return built


def store(ctx, peer, texts, library, item, editing=False):
    """Put the item in the library (asking Gộp / Giữ cả hai for a duplicate) and save it; returns the stored item."""
    if editing and library.get(item["id"]) is not None:
        library.update(item)
    else:
        _added, duplicates = library.add([item])
        for found, existing_id in duplicates:
            t = texts["import"]
            answer = ui.choose(ctx, peer, texts["common"]["title"], t["duplicatesAsk"] % 1,
                               (t["merge"], t["keepBoth"]), 0)
            if answer == 0:
                library.merge(existing_id, found)
                item = library.get(existing_id)
            else:
                library.keep_both(found)
    ui.save_library(ctx, peer, texts, library)
    return item
