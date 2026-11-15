#!/usr/bin/env python3
# SPDX-License-Identifier: AGPL-3.0-only
"""Tài liệu chưa lưu on Linux: a document closed without saving keeps its last recovery copy for 7 days.

Usage: python3 tests/runtime/check-unsaved-documents.py --instdir <instdir> [--out tests/output/unsaved-documents]
           [--display :97]

A new Writer document gets its first recovery copy (30 s), is closed without saving: user/hst-unsaved holds the copy
and its description (title), which the extension lists (unsaved_store) and opens as a new untitled document with the
text. A kept copy whose time is 8 days old is removed at the next start; the backup folder keeps no copy of the closed
document. The dialog itself (org.hst.office.vi:UnsavedDocuments) is opened once and closed. The X display must already
run. Exit 1 when a check fails.
"""
import argparse
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path[:0] = [HERE, os.path.join(os.path.dirname(os.path.dirname(HERE)), "extensions", "hst-vietnamese-tools", "python")]
import hst_gui  # noqa: E402
import recovery_runtime as rr  # noqa: E402
from recovery_runtime import record  # noqa: E402

PORT = 22233


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--instdir", required=True)
    ap.add_argument("--out", default=os.path.join(hst_gui.ROOT, "tests", "output", "unsaved-documents"))
    ap.add_argument("--display", default=":97")
    args = ap.parse_args()
    os.makedirs(args.out, exist_ok=True)
    hst_gui.setup_uno(args.instdir)
    from hst_office import unsaved_store as store
    off = rr.office(args.instdir, os.path.join(args.out, "work"), PORT, args.display)
    off.start()
    folder = store.store_dir(rr.user_dir(off))
    doc = rr.new_document(off, "writer", "CHUA-LUU-GIU-LAI")
    record("a recovery copy within 45 s", rr.wait(lambda: rr.copies(off), 45, 1), rr.backups(off))
    title = doc.Title
    doc.close(True)  # the "Không lưu" answer: closed while modified
    kept = rr.wait(lambda: store.list_kept(folder), 10)
    record("the closed document is kept", kept, os.listdir(folder) if os.path.isdir(folder) else "no folder")
    record("its title is recorded", kept and kept[0].title == title, kept)
    record("the backup folder keeps no copy of it", not rr.copies(off), rr.backups(off))
    if kept:
        store_doc = off.desktop().loadComponentFromURL("file://" + kept[0].path, "_default", 0,
                                                       (_prop("AsTemplate", True),))
        record("Mở opens it as a new untitled document with the text",
               store_doc is not None and "CHUA-LUU-GIU-LAI" in rr.text_of(store_doc) and not store_doc.hasLocation())
        # the menu entry runs in the window of the opened copy (--nodefault: no other window is left)
        frame = store_doc.getCurrentController().getFrame()
        import threading
        threading.Thread(target=lambda: off.dispatch(frame, "org.hst.office.vi:UnsavedDocuments"), daemon=True).start()
        shown = rr.wait(lambda: [w for w in hst_gui.toplevels(off.display, off.pid) if w[1] == "Tài liệu chưa lưu"], 20)
        record("the dialog Tài liệu chưa lưu opens", shown)
        if shown:
            hst_gui.send_close_request(shown[0][0], off.display)
            rr.wait(lambda: not [w for w in hst_gui.toplevels(off.display, off.pid) if w[1] == "Tài liệu chưa lưu"], 10)
        store_doc.setModified(False)
        store_doc.close(True)
        # age it: the description says it was closed 8 days ago
        with open(kept[0].info, "a", encoding="utf-8") as handle:
            handle.write("closed\t%d\n" % (time.time() - 8 * 86400))
        old = time.time() - 8 * 86400
        for path in (kept[0].path, kept[0].info):
            os.utime(path, (old, old))
    rr.finish(off)
    off.start(fresh=False)
    time.sleep(5)
    record("an 8-day-old kept document is removed at the next start", not store.list_kept(folder, now=0),
           os.listdir(folder) if os.path.isdir(folder) else [])
    rr.finish(off)
    return rr.summary("unsaved documents runtime")


def _prop(name, value):
    from com.sun.star.beans import PropertyValue
    prop = PropertyValue()
    prop.Name, prop.Value = name, value
    return prop


if __name__ == "__main__":
    sys.exit(main())
