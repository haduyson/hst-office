# SPDX-License-Identifier: LicenseRef-HST-Proprietary
# Copyright (C) 2026 HASON TECH
"""The extension's dialogs that are inside their modal loop (dialogs.Dialog.execute, the welcome dialog).

A modal dialog keeps the frame it belongs to from closing, so Desktop.terminate() fails at once while one is open.
"Cập nhật ngay" ends these before it closes the office (update_launch.end_own_dialogs); the update pop-up waits while
one is open (update_popup).
"""
OPEN = []  # UnoControlDialogs, oldest first


def execute(dialog):
    """dialog.execute(), with `dialog` in OPEN for the duration of its modal loop."""
    OPEN.append(dialog)
    try:
        return dialog.execute()
    finally:
        OPEN.remove(dialog)
