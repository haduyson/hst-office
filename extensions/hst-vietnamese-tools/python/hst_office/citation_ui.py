# SPDX-License-Identifier: AGPL-3.0-only
"""Shared pieces of the citation dialogs (UNO): messages and choices with buttons in the UI language, file pickers,
the user's library, and one-line labels of sources for list boxes."""
import math

from .dialogs import Dialog

FILEOPEN_SIMPLE, FILESAVE_AUTOEXTENSION = 0, 10
MAX_ROWS = 500  # list boxes show at most this many rows (filtering does the rest)


def choose(ctx, peer, title, text, labels, default=0):
    """Index of the button the user pressed (labels left to right), or -1 when the dialog was closed."""
    lines = sum(max(1, math.ceil(len(part) / 60)) for part in text.split("\n"))
    width, height = 300, lines * 9 + 2
    dialog = Dialog(ctx, title, width, height + 38)
    dialog.label("text", text, 8, 8, width - 16, height, wrap=True)
    chosen = {"index": -1}
    x = width - 8 - 74 * len(labels) + 4
    for index, label in enumerate(labels):
        def pick(index=index):
            chosen["index"] = index
            dialog.end(1)
        dialog.button("b%d" % index, label, x, height + 16, 70, default=index == default, callback=pick)
        x += 74
    dialog.execute(peer)
    return chosen["index"]


def inform(ctx, peer, texts, text):
    choose(ctx, peer, texts["common"]["title"], text, (texts["common"]["ok"],))


def ask(ctx, peer, texts, text):
    """True for "Có"/"Yes"; "Không"/"No" is the default, so Enter never confirms by accident."""
    return choose(ctx, peer, texts["common"]["title"], text, (texts["common"]["yes"], texts["common"]["no"]), 1) == 0


def with_warnings(texts, text, warnings):
    if not warnings:
        return text
    shown = list(dict.fromkeys(warnings))[:8]
    return "%s\n\n%s\n- %s" % (text, texts["common"]["warnings"], "\n- ".join(shown))


def pick_file(ctx, title, filters, save=False, default_name=""):
    """System path chosen in the office file dialog, or None. ``filters`` = ((name, "*.ris;*.bib"), ...)."""
    import uno
    picker = ctx.ServiceManager.createInstanceWithContext("com.sun.star.ui.dialogs.FilePicker", ctx)
    picker.initialize((FILESAVE_AUTOEXTENSION if save else FILEOPEN_SIMPLE,))
    try:
        picker.setTitle(title)
        for name, pattern in filters:
            picker.appendFilter(name, pattern)
        if default_name:
            picker.setDefaultName(default_name)
        if picker.execute() != 1:
            return None
        return uno.fileUrlToSystemPath(picker.getSelectedFiles()[0])
    finally:
        picker.dispose()


def open_library(ctx, peer, texts):
    """The user's library; a damaged file is kept aside (the engine does that) and an empty library is used."""
    from . import citation_library, citation_refresh
    path = citation_library.library_path(citation_refresh.user_dir(ctx))
    try:
        return citation_library.Library.load(path)
    except citation_library.LibraryDamaged as exc:
        inform(ctx, peer, texts, texts["blockers"]["libraryDamaged"] % exc)
        return citation_library.Library(path)


def save_library(ctx, peer, texts, library):
    """Save; tells the user and returns False when it cannot be written."""
    from . import citation_library
    try:
        library.save()
        return True
    except (citation_library.LibraryError, OSError) as exc:
        inform(ctx, peer, texts, texts["common"]["error"] % exc)
        return False


def short_label(item):
    """"Nguyễn Văn An, Trần Bình (2010) — Nhan đề" for list boxes."""
    from .citation_names import full_name
    from .citation_model import year
    names = [full_name(n) for n in (item.get("author") or item.get("editor") or [])[:3]]
    who = ", ".join(n for n in names if n) + (" …" if len(item.get("author") or []) > 3 else "")
    when = year(item)
    head = "%s (%s)" % (who, when) if who and when else (who or (str(when) if when else ""))
    title = " ".join((item.get("title") or "").split())
    text = "%s — %s" % (head, title) if head else title
    return text if len(text) <= 160 else text[:157] + "…"
