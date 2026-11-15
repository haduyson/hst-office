# SPDX-License-Identifier: AGPL-3.0-only
"""Another application's clipboard on an X display: owns CLIPBOARD with a text until it is killed.

Used by check-gtk-clipboard-paste-state.py as "a text editor or browser on the same display".
Usage: python3 tests/runtime/x11_clipboard_owner.py <display> <text>. Prints "owned" once it owns the selection.
"""
import os
import sys

os.environ["DISPLAY"] = sys.argv[1]
import gi  # noqa: E402

gi.require_version("Gdk", "3.0")
gi.require_version("Gtk", "3.0")
from gi.repository import Gdk, GLib, Gtk  # noqa: E402


def main():
    clipboard = Gtk.Clipboard.get(Gdk.SELECTION_CLIPBOARD)
    clipboard.set_text(sys.argv[2], -1)
    GLib.idle_add(lambda: print("owned", flush=True) and False)
    Gtk.main()


if __name__ == "__main__":
    main()
