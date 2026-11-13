# SPDX-License-Identifier: AGPL-3.0-only
""""Chèn lại trích dẫn" list: the sources the document cites, by their number in the bibliography
("[3] Nguyễn Văn An (2010), …"); typing a number or words filters the list, Enter inserts the selected sources with
an optional page. The quick way, typing "[3" then Alt+Shift+I, does not open it (citation_cite_actions).
Returns (ids, locator) or None."""
from . import citation_lists as lists
from . import citation_ui as ui
from .dialogs import Dialog

W, H = 340, 214


def run(ctx, peer, texts, entries):
    t = texts["reinsert"]
    shown, result = list(entries), {}
    dialog = Dialog(ctx, t["title"], W, H)
    dialog.label("lFilter", t["filter"], 8, 8, 200)
    dialog.edit("filter", 8, 19, W - 16, help_text=t["filter"])
    dialog.label("lList", t["list"], 8, 36, 200)
    lists.multi_list(dialog, "list", 8, 46, W - 16, 120, t["list"])
    dialog.label("lLocator", t["locator"], 8, 172, 40)
    dialog.edit("locator", 50, 170, 80, help_text=t["locator"])
    dialog.label("hint", t["hint"], 8, 186, W - 16, 10)
    dialog.button("ok", t["insert"], W - 156, H - 20, 72, default=True, callback=lambda: finish())
    dialog.button("cancel", texts["common"]["cancel"], W - 80, H - 20, 72, kind=2)

    def refill():
        shown[:] = lists.filter_entries(entries, dialog.get("filter"))
        lists.set_rows(dialog, "list", [lists.row_text(e) for e in shown], (0,) if shown else ())

    def finish():
        rows = lists.selected_rows(dialog, "list")
        if not rows:
            return ui.inform(ctx, dialog.dialog.getPeer(), texts, texts["blockers"]["noSelection"])
        result["ids"] = [shown[r]["id"] for r in rows]
        result["locator"] = dialog.get("locator").strip()
        dialog.end(1)

    dialog.on_change(["filter"], refill)
    dialog.on_ready = refill
    if dialog.execute(peer) != 1:
        return None
    return result["ids"], result["locator"]
