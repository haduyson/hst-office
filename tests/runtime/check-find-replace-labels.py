#!/usr/bin/env python3
# SPDX-License-Identifier: AGPL-3.0-only
"""Find and Replace in Writer shows its labels without a literal "_": the Advanced expander and every Go To prompt,
in Vietnamese and in English, and the English prompts keep their access key.

The prompts and the expander's Writer title are lines of a hidden list in findreplacedialog.ui; a list item is not
run through the builder's mnemonic conversion, so "_Nâng cao" and "Enter page _number:" used to show as written.
Names are read as the user sees them: the accessible name (vcl drops the "~" access-key marker) and, for the Go To
prompt, the label's text with its marker removed.

Usage: check-find-replace-labels.py [--instdir DIR] [--work DIR] [--port N] [--display :N] [--ui LANG ...]
Needs a built instdir with the vi language pack. Runs headless (svp) with a fresh profile per language.
"""
import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from dialogs_writer_find_cases import BOOKMARK, LINE, PAGE, SECTION, TAB_FIND, TAB_GOTO, TAB_REPLACE, TABLE, open_find  # noqa: E402
from hst_dialog_uitest import Checks, DialogHarness, select_entry, select_tab, state  # noqa: E402
from hst_gui import free_port  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
# Per UI language: the expander's Writer title and the Go To prompt (raw label text, "~" = access key) per place.
EXPECTED = {
    "vi": ("Nâng cao", {PAGE: "Nhập số trang:", SECTION: "Nhập số phần:", LINE: "Nhập số dòng:",
                        BOOKMARK: "Nhập tên đánh dấu trang:", TABLE: "Nhập số thứ tự:"}),
    "en-US": ("Advanced", {PAGE: "Enter page ~number:", SECTION: "Enter section ~number:", LINE: "Enter line ~number:",
                           BOOKMARK: "Enter bookmark ~name:", TABLE: "Enter ~number:"}),
}
# Roles whose name is what the user typed or picked, not a label of the dialog.
CONTENT_ROLES = ("COMBO_BOX", "LIST", "LIST_ITEM", "TEXT", "PARAGRAPH", "MENU_ITEM", "SCROLL_BAR")


def dialog_names(h):
    """Accessible names of the showing widgets of the open modeless dialog (top windows that are no frame's)."""
    import uno
    showing = uno.getConstantByName("com.sun.star.accessibility.AccessibleStateType.SHOWING")
    skip = {uno.getConstantByName("com.sun.star.accessibility.AccessibleRole." + r) for r in CONTENT_ROLES}
    toolkit = h.office.service("com.sun.star.awt.Toolkit")
    frames = h.office.desktop().getFrames()
    containers = [frames.getByIndex(i).getContainerWindow() for i in range(frames.getCount())]
    windows = [toolkit.getTopWindow(i) for i in range(toolkit.getTopWindowCount())]
    names = []
    for window in windows:
        if not window.isVisible() or any(window == c for c in containers):
            continue
        node = window.getProperty("XAccessible")  # toolkit windows hand out their XAccessible as a property
        stack = [node.getAccessibleContext() if node is not None else None]
        while stack:
            context = stack.pop()
            if context is None or not context.getAccessibleStateSet() & showing:
                continue
            if context.getAccessibleRole() not in skip and context.getAccessibleName():
                names.append(context.getAccessibleName())
            stack.extend(context.getAccessibleChild(i).getAccessibleContext()
                         for i in range(min(context.getAccessibleChildCount(), 400)))
    return names


def check_language(h, c, lang):
    advanced, prompts = EXPECTED[lang]
    doc = h.new_document()
    dlg = open_find(h)
    for tab, title in ((TAB_FIND, "Find"), (TAB_REPLACE, "Replace"), (TAB_GOTO, "Go To")):
        select_tab(dlg, tab, "hsttabs")
        h.wait_idle(0.5)
        names = dialog_names(h)
        if tab != TAB_GOTO:
            c.equal(f"{lang} {title}: the expander reads {advanced}", advanced in names, True)
        c.equal(f"{lang} {title}: no shown label has a literal _", [n for n in names if "_" in n], [])
    for place, raw in prompts.items():
        select_entry(dlg, "hstgotowhat", place)
        text = state(dlg.getChild("hstgotoprompt")).get("Text", "")
        c.equal(f"{lang} Go To prompt {place}: shown without _", text.replace("~", "", 1), raw.replace("~", "", 1))
        c.equal(f"{lang} Go To prompt {place}: access key kept as in the .ui", text, raw)
    dlg.getChild("close").executeAction("CLICK", ())
    h.wait_idle()
    h.close_document(doc)


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--instdir", default=os.path.join(ROOT, "upstream/libreoffice/instdir"))
    parser.add_argument("--work", default=os.path.join(ROOT, "tests/output/find-replace-labels"))
    parser.add_argument("--port", type=int, default=0, help="UNO socket of the office (default: a free port)")
    parser.add_argument("--display", default=":86")
    parser.add_argument("--ui", nargs="*", choices=sorted(EXPECTED), default=sorted(EXPECTED, reverse=True))
    args = parser.parse_args()
    checks = Checks()
    for lang in args.ui:
        harness = DialogHarness(args.instdir, os.path.join(args.work, lang), args.port or free_port(), args.display, ui=lang)
        try:
            check_language(harness, checks, lang)
        except Exception as error:  # noqa: BLE001 - one language is reported; the other still runs
            checks.error(lang, error)
            harness.discard_documents()
        finally:
            harness.close()
    return checks.finish()


if __name__ == "__main__":
    sys.exit(main())
