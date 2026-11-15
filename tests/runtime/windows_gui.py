# SPDX-License-Identifier: AGPL-3.0-only
"""Windows side of the GUI runtime checks: an installed HST Office started with its own profile, its windows, real
mouse and keyboard input (SendInput), screenshots and the accessibility tree over UNO.

Run with the office's own python.exe (so `import uno` works) on an interactive desktop. Nothing here starts or stops
anything but the office it started itself. This module is the stable facade; the work is in
  windows_gui_win32    window queries (office_windows, find_window, hwnd_of, window_rect, client_origin)
  windows_gui_guard    the input gate: keys and clicks reach only a verified HST Office window (BlockedInput)
  windows_gui_input    gated SendInput (keys, chord, click, drag, mouse_move), foreground, activate, screenshot
  windows_gui_dialogs  dialogs over UNO, close_dialog/close_hwnd with WM_CLOSE (no keys), dismiss_startup
  windows_gui_office   WinOffice
  windows_gui_a11y     walk, showing, find_named, texts, press
"""
import os

from windows_gui_a11y import find_named, press, showing, texts, walk  # noqa: F401
from windows_gui_dialogs import (close_dialog, close_hwnd, dialog_hwnd, dialogs, dismiss_startup,  # noqa: F401
                                 window_title)
from windows_gui_guard import BlockedInput, is_ours  # noqa: F401
from windows_gui_input import (VK, activate, chord, click, drag, foreground, key_press, keys,  # noqa: F401
                               mouse_move, screenshot)
from windows_gui_office import WinOffice  # noqa: F401
from windows_gui_win32 import client_origin, find_window, hwnd_of, office_windows, user32, window_rect  # noqa: F401

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))


def load_check(name):
    """A tests/runtime/check-*.py script as a module (its main() is not run), to share its checks with Windows."""
    import importlib.util
    spec = importlib.util.spec_from_file_location(name.replace("-", "_"), os.path.join(HERE, name + ".py"))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class Results:
    """PASS/FAIL rows printed as they come and written to <out>/results.json after each one (a hang keeps evidence)."""

    def __init__(self, out, profile):
        self.out, self.profile, self.rows = out, profile, []
        os.makedirs(out, exist_ok=True)

    def __call__(self, name, ok, detail=""):
        import json
        self.rows.append({"check": name, "status": "PASS" if ok else "FAIL", "detail": str(detail)[:1500]})
        print("%s  %s  %s" % ("PASS" if ok else "FAIL", name, str(detail)[:400]), flush=True)
        with open(os.path.join(self.out, "results.json"), "w", encoding="utf-8") as handle:
            json.dump({"profile": self.profile, "results": self.rows,
                       "failed": sum(r["status"] == "FAIL" for r in self.rows)}, handle, ensure_ascii=False, indent=1)
        return ok

    def note(self, name, detail):
        """Evidence that is not a pass/fail claim."""
        print("INFO  %s  %s" % (name, str(detail)[:600]), flush=True)
        self.rows.append({"check": name, "status": "INFO", "detail": str(detail)[:1500]})

    def exit_code(self):
        failed = [r for r in self.rows if r["status"] == "FAIL"]
        print("%d checks, %d failed" % (sum(r["status"] != "INFO" for r in self.rows), len(failed)), flush=True)
        return 1 if failed else 0
