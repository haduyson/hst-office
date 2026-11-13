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


def ask_text(ctx, texts, parent_peer, title, prompt, value=""):
    """One answer (str, may be empty) or None on Cancel: the question of a "Hỏi" rule, or a list name."""
    d = Dialog(ctx, title, 240, 66)
    d.label("text", prompt, 8, 6, 224, 18, wrap=True)
    d.edit("answer", 8, 26, 224, text=value, help_text=prompt)
    answer = {}

    def accept():
        answer["text"] = d.get("answer")
        d.end(1)
    d.button("ok", texts["ok"], 116, 46, 56, default=True, callback=accept)
    d.button("cancel", texts["cancel"], 176, 46, 56, callback=lambda: d.end(0))
    return answer.get("text", "") if d.execute(parent_peer) == 1 else None


def show_lines(ctx, texts, parent_peer, title, heading, lines):
    """A read-only list of result lines (Kiểm tra lỗi)."""
    d = Dialog(ctx, title, 320, 200)
    d.label("heading", heading, 8, 6, 304, 18, wrap=True)
    d.listbox("lines", 8, 26, 304, list(lines), 0, h=150, dropdown=False, help_text=heading)
    d.button("close", texts["close"], 256, 182, 56, default=True, callback=lambda: d.end(0))
    d.execute(parent_peer)


def choose_item(ctx, texts, parent_peer, title, label, items):
    """Index of the chosen item, or None (Chọn từ danh bạ)."""
    d = Dialog(ctx, title, 260, 150)
    d.label("text", label, 8, 6, 244, 18, wrap=True)
    d.listbox("items", 8, 26, 244, list(items), 0, h=100, dropdown=False, help_text=label)
    chosen = {}

    def accept():
        chosen["index"] = d.get("items")
        d.end(1)
    d.button("ok", texts["ok"], 136, 132, 56, default=True, callback=accept)
    d.button("cancel", texts["cancel"], 196, 132, 56, callback=lambda: d.end(0))
    if d.execute(parent_peer) != 1 or chosen.get("index", -1) < 0:
        return None
    return chosen["index"]
