# SPDX-License-Identifier: AGPL-3.0-only
"""The warning before a Sheets document whose cells use HST functions is saved as .xlsx/.xls (save_format_check.py):
"Chuyển thành giá trị khi lưu" (Enter), "Vẫn lưu", "Hủy" (Esc, or closing the dialog), and "Không hỏi lại"."""
from . import utilities_texts as T
from .save_format_rules import CANCEL, CONVERT, KEEP

WIDTH, HEIGHT, MARGIN, GAP = 300, 118, 8, 4
BUTTON_WIDTHS = (120, 60, 50)


def ask(ctx, doc, names, count, extension):
    """(choice, "Không hỏi lại" ticked) from the dialog; (CANCEL, False) when it is closed without a button."""
    from .dialogs import Dialog
    dialog = Dialog(ctx, T.SAVE_TITLE % extension, WIDTH, HEIGHT)
    dialog.label("text", T.SAVE_TEXT % (", ".join(names), extension, count), MARGIN, MARGIN, WIDTH - 2 * MARGIN, 66,
                 wrap=True)
    dialog.check("dontAsk", T.SAVE_DONT_ASK, MARGIN, 78, WIDTH - 2 * MARGIN, state=False)
    chosen = []
    x = WIDTH - MARGIN - sum(BUTTON_WIDTHS) - GAP * (len(BUTTON_WIDTHS) - 1)
    # left to right is also the Tab order after the check box; Enter converts, Esc cancels
    for result, label, width in zip((CONVERT, KEEP, CANCEL), T.SAVE_BUTTONS, BUTTON_WIDTHS):
        dialog.button(result, label, x, 96, width, default=result == CONVERT,
                      callback=lambda result=result: chosen.append((result, bool(dialog.get("dontAsk"))))
                      or dialog.end(1))
        x += width + GAP
    controller = doc.getCurrentController()
    peer = controller.getFrame().getContainerWindow() if controller else None
    dialog.execute(peer)
    return chosen[-1] if chosen else (CANCEL, False)  # the dialog is disposed: its state was read on the click
