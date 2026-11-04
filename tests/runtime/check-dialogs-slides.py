#!/usr/bin/env python3
# SPDX-License-Identifier: AGPL-3.0-only
"""Slides dialogs follow PowerPoint's structure: tab names and key controls, on a private Xvfb.

Usage: check-dialogs-slides.py [--instdir DIR] [--work DIR]
Needs a built instdir with the vi language pack.
"""
import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from hst_dialog_uitest import Checks, DialogHarness, click, tab_titles, visible  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def check_slide_properties(h, c):
    doc = h.new_document("simpress")
    dlg = h.open_dialog(".uno:PageSetup", "DrawPageDialog")
    titles = tab_titles(dlg)
    c.equal("slide properties: Format Background", "Định dạng nền" in titles, True)
    click(dlg, "cancel")
    doc.close(True)


def check_slide_show(h, c):
    doc = h.new_document("simpress")
    dlg = h.open_dialog(".uno:PresentationDialog", "PresentationDialog")
    for widget in ("default", "allslides", "manualslides"):
        c.equal(f"slide show: {widget} kept", visible(dlg, widget), True)
    click(dlg, "cancel")
    doc.close(True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--instdir", default=os.path.join(ROOT, "upstream/libreoffice/instdir"))
    parser.add_argument("--work", default=os.path.join(ROOT, "tests/output/dialogs-slides"))
    args = parser.parse_args()
    harness = DialogHarness(args.instdir, args.work, 22982, ":82")
    checks = Checks()
    try:
        check_slide_properties(harness, checks)
        check_slide_show(harness, checks)
    finally:
        harness.close()
    return checks.finish()


if __name__ == "__main__":
    sys.exit(main())
