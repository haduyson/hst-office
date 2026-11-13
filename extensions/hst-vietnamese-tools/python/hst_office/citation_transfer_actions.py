# SPDX-License-Identifier: AGPL-3.0-only
"""Import references into the user's library (RIS, BibTeX, CSL-JSON, EndNote XML, PubMed, EndNote tagged) with a
preview of the "sửa tên Việt" corrections, and export the library, a selection or a document's sources (RIS,
BibTeX, CSL-JSON). Files are read and written only where the user picks them."""
import os

from . import citation_lists as lists
from . import citation_ui as ui
from .dialogs import Dialog

EXPORT_FORMATS = ("ris", "bibtex", "csl-json")


def _preview(ctx, peer, texts, path, result):
    """The suggestions the user keeps (list of suggestion dicts), or None when cancelled."""
    t = texts["import"]
    width, height = 380, 250
    dialog = Dialog(ctx, t["previewTitle"], width, height)
    dialog.label("summary", t["summary"] % (os.path.basename(path), len(result.items)), 8, 8, width - 16)
    dialog.label("lWarnings", t["warnings"], 8, 22, width - 16)
    dialog.edit("warnings", 8, 32, width - 16, h=48, multiline=True, readonly=True,
                text="\n".join(result.warnings) or "—")
    dialog.label("lSuggestions", t["suggestions"], 8, 86, width - 16)
    lists.multi_list(dialog, "suggestions", 8, 96, width - 16, 124, t["suggestions"])
    kept = {}

    def finish():
        kept["rows"] = lists.selected_rows(dialog, "suggestions")
        dialog.end(1)

    dialog.button("ok", t["doImport"], width - 156, height - 20, 72, default=True, callback=finish)
    dialog.button("cancel", texts["common"]["cancel"], width - 80, height - 20, 72, kind=2)
    rows = [s["message"] for s in result.suggestions]
    dialog.on_ready = lambda: lists.set_rows(dialog, "suggestions", rows, range(len(rows)))
    if dialog.execute(peer) != 1:
        return None
    return [result.suggestions[r] for r in kept["rows"]]


def import_into(ctx, peer, texts, library):
    """Ask for a file and import it; returns how many items were added."""
    from . import citation_import, citation_vn_fix
    from .citation_text_io import ImportFailure
    t = texts["import"]
    path = ui.pick_file(ctx, t["pickTitle"], citation_import.FILTER + (("*", "*.*"),))
    if not path:
        return 0
    try:
        result = citation_import.import_file(path)
    except (ImportFailure, OSError) as exc:
        ui.inform(ctx, peer, texts, texts["common"]["error"] % exc)
        return 0
    if not result.items:
        ui.inform(ctx, peer, texts, ui.with_warnings(texts, t["nothing"], result.warnings))
        return 0
    accepted = _preview(ctx, peer, texts, path, result)
    if accepted is None:
        return 0
    items = citation_vn_fix.apply(result.items, accepted)
    added, duplicates = library.add(items)
    if duplicates:
        answer = ui.choose(ctx, peer, texts["common"]["title"], t["duplicatesAsk"] % len(duplicates),
                           (t["merge"], t["keepBoth"], t["skip"]), 0)
        for item, existing_id in duplicates:
            if answer == 0:
                library.merge(existing_id, item)
            elif answer == 1:
                library.keep_both(item)
    if ui.save_library(ctx, peer, texts, library):
        done = texts["done"]["imported"] % (len(added) + (len(duplicates) if duplicates and answer == 1 else 0))
        if duplicates and answer != 1:
            done += "\n" + texts["done"]["duplicates"] % len(duplicates)
        ui.inform(ctx, peer, texts, done)
    return len(added)


def export(ctx, peer, texts, scopes):
    """``scopes`` = [items of the selection, of the library, of the document]; asks scope, format and file."""
    from . import citation_export
    t = texts["export"]
    width, height = 260, 84
    dialog = Dialog(ctx, t["title"], width, height)
    choices = {}
    available = [i for i, items in enumerate(scopes) if items]
    if not available:
        return 0
    dialog.label("lScope", t["scope"], 8, 10, 60)
    dialog.listbox("scope", 70, 8, width - 78, [t["scopes"][i] for i in available], 0, help_text=t["scope"])
    dialog.label("lFormat", t["format"], 8, 28, 60)
    dialog.listbox("format", 70, 26, width - 78, t["formats"], 0, help_text=t["format"])

    def finish():
        choices.update(scope=available[max(0, dialog.get("scope"))], fmt=EXPORT_FORMATS[max(0, dialog.get("format"))])
        dialog.end(1)

    dialog.button("ok", t["export"], width - 156, height - 20, 72, default=True, callback=finish)
    dialog.button("cancel", texts["common"]["cancel"], width - 80, height - 20, 72, kind=2)
    if dialog.execute(peer) != 1:
        return 0
    items, fmt = scopes[choices["scope"]], choices["fmt"]
    extension = citation_export.FORMATS[fmt]
    path = ui.pick_file(ctx, t["title"], ((t["formats"][EXPORT_FORMATS.index(fmt)], "*" + extension),), save=True,
                        default_name="tai-lieu-tham-khao" + extension)
    if not path:
        return 0
    try:
        with open(path, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(citation_export.export(items, fmt, portable=True))
    except (OSError, ValueError) as exc:
        ui.inform(ctx, peer, texts, texts["common"]["error"] % exc)
        return 0
    ui.inform(ctx, peer, texts, texts["done"]["exported"] % len(items))
    return len(items)
