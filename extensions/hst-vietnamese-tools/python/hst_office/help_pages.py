# SPDX-License-Identifier: AGPL-3.0-only
"""Open a page of the offline user guide (help/ of this extension) in the system browser.

Used by the Help tab buttons org.hst.office.vi:WhereIsCommand ("Lệnh quen thuộc ở đâu?") and
org.hst.office.vi:KeyboardShortcuts ("Phím tắt"), and by the welcome dialog's "Xem hướng dẫn chuyển đổi nhanh".
The pages are local files: nothing is fetched.
"""
import os

from .data_files import EXT_ROOT

PAGES = {"WhereIsCommand": "lenh-quen-thuoc.html", "KeyboardShortcuts": "phim-tat.html"}
COMMANDS = frozenset(PAGES)
URIS_ONLY = 1  # com.sun.star.system.SystemShellExecuteFlags.URIS_ONLY: open the URL, never run a program


def page_path(command):
    """Absolute path of the guide page of `command`; KeyError for an unknown command, OSError when it is missing."""
    path = os.path.join(EXT_ROOT, "help", PAGES[command])
    if not os.path.isfile(path):
        raise FileNotFoundError(path)
    return path


def open_page(ctx, command):
    """Show the guide page of `command` in the system browser."""
    import uno
    shell = ctx.ServiceManager.createInstanceWithContext("com.sun.star.system.SystemShellExecute", ctx)
    shell.execute(uno.systemPathToFileUrl(page_path(command)), "", URIS_ONLY)
