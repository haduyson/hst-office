#!/usr/bin/env python3
# SPDX-License-Identifier: AGPL-3.0-only
"""HST Writer commands with the cursor or selection anywhere (error report: "RuntimeException: no text selection" from
the view cursor while cells, a picture, frame, shape or comment were selected): on the real build, every scenario of
nd30_insertion_scenarios gets the expected ND30 decision, the HST commands (ND30 wizard, TCVN3/VNI conversion, number
to words) run through actions with a captured message box and never raise, and a cursor in a table of the main text
gets the document right after that table in one undo step.

Usage: <office>/program/python tests/runtime/check-nd30-insertion-point.py --display :173 --instdir <instdir>
       [--out DIR] [--port 2307]
The display must already run; it is never started or stopped here. Exit 1 on failure.
"""
import argparse
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path[:0] = [HERE, os.path.join(os.path.dirname(os.path.dirname(HERE)), "extensions/hst-vietnamese-tools/python")]
import hst_gui  # noqa: E402

ROWS = []
EXPECTED = {"plain_body": [], "table_cell": [], "table_cells_selected": [], "nested_table_cell": [],
            "table_last_in_document": [], "table_cell_text_selected": ["selection"], "text_selected": ["selection"],
            "multi_selection": ["selection"], "image_selected": ["not-text-cursor"], "shape_selected": ["not-text-cursor"],
            "frame_selected": ["not-text-cursor"], "comment_editing": ["not-text-cursor"], "inside_frame": ["not-body-text"],
            "header": ["not-body-text"], "footer": ["not-body-text"], "footnote": ["not-body-text"],
            "protected_section": ["protected-cursor"], "read_only": ["read-only"]}
AFTER_TABLE = {"table_cell", "table_cells_selected", "nested_table_cell", "table_last_in_document"}


def check(name, ok, detail=""):
    ROWS.append(bool(ok))
    print("%s  %s  %s" % ("PASS" if ok else "FAIL", name, str(detail)[:240]), flush=True)


def elements(doc):
    """Kinds of the main text's elements: 'T:<name>' for a table, the text for a paragraph."""
    out, paragraphs = [], doc.getText().createEnumeration()
    while paragraphs.hasMoreElements():
        el = paragraphs.nextElement()
        out.append("T:" + el.getName() if el.supportsService("com.sun.star.text.TextTable") else el.getString())
    return out


def run_command(ctx, actions, command, doc, wizard_choice=None):
    """Run an HST command as the dispatcher does, its dialogs answered (the ND30 wizard with `wizard_choice`, the
    others cancelled) and its messages captured; returns (messages, exception or None)."""
    from hst_office import number_words_action
    from hst_office.data_files import load_locale
    host = actions.Host(ctx, doc.getCurrentController().getFrame(), load_locale("vi"))
    said = []
    host.say = lambda text, error=False: said.append(text)
    dialogs = (actions.Nd30Wizard, actions.ConvertWizard, number_words_action.NumberWordsDialog)
    saved = [d.run for d in dialogs]
    for dialog in dialogs:
        dialog.run = (lambda self, peer: wizard_choice) if dialog is actions.Nd30Wizard else (lambda self, peer: None)
    try:
        command(host)
        return said, None
    except Exception as exc:  # noqa: BLE001 - the failure under test
        return said, exc
    finally:
        for dialog, run in zip(dialogs, saved):
            dialog.run = run


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--display", required=True)
    parser.add_argument("--instdir", default=os.path.join(hst_gui.ROOT, "upstream/libreoffice/instdir"))
    parser.add_argument("--out", default=os.path.join(hst_gui.ROOT, "tests/output/nd30-insertion-point"))
    parser.add_argument("--port", type=int, default=2307)
    args = parser.parse_args()
    out = os.path.abspath(args.out)
    os.makedirs(out, exist_ok=True)
    hst_gui.setup_uno(args.instdir)
    office = hst_gui.Office(args.instdir, os.path.join(out, "office"), args.port, display=args.display).start()
    try:
        import nd30_insertion_scenarios as scenarios
        from hst_office import actions, nd30_insertion
        from hst_office.data_files import load_locale
        blockers = load_locale("vi")["blockers"]
        choice = {"type": "cong-van", "fields": {}, "apply_page": False, "page_numbers": False, "duplex": False}
        for make in scenarios.SCENARIOS:
            name, want = make.__name__, EXPECTED[make.__name__]
            doc = make(office)
            got = nd30_insertion.insertion_point(doc, doc.getCurrentController())["reasons"]
            check("%s: ND30 decision %s" % (name, want), got == want, got)
            before = elements(doc)
            said, exc = run_command(office.ctx, actions, actions.nd30_wizard, doc, choice)
            check("%s: ND30 wizard command does not raise" % name, exc is None, exc)
            if want:
                check("%s: the user is told what to do" % name, said == ["\n".join(blockers[r] for r in want)], said)
                check("%s: nothing written" % name, elements(doc) == before)
            else:
                after = elements(doc)
                check("%s: inserted" % name, len(after) > len(before) and said and said[-1].startswith("Đã chèn"), said)
            if name in AFTER_TABLE:
                tables = [e for e in before if e.startswith("T:")]
                check("%s: the user's table is untouched and first, the document follows it" % name,
                      after[0] == before[0] == tables[0] and len([e for e in after if e.startswith("T:")]) > len(tables)
                      and "Văn bản được chèn ngay sau bảng" in said[-1], after[:3])
                doc.getUndoManager().undo()
                check("%s: one undo removes it" % name, elements(doc) == before, elements(doc)[:3])
            for label, command in (("convert encoding", actions.convert_encoding), ("number to words", actions.COMMANDS["NumberToWords"])):
                said, exc = run_command(office.ctx, actions, command, doc)
                check("%s: %s does not raise" % (name, label), exc is None, exc)
            scenarios.close(doc)
    finally:
        office.stop()
    print("PASS" if all(ROWS) else "FAIL", flush=True)
    return 0 if all(ROWS) else 1


if __name__ == "__main__":
    sys.exit(main())
