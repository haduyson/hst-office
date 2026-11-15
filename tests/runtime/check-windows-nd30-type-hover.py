#!/usr/bin/env python3
# SPDX-License-Identifier: AGPL-3.0-only
"""ND30 "Văn bản hành chính": the open "Loại văn bản" list follows the pointer on Windows, with real mouse input.

The wizard of the INSTALLED extension is run as check-nd30-type-list.py (Linux) runs it; the arrow is clicked with
SendInput, then the pointer moves over several rows of the open list (FloatingWindow, wizard_type_popup) and the
highlighted row is read back from the list itself (XListBox.getSelectedItemPos) after each move. A dropdown moves its
highlight under the pointer; the picker's list must do the same. Down then moves it from the keyboard, as before.

Usage: "<install>\\program\\python.exe" tests/runtime/check-windows-nd30-type-hover.py --install DIR --out DIR
[--port 2118]. Screenshots: <out>/hover-row<N>.png. Exit 1 on any FAIL.
"""
import argparse
import os
import sys
import threading
import time

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import windows_gui as wg  # noqa: E402


def row_boxes(listbox):
    """{row index: (x, y, w, h)} of the list's shown rows, relative to the list, from its accessible rows."""
    boxes = {}
    try:
        rows = listbox.getAccessibleContext().getAccessibleChild(0).getAccessibleContext()
        for index in range(min(rows.getAccessibleChildCount(), 300)):
            item = rows.getAccessibleChild(index).getAccessibleContext()
            if not wg.showing(item):
                continue
            box = item.getBounds()
            if box.Height > 0:
                # item bounds are relative to the inner list, which sits in the list control's border
                origin = rows.getLocation()
                boxes[item.getAccessibleIndexInParent()] = (origin.X + box.X, origin.Y + box.Y, box.Width, box.Height)
    except Exception:  # noqa: BLE001 - no accessible rows: the caller reports it
        pass
    return boxes


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--install", required=True)
    parser.add_argument("--out", required=True)
    parser.add_argument("--port", type=int, default=2118)
    args = parser.parse_args()
    out, install = os.path.abspath(args.out), os.path.abspath(args.install)
    sys.path.insert(0, os.path.join(install, "share", "extensions", "hst-vietnamese-tools", "python"))
    check = wg.Results(out, "nd30-type-hover")
    office = wg.WinOffice(install, os.path.join(out, "profile"), args.port, os.path.join(out, "logs"))
    try:
        office.start(fresh=True)
        check.note("start-up dialog closed first", wg.dismiss_startup(office, os.path.join(out, "startup-dialog.png")))
        from hst_office import data_files, wizard_nd30
        doc = office.load("private:factory/swriter")
        wizard = wizard_nd30.Nd30Wizard(office.ctx, data_files.load_locale("vi"))
        peer = doc.getCurrentController().getFrame().getContainerWindow()
        thread = threading.Thread(target=lambda: wizard.run(peer), daemon=True)
        thread.start()
        for _ in range(60):
            time.sleep(1)
            if wizard.picker.handler and wizard.d.dialog.getPeer():
                break
        time.sleep(2)
        dialog, picker = wizard.d.dialog, wizard.picker
        hwnd = wg.hwnd_of(wizard.d.model.Title, timeout=20)
        check("the wizard window is on screen", hwnd is not None, wizard.d.model.Title)
        if hwnd is None:
            raise RuntimeError("wizard window not found")
        check.note("foreground", wg.foreground(hwnd))
        ox, oy = wg.client_origin(hwnd)
        arrow = dialog.getControl("typeOpen").getPeer().getPosSize()
        wg.click(ox + arrow.X + arrow.Width // 2, oy + arrow.Y + arrow.Height // 2)
        time.sleep(1.5)
        check("a real click on the arrow opens the list", picker.open)
        listbox = picker.popup.control
        lx, ly, lw, lh = picker.popup.box()
        rows = row_boxes(listbox)
        selectable = [i for i in sorted(rows) if i < len(picker.table) and picker.table[i][1]]
        check.note("rows shown / selectable", (len(rows), selectable[:20]))
        check("the open list has rows to hover", len(selectable) >= 4, rows)
        start = listbox.getSelectedItemPos()
        targets = [i for i in selectable if i != start][1:8:2][:3]  # three rows apart from the highlighted one
        followed = []
        for row in targets:
            rx, ry, rw, rh = rows[row]
            where = wg.mouse_move(ox + lx + rx + min(rw // 3, 120), oy + ly + ry + rh // 2, steps=12, pause=0.03)
            time.sleep(0.8)
            now = listbox.getSelectedItemPos()
            followed.append({"row": row, "label": picker.table[row][0], "pointer": where, "highlight": now,
                             "highlight label": picker.table[now][0] if 0 <= now < len(picker.table) else None})
            wg.screenshot(os.path.join(out, "hover-row%d.png" % row))
        check.note("hover trace (row under the pointer -> highlighted row)", followed)
        check("the highlight follows the pointer over the list (%d rows)" % len(targets),
              bool(targets) and all(item["highlight"] == item["row"] for item in followed), followed)
        before = listbox.getSelectedItemPos()
        wg.keys("down", target=hwnd, front=False)
        time.sleep(0.6)
        after = listbox.getSelectedItemPos()
        check("Down still moves the highlight", after != before and after >= 0, (before, after))
        wg.screenshot(os.path.join(out, "after-down.png"))
        wg.keys("escape", target=hwnd, front=False)
        time.sleep(0.5)
        dialog.endExecute()
        thread.join(10)
        doc.close(True)
    except Exception:  # noqa: BLE001
        import traceback
        check("harness", False, traceback.format_exc())
    finally:
        office.stop()
    return check.exit_code()


if __name__ == "__main__":
    sys.exit(main())
