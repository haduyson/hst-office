#!/usr/bin/env python3
# SPDX-License-Identifier: AGPL-3.0-only
""""Đặt làm mặc định" (Set As Default) in Writer's Paragraph and Font dialogs and in Sheets' Format Cells.

Usage: check-set-as-default.py [--instdir DIR] [--work DIR] [--port N]
Needs a built instdir with the vi language pack. Runs headless (svp) with a fresh profile, then restarts the
office on the same profile, as a user closing and reopening HST Office would:
- Paragraph: Justified + 1.5 lines, Set As Default for all new documents -> this document has them, and after
  a restart a new document (what Ctrl+N, Start Center "Văn bản" and the HST Writer launcher open) starts with them.
- Font: 14 pt for this document only -> this document has it, new documents keep their size.
- Format Cells: centered for all new spreadsheets -> after the restart a new spreadsheet's A1 is centered.
"""
import argparse
import os
import sys
import threading
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from hst_dialog_uitest import Checks, DialogHarness, click, has_child, select_entry, state, type_value  # noqa: E402
from hst_gui import free_port  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
BLOCK, CENTER_CELL = 2, 2  # style.ParagraphAdjust.BLOCK, table.CellHoriJustify.CENTER


def set_as_default(h, c, dlg, scope, label):
    """Set As Default runs the scope question inside the click, so the click gets its own thread."""
    c.equal(f"{label}: button shown", state(dlg.getChild("hstsetdefault")).get("ReallyVisible"), "true")
    clicker = threading.Thread(target=click, args=(dlg, "hstsetdefault"), daemon=True)
    clicker.start()
    question = None
    for _ in range(60):
        top = h.ui.getTopFocusWindow()
        if state(top).get("ID") == "HstDefaultScopeDialog":
            question = top
            break
        time.sleep(0.25)
    assert question is not None, f"{label}: the scope question did not open"
    c.equal(f"{label}: all new documents preselected", state(question.getChild("newdocs")).get("Checked"), "true")
    click(question, scope)
    click(question, "ok")
    clicker.join(30)
    h.wait_idle(2)


def first_paragraph(doc):
    return doc.getText().createEnumeration().nextElement()


def template_on_disk(h, module, ext):
    path = os.path.join(h.office.workdir, "profile", "user", "hst", "default-templates", f"{module}.{ext}")
    return os.path.isfile(path)


def before_restart(h, c):
    doc = h.new_document()
    doc.getText().setString("Văn bản kiểm tra đặt làm mặc định.")
    h.wait_idle()
    dlg = h.open_dialog(".uno:ParagraphDialog", "ParagraphPropertiesDialog")
    select_entry(dlg, "comboLB_HST_ALIGN", 3)  # Justified
    select_entry(dlg, "comboLB_LINEDIST", 2)  # 1.5 lines
    set_as_default(h, c, dlg, "newdocs", "paragraph")
    para = first_paragraph(doc)
    c.equal("paragraph: this document justified", int(para.ParaAdjust), BLOCK)
    c.equal("paragraph: this document 1.5 lines", para.ParaLineSpacing.Height, 150)
    c.equal("paragraph: default template written", template_on_disk(h, "swriter", "ott"), True)
    h.close_document(doc)

    doc = h.new_document()
    doc.getText().setString("Chỉ tài liệu này.")
    h.wait_idle()
    dlg = h.open_dialog(".uno:FontDialog", "CharacterPropertiesDialog")
    type_value(dlg, "cbWestSize", "14")
    set_as_default(h, c, dlg, "thisdoc", "font")
    c.equal("font: this document 14 pt", first_paragraph(doc).CharHeight, 14.0)
    h.close_document(doc)

    sheet = h.new_document("scalc")
    sheet.getSheets().getByIndex(0).getCellByPosition(0, 0).setString("A1")
    h.wait_idle()
    dlg = h.open_dialog(".uno:FormatCellDialog", "FormatCellsDialog")
    pages = dlg.getChild("tabcontrol")
    for pos in range(int(state(pages)["PageCount"])):
        dlg.getChild("tabcontrol").executeAction("SELECT", (prop("POS", str(pos)),))
        if has_child(dlg, "comboboxHorzAlign"):
            break
    select_entry(dlg, "comboboxHorzAlign", 2)  # Center
    set_as_default(h, c, dlg, "newdocs", "format cells")
    c.equal("format cells: default template written", template_on_disk(h, "scalc", "ots"), True)
    h.close_document(sheet)


def after_restart(h, c):
    doc = h.new_document()
    para = first_paragraph(doc)
    c.equal("restart: new document justified", int(para.ParaAdjust), BLOCK)
    c.equal("restart: new document 1.5 lines", para.ParaLineSpacing.Height, 150)
    c.equal("restart: font set for one document only stays out", para.CharHeight != 14.0, True)
    h.close_document(doc)
    sheet = h.new_document("scalc")
    cell = sheet.getSheets().getByIndex(0).getCellByPosition(0, 0)
    c.equal("restart: new spreadsheet centered", int(cell.HoriJustify), CENTER_CELL)
    h.close_document(sheet)


def prop(name, value):
    from com.sun.star.beans import PropertyValue
    result = PropertyValue()
    result.Name, result.Value = name, value
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--instdir", default=os.path.join(ROOT, "upstream/libreoffice/instdir"))
    parser.add_argument("--work", default=os.path.join(ROOT, "tests/output/set-as-default"))
    parser.add_argument("--port", type=int, default=0)
    args = parser.parse_args()
    checks = Checks()
    harness = DialogHarness(args.instdir, args.work, args.port or free_port(), ":79")
    try:
        try:
            before_restart(harness, checks)
        except Exception as error:  # noqa: BLE001 - reported; the restart part still runs
            checks.error("before restart", error)
            harness.discard_documents()
        harness.office.stop()
        harness.office.start(fresh=False)
        harness.ui = harness.office.service("com.sun.star.ui.test.UITest")
        harness.office.load("private:factory/swriter")  # kept open, as DialogHarness does at its start
        try:
            after_restart(harness, checks)
        except Exception as error:  # noqa: BLE001
            checks.error("after restart", error)
            harness.discard_documents()
    finally:
        harness.close()
    return checks.finish()


if __name__ == "__main__":
    sys.exit(main())
