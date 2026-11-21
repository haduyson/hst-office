#!/usr/bin/env python3
# SPDX-License-Identifier: AGPL-3.0-only
"""The Sheets header/footer edit dialog (Insert > Headers and Footers) shows "Preset", "Format", "Field" and the
Bold/Italic/Underline buttons in Vietnamese: the labels' text and every accessible name of the dialog.

Usage: check-vi-sheets-headerfooter-labels.py [--instdir DIR] [--work DIR] [--port N] [--display :N]
Needs an instdir with the vi language pack (the default UI language). Runs headless (svp) with a fresh profile.
"""
import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from hst_dialog_uitest import Checks, DialogHarness, click, state  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
LABELS = {"labelFT_PRESET": "Định sẵn", "labelFT_FORMAT": "Định dạng", "labelFT_FIELD": "Trường"}
BUTTONS = ("Đậm", "Nghiêng", "Gạch dưới")
ENGLISH = {"Preset", "Format", "Field", "Bold", "Italic", "Underline"}


def dialog_accessible_names(h):
    """Accessible names of every showing widget in the visible top windows that are no document frame's."""
    import uno
    showing = uno.getConstantByName("com.sun.star.accessibility.AccessibleStateType.SHOWING")
    toolkit = h.office.service("com.sun.star.awt.Toolkit")
    frames = h.office.desktop().getFrames()
    containers = [frames.getByIndex(i).getContainerWindow() for i in range(frames.getCount())]
    names = []
    for i in range(toolkit.getTopWindowCount()):
        window = toolkit.getTopWindow(i)
        if not window.isVisible() or any(window == c for c in containers):
            continue
        node = window.getProperty("XAccessible")  # toolkit windows hand out their XAccessible as a property
        stack = [node.getAccessibleContext() if node is not None else None]
        while stack:
            context = stack.pop()
            if context is None or not context.getAccessibleStateSet() & showing:
                continue
            if context.getAccessibleName():
                names.append(context.getAccessibleName())
            stack.extend(context.getAccessibleChild(i).getAccessibleContext()
                         for i in range(min(context.getAccessibleChildCount(), 400)))
    return names


def check_header_footer(h, c):
    doc = h.new_document("scalc")
    dlg = h.open_dialog(".uno:EditHeaderAndFooter", "HeaderFooterDialog")
    for widget, expected in LABELS.items():
        c.equal(f"label {widget}", state(dlg.getChild(widget)).get("Text", "").replace("~", ""), expected)
    names = dialog_accessible_names(h)
    for name in BUTTONS:
        c.equal(f"button accessible name {name!r} present", name in names, True)
    c.equal("English names left", sorted(ENGLISH & set(names)), [])
    click(dlg, "cancel")
    h.close_document(doc)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--instdir", default=os.path.join(ROOT, "upstream/libreoffice/instdir"))
    parser.add_argument("--work", default=os.path.join(ROOT, "tests/output/vi-sheets-headerfooter-labels"))
    parser.add_argument("--port", type=int, default=22992)
    parser.add_argument("--display", default=":91")
    args = parser.parse_args()
    harness = DialogHarness(args.instdir, args.work, args.port, args.display)
    checks = Checks()
    try:
        check_header_footer(harness, checks)
    finally:
        harness.close()
    return checks.finish()


if __name__ == "__main__":
    sys.exit(main())
