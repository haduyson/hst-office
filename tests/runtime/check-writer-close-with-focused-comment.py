#!/usr/bin/env python3
# SPDX-License-Identifier: LicenseRef-HST-Proprietary
# Copyright (C) 2026 HASON TECH
"""Writer: a content control, a comment left in edit mode (its window has the focus), a PDF export with the comments
in the margin, then XCloseable.close: the office must survive (Linux X display).

1.0.2 crashed in the close (SIGSEGV in SwPostItMgr::HasActiveSidebarWin from SwEditWin::GetFocus): the view destroys
its comment manager, the focused comment window gives the focus back to the document window, whose GetFocus asked
the comment manager that was gone. It needs the document window to have the X input focus (given with xdotool here,
as a window manager would); 1.0.2 then crashed within 3 rounds. The headless unit test does not get there.
Usage: <office python> check-writer-close-with-focused-comment.py --instdir DIR --out DIR [--display :N] [--rounds N]
Exit 1 when the office goes away.
"""
import argparse, os, subprocess, sys, time  # noqa: E401

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import hst_gui  # noqa: E402


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--instdir", required=True)
    parser.add_argument("--out", required=True)
    parser.add_argument("--display", default=os.environ.get("DISPLAY", ":97"))
    parser.add_argument("--rounds", type=int, default=5)
    args = parser.parse_args()
    out = os.path.abspath(args.out)
    os.makedirs(out, exist_ok=True)
    hst_gui.setup_uno(args.instdir)
    import uno
    from com.sun.star.beans import PropertyValue

    def prop(name, value):
        item = PropertyValue()
        item.Name, item.Value = name, value
        return item

    office = hst_gui.Office(args.instdir, os.path.join(out, "work"), hst_gui.free_port(), display=args.display,
                            lang="en_US.UTF-8")
    office.start()
    alive = True
    try:
        for round_ in range(args.rounds):
            doc = office.load("private:factory/swriter")
            time.sleep(3)
            frame = doc.getCurrentController().getFrame()
            office.dispatch(frame, ".uno:InsertContentControl")
            office.dispatch(frame, ".uno:GoToEndOfDoc")
            office.dispatch(frame, ".uno:InsertAnnotation")  # the comment stays in edit mode, with the focus
            time.sleep(2)
            # as on a desktop, the document window has the input focus (bare X server: no window manager gives it)
            env = dict(os.environ, DISPLAY=args.display)
            for wid in subprocess.run(["xdotool", "search", "--onlyvisible", "--pid", str(office.pid), "--name", "HST"],
                                      env=env, capture_output=True, text=True).stdout.split():
                subprocess.run(["xdotool", "windowfocus", "--sync", wid], env=env, capture_output=True, timeout=10)
            time.sleep(1)
            filter_data = (prop("ExportFormFields", True), prop("ExportNotes", False),
                           prop("ExportNotesInMargin", True))
            store_args = (prop("FilterName", "writer_pdf_Export"),
                          prop("FilterData", uno.Any("[]com.sun.star.beans.PropertyValue", filter_data)))
            uno.invoke(doc, "storeToURL", (uno.systemPathToFileUrl(os.path.join(out, f"round{round_}.pdf")),
                                           uno.Any("[]com.sun.star.beans.PropertyValue", store_args)))
            try:
                doc.close(True)
                time.sleep(2)
                alive = office.desktop().getComponents() is not None
            except Exception as error:  # noqa: BLE001 - the bridge goes away when the office crashes
                print(f"close: {type(error).__name__}", flush=True)
                alive = False
            print(("PASS  " if alive else "FAIL  ") + f"round {round_ + 1}: the office survives closing the document",
                  flush=True)
            if not alive:
                break
    finally:
        if alive:
            office.stop()
    return 0 if alive else 1


if __name__ == "__main__":
    sys.exit(main())
