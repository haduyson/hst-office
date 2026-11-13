# SPDX-License-Identifier: AGPL-3.0-only
"""List boxes of the citation dialogs: fill them, read their (multiple) selection, filter sources by typed words.
Filtering is pure Python; the list helpers take a dialogs.Dialog."""
from .vietnamese_text import remove_diacritics

MAX_ROWS = 500


def fold(text):
    return remove_diacritics(text or "").lower()


def matches(words, haystack):
    folded = fold(haystack)
    return all(word in folded for word in words)


def filter_items(items, text, label, limit=MAX_ROWS):
    """(shown, hidden count): items whose label, DOI or ISBN contain every typed word (accents ignored)."""
    words = fold(text).split()
    found = [i for i in items if matches(words, " ".join((label(i), i.get("DOI", ""), i.get("ISBN", ""))))]
    return found[:limit], max(0, len(found) - limit)


def row_text(entry):
    label = entry["label"] or "[%d]" % entry["number"]
    text = " ".join(entry["text"].split())
    return "%s %s" % (label, text if len(text) <= 150 else text[:147] + "…")


def filter_entries(entries, typed):
    """Entries matching what was typed: a number keeps the entries with that number first, words filter the text."""
    typed = typed.strip().strip("[]")
    if typed.isdigit():
        number = int(typed)
        return [e for e in entries if e["number"] == number] + \
               [e for e in entries if e["number"] != number and str(e["number"]).startswith(typed)]
    words = fold(typed).split()
    return [e for e in entries if matches(words, row_text(e))]


def set_rows(dialog, name, rows, selected=()):
    import uno
    model = dialog.model.getByName(name)
    model.StringItemList = uno.Any("[]string", tuple(rows))
    uno.invoke(model, "setPropertyValue", ("SelectedItems", uno.Any("[]short", tuple(selected))))


def selected_rows(dialog, name):
    return list(dialog.model.getByName(name).SelectedItems)


def multi_list(dialog, name, x, y, w, h, help_text, multi=True):
    """A list box showing several rows, with multiple selection when ``multi``."""
    model = dialog.listbox(name, x, y, w, [], h=h, help_text=help_text, dropdown=False)
    model.MultiSelection = multi
    return model
