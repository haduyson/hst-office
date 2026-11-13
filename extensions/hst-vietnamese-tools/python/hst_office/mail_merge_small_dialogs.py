# SPDX-License-Identifier: AGPL-3.0-only
"""Trộn thư: the file picker for the recipient list, the sheet choice of a workbook with several sheets and
"Tìm người nhận"."""
from .dialogs import Dialog

PATTERNS = "*.xlsx;*.xls;*.ods;*.csv;*.xlsm;*.fods;*.txt"


def pick_file(ctx, texts, folder=""):
    """Path of the chosen list file, or None."""
    import uno
    picker = ctx.ServiceManager.createInstanceWithArgumentsAndContext(
        "com.sun.star.ui.dialogs.FilePicker", (0,), ctx)  # TemplateDescription.FILEOPEN_SIMPLE
    picker.setTitle(texts["pick.title"])
    picker.appendFilter(texts["pick.filter"], PATTERNS)
    picker.setCurrentFilter(texts["pick.filter"])
    if folder:
        try:
            picker.setDisplayDirectory(uno.systemPathToFileUrl(folder))
        except Exception:  # noqa: BLE001 - folder gone: the picker's own default
            pass
    if picker.execute() != 1:
        return None
    files = picker.getSelectedFiles()
    return uno.fileUrlToSystemPath(files[0]) if files else None


def choose_sheet(ctx, texts, names, parent_peer):
    """The sheet holding the list, or None; no question for a single sheet."""
    if len(names) < 2:
        return names[0] if names else None
    d = Dialog(ctx, texts["sheet.title"], 220, 132)
    d.label("text", texts["sheet.label"], 8, 6, 204, 20, wrap=True)
    d.listbox("sheets", 8, 28, 204, names, 0, h=78, dropdown=False, help_text=texts["sheet.title"])
    chosen = {}

    def accept():
        chosen["index"] = d.get("sheets")
        d.end(1)
    d.button("ok", texts["ok"], 96, 112, 56, default=True, callback=accept)
    d.button("cancel", texts["cancel"], 156, 112, 56, callback=lambda: d.end(0))
    if d.execute(parent_peer) != 1:
        return None
    return names[max(0, chosen.get("index", 0))]


def ask_find(ctx, texts, parent_peer, last=""):
    """The text to look for, or None."""
    d = Dialog(ctx, texts["find.title"], 220, 56)
    d.label("text", texts["find.label"], 8, 6, 204)
    d.edit("needle", 8, 18, 204, text=last, help_text=texts["find.label"])
    found = {}

    def accept():
        found["text"] = d.get("needle")
        d.end(1)
    d.button("find", texts["find.run"], 96, 36, 56, default=True, callback=accept)
    d.button("cancel", texts["cancel"], 156, 36, 56, callback=lambda: d.end(0))
    if d.execute(parent_peer) != 1:
        return None
    return found.get("text", "").strip() or None
