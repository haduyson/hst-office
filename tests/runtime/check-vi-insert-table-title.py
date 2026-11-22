#!/usr/bin/env python3
# SPDX-License-Identifier: LicenseRef-HST-Proprietary
# Copyright (C) 2026 HASON TECH
"""The Insert Table dialog of Slides and Draw is titled "Chèn bảng" in Vietnamese, never "Chèn tệp tin" (Insert File).

The title is read as the user and a screen reader get it: the dialog window's text and its accessible name.

Usage: check-vi-insert-table-title.py [--instdir DIR] [--work DIR] [--port N] [--display :N]
Needs an instdir with the vi language pack (the default UI language). Runs headless (svp) with a fresh profile.
"""
import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from hst_dialog_uitest import Checks, DialogHarness, click, state  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
EXPECTED = "Chèn bảng"


def dialog_accessible_names(h):
    """Accessible names of the visible top windows that are no document frame's (the open dialog)."""
    toolkit = h.office.service("com.sun.star.awt.Toolkit")
    frames = h.office.desktop().getFrames()
    containers = [frames.getByIndex(i).getContainerWindow() for i in range(frames.getCount())]
    names = []
    for i in range(toolkit.getTopWindowCount()):
        window = toolkit.getTopWindow(i)
        if not window.isVisible() or any(window == c for c in containers):
            continue
        node = window.getProperty("XAccessible")  # toolkit windows hand out their XAccessible as a property
        if node is not None:
            names.append(node.getAccessibleContext().getAccessibleName())
    return names


def check_app(h, c, factory, app):
    doc = h.new_document(factory)
    dlg = h.open_dialog(".uno:InsertTable", "NewTableDialog")
    title = state(dlg).get("Text")
    names = dialog_accessible_names(h)
    print(f"{app}: window text {title!r}, accessible names {names!r}")
    c.equal(f"{app}: Insert Table dialog title", title, EXPECTED)
    c.equal(f"{app}: Insert Table dialog accessible name", EXPECTED in names, True)
    click(dlg, "cancel")
    h.close_document(doc)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--instdir", default=os.path.join(ROOT, "upstream/libreoffice/instdir"))
    parser.add_argument("--work", default=os.path.join(ROOT, "tests/output/vi-insert-table-title"))
    parser.add_argument("--port", type=int, default=22991)
    parser.add_argument("--display", default=":91")
    args = parser.parse_args()
    harness = DialogHarness(args.instdir, args.work, args.port, args.display)
    checks = Checks()
    try:
        check_app(harness, checks, "simpress", "Slides")
        check_app(harness, checks, "sdraw", "Draw")
    finally:
        harness.close()
    return checks.finish()


if __name__ == "__main__":
    sys.exit(main())
