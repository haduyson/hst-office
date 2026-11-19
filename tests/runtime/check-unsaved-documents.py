#!/usr/bin/env python3
# SPDX-License-Identifier: AGPL-3.0-only
"""Tài liệu chưa lưu on Linux: a document closed without saving keeps its last recovery copy for 7 days.

Usage: python3 tests/runtime/check-unsaved-documents.py --instdir <instdir> [--out tests/output/unsaved-documents]
           [--display :97]

A new Writer document gets its first recovery copy (30 s), is closed without saving: user/hst-unsaved holds the copy
and its description (title), which the extension lists (unsaved_store) and opens as a new untitled document with the
text. The dialog (org.hst.office.vi:UnsavedDocuments) opens from its three entries: the command itself, the Info page
of the File panel (button "Tài liệu chưa lưu") and the Start Center's menu item (nav_unsaved), where it lists the kept
document. A kept copy whose time is 8 days old is removed at the next start; the backup folder keeps no copy of the
closed document. The X display must already run; as root the check re-executes itself as the build user under a
session bus of its own, with a private AT-SPI bus. Exit 1 when a check fails.
"""
import argparse
import importlib.util
import os
import signal
import subprocess
import sys
import threading
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path[:0] = [HERE, os.path.join(os.path.dirname(os.path.dirname(HERE)), "extensions", "hst-vietnamese-tools", "python")]
import hst_gui  # noqa: E402
import recovery_runtime as rr  # noqa: E402
from recovery_runtime import record  # noqa: E402

PORT = 22233
DIALOG = "Tài liệu chưa lưu"  # the dialog's title, the File panel's button and the Start Center's menu item


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--instdir", required=True)
    ap.add_argument("--out", default=os.path.join(hst_gui.ROOT, "tests", "output", "unsaved-documents"))
    ap.add_argument("--display", default=":97")
    args = ap.parse_args()
    os.makedirs(args.out, exist_ok=True)
    if os.geteuid() == 0:  # as the build user under a session bus of its own (AT-SPI needs one)
        subprocess.run(["chown", "-R", hst_gui.BUILD_USER, args.out], check=False)
        os.execvp("runuser", ["runuser", "-u", hst_gui.BUILD_USER, "--", "dbus-run-session", "--", sys.executable]
                  + sys.argv)
    address, launcher = private_atspi_bus()
    os.environ.update(NO_AT_BRIDGE="0", GTK_MODULES="gail:atk-bridge", AT_SPI_BUS_ADDRESS=address)
    try:
        return run(args)
    finally:
        try:
            os.kill(launcher, signal.SIGTERM)
        except ProcessLookupError:
            pass


def run(args):
    hst_gui.setup_uno(args.instdir)
    import backstage_gui as gui  # noqa: PLC0415 - needs the UNO path set up
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
    else:  # the entry points are still checked, in a new document
        store_doc = off.desktop().loadComponentFromURL("private:factory/swriter", "_default", 0, ())
    check_entries(off, gui, store_doc, title if kept else None)
    if kept:
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


def check_entries(off, gui, doc, title):
    """The dialog opens from its three entries: the command, the File panel's Thông tin page and the Start Center's
    menu item; with a kept document (title), the dialog lists it. doc is the only open document (--nodefault)."""
    frame = doc.getCurrentController().getFrame()
    threading.Thread(target=lambda: off.dispatch(frame, "org.hst.office.vi:UnsavedDocuments"), daemon=True).start()
    record("the command opens the dialog Tài liệu chưa lưu", dialog_shown(off))
    # the File panel: Thông tin › Tài liệu chưa lưu
    gui.reopen(off, frame)
    info = gui.view_items().get("Thông tin")
    record("the File panel has its Thông tin page", info is not None and gui.press(info))
    time.sleep(0.8)
    button = gui.view_items().get(DIALOG)
    record("the Thông tin page has the button Tài liệu chưa lưu", button is not None, sorted(gui.view_items())[:40])
    if button is not None:
        gui.press(button)
        record("the File panel's button opens the dialog", dialog_shown(off))
    # the Start Center: closing the last document (Close, as the File menu does) shows it in the same window
    doc.setModified(False)
    off.dispatch(frame, ".uno:CloseDoc")
    item = rr.wait(lambda: start_center_item(gui), 20)
    record("the Start Center's menu has the item Tài liệu chưa lưu", item)
    if item:
        gui.press(item)
        names = rr.wait(lambda: dialog_names(gui), 20)
        record("the Start Center's item opens the dialog", names is not None)
        if title is not None:
            record("the dialog lists the kept document", names is not None and any(title in n for n in names),
                   (names or [])[:30])
        dialog_shown(off)


def dialog_shown(off):
    """True when the dialog Tài liệu chưa lưu shows; it is closed again before the answer."""
    shown = rr.wait(lambda: [w for w in hst_gui.toplevels(off.display, off.pid) if w[1] == DIALOG], 20)
    if shown:
        hst_gui.send_close_request(shown[0][0], off.display)
        rr.wait(lambda: not [w for w in hst_gui.toplevels(off.display, off.pid) if w[1] == DIALOG], 10)
    return bool(shown)


def start_center_item(gui):
    """The Start Center's showing menu item Tài liệu chưa lưu (a push button of the new Start Center's left column)."""
    for role, name, node in gui.showing(gui.walk(gui.nd30.office_app(), [])):
        if role == "push button" and name == DIALOG and not gui.is_open():
            return node
    return None


def dialog_names(gui):
    """The names inside the showing dialog Tài liệu chưa lưu, or None while it does not show."""
    for role, name, node in gui.walk(gui.nd30.office_app(), []):
        if role in ("dialog", "frame") and name == DIALOG:
            return [n for _r, n, _node in gui.walk(node, []) if n]
    return None


def private_atspi_bus():
    """This run's own AT-SPI bus, as check-banner-everywhere.py sets it up (that file's name is not importable)."""
    spec = importlib.util.spec_from_file_location("banner_everywhere", os.path.join(HERE, "check-banner-everywhere.py"))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.private_atspi_bus()


def _prop(name, value):
    from com.sun.star.beans import PropertyValue
    prop = PropertyValue()
    prop.Name, prop.Value = name, value
    return prop


if __name__ == "__main__":
    sys.exit(main())
