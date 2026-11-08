# SPDX-License-Identifier: AGPL-3.0-only
"""The Slides animation gallery and .uno:HstApplyAnimation (gtk3, vi_VN).

Usage: python3 tests/runtime/check-slides-animation-gallery.py [--instdir DIR] [--display :71] [--out DIR]

Creates one slide with two rectangles and a two-paragraph text box. Checks dispatcher application,
state, undo/redo, replacement, multi-selection WITH_PREVIOUS, None, disabled empty selection,
mixed state, unknown ids, and the text-group rule. Reads the actual UNO main animation sequence.
If the notebookbar contains the command, also checks click/Enter, paging, accessible class labels,
and the deck button, and saves gallery.png. Writes evidence.json; exit 1 on a failed check.
Run on S6's private build, after its component registry has been refreshed.
"""
import argparse
import json
import os
import socket
import subprocess
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import hst_gui  # noqa: E402
from slides_animation_gallery_screen import check_gallery_on_screen  # noqa: E402
from slides_animation_gallery_uno import (ROWS, dispatch, effects, make_slide, record,  # noqa: E402
                                          select, settled_effects, state_of)

PORT = 7463


def check_dispatcher(office, doc, page, shapes):
    from com.sun.star.presentation.EffectNodeType import ON_CLICK, WITH_PREVIOUS
    first, second, text = shapes
    undo = doc.getUndoManager()
    select(office, doc, first)
    undo.clear()
    doc.setModified(False)
    dispatch(office, doc, "ooo-entrance-fly-in")
    current = settled_effects(page)
    record("1. fly-in applies to one selected rectangle", len(current) == 1
           and current[0]["id"] == "ooo-entrance-fly-in" and current[0]["targets"] == [first.getName()], current)
    record("7. command state reports the preset id", state_of(office, doc) == (True, "ooo-entrance-fly-in"),
           state_of(office, doc))
    record("application modifies the document", doc.isModified())
    titles = undo.getAllUndoActionTitles()
    undo.undo()
    removed = settled_effects(page)
    record("2. one undo action restores the empty sequence", len(titles) == 1 and not removed, (titles, removed))
    undo.redo()
    record("redo restores the effect", settled_effects(page) == current)
    undo.clear()
    dispatch(office, doc, "ooo-exit-fade-out")
    replaced = settled_effects(page)
    record("3. fade-out replaces fly-in", len(replaced) == 1 and replaced[0]["id"] == "ooo-exit-fade-out"
           and replaced[0]["targets"] == [first.getName()], replaced)
    titles = undo.getAllUndoActionTitles()
    undo.undo()
    record("replacement is one undo action restoring fly-in", len(titles) == 1 and settled_effects(page) == current)
    undo.redo()
    settled_effects(page)
    select(office, doc, first, second)
    record("different selected shapes report mixed state", state_of(office, doc) == (True, ""), state_of(office, doc))
    undo.clear()
    dispatch(office, doc, "ooo-entrance-fly-in")
    paired = settled_effects(page)
    record("4. two shapes get ordered effects, second WITH_PREVIOUS", len(paired) == 2
           and [e["id"] for e in paired] == ["ooo-entrance-fly-in"] * 2
           and [e["targets"] for e in paired] == [[first.getName()], [second.getName()]]
           and [e["node_type"] for e in paired] == [ON_CLICK, WITH_PREVIOUS], paired)
    titles = undo.getAllUndoActionTitles()
    undo.undo()
    record("multi-shape replacement is one undo action", len(titles) == 1 and settled_effects(page) == replaced)
    undo.redo()
    settled_effects(page)
    undo.clear()
    dispatch(office, doc, "None")
    removed = settled_effects(page)
    record("5. None removes both shapes' effects", not removed and state_of(office, doc) == (True, "None"), removed)
    titles = undo.getAllUndoActionTitles()
    undo.undo()
    record("None is one undo action restoring both effects", len(titles) == 1 and settled_effects(page) == paired)
    undo.redo()
    settled_effects(page)
    undo.clear()
    dispatch(office, doc, "no-such-animation")
    record("unknown preset leaves effects and undo unchanged", not settled_effects(page)
           and not undo.getAllUndoActionTitles())
    select(office, doc)
    state = state_of(office, doc)
    dispatch(office, doc, "ooo-entrance-fly-in")
    record("6. empty selection disables the command and changes nothing", state is not None and not state[0]
           and not settled_effects(page) and not undo.getAllUndoActionTitles(), state)
    select(office, doc, text)
    undo.clear()
    dispatch(office, doc, "ooo-entrance-appear")
    grouped = settled_effects(page)
    record("a lone unfilled text box animates by paragraph", len(grouped) == 2
           and all(e["id"] == "ooo-entrance-appear" and e["targets"] == [text.getName()] for e in grouped)
           and sorted(p for e in grouped for p in e["paragraphs"]) == [0, 1], grouped)
    dispatch(office, doc, "ooo-exit-fade-out")
    grouped = settled_effects(page)
    record("text replacement removes all previous paragraph effects", len(grouped) == 2
           and all(e["id"] == "ooo-exit-fade-out" for e in grouped), grouped)
    dispatch(office, doc, "None")
    record("None removes paragraph targets too", not settled_effects(page))
    select(office, doc, first)
    undo.clear()
    # No sleeps between these mutations: UndoAnimation must never clone a stale timer-backed tree.
    dispatch(office, doc, "ooo-entrance-appear")
    dispatch(office, doc, "ooo-exit-fade-out")
    titles = undo.getAllUndoActionTitles()
    undo.undo()
    immediate = effects(page)
    record("consecutive dispatches keep separate undo snapshots", len(titles) == 2 and len(immediate) == 1
           and immediate[0]["id"] == "ooo-entrance-appear", immediate)
    undo.redo()
    immediate = effects(page)
    record("immediate redo restores the replacement", len(immediate) == 1
           and immediate[0]["id"] == "ooo-exit-fade-out", immediate)
    undo.undo()
    undo.undo()
    record("immediate undo restores the original empty sequence", not effects(page))
    undo.clear()


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--instdir", default=os.path.join(hst_gui.ROOT, "upstream/libreoffice/instdir"))
    parser.add_argument("--display", default=":71")
    parser.add_argument("--out", default=os.path.join(hst_gui.ROOT, "tests/output/slides-animation-gallery"))
    args = parser.parse_args()
    args.instdir, args.out = os.path.abspath(args.instdir), os.path.abspath(args.out)
    os.makedirs(args.out, exist_ok=True)
    if os.geteuid() == 0:
        subprocess.run(["chown", "-R", hst_gui.BUILD_USER, args.out], check=True)
        os.execvp("runuser", ["runuser", "-u", hst_gui.BUILD_USER, "--", "dbus-run-session", "--", sys.executable] + sys.argv)
    os.environ.update(NO_AT_BRIDGE="0", GTK_MODULES="gail:atk-bridge")
    hst_gui.setup_uno(args.instdir)
    office = hst_gui.Office(args.instdir, args.out, PORT, display=args.display,
                            config=[("/org.openoffice.Office.Impress/Misc/NewDoc", "AutoPilot", "false")])
    try:
        with socket.socket() as probe:
            probe.settimeout(1)
            if probe.connect_ex(("127.0.0.1", PORT)) == 0:
                raise RuntimeError(f"UNO port {PORT} is already in use; stop its owned instance before retrying")
        office.start()
        doc = office.load("private:factory/simpress")
        time.sleep(6)
        page, shapes = make_slide(doc)
        check_dispatcher(office, doc, page, shapes)
        check_gallery_on_screen(office, doc, page, args)
    except Exception as error:  # noqa: BLE001
        record("crashed", False, repr(error))
    finally:
        if office.proc is not None:
            office.stop()
    with open(os.path.join(args.out, "evidence.json"), "w", encoding="utf-8") as handle:
        json.dump(ROWS, handle, ensure_ascii=False, indent=1)
    failed = sum(r["status"] == "FAIL" for r in ROWS)
    print(f"{len(ROWS)} checks, {failed} failed")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
