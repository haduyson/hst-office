#!/usr/bin/env python3
# SPDX-License-Identifier: AGPL-3.0-only
"""Runtime check of "Tìm tính năng…" (feature search, .uno:CommandPopup) in the vi and en UI.

Usage (needs a running X display; never started or stopped here; runs the office as the build user):
    python3 tests/runtime/check-feature-search.py [--instdir upstream/libreoffice/instdir]
        [--out tests/output/feature-search] [--display :93] [--port 2161]

Per UI language, read through AT-SPI (GTK3) with screenshots kept in --out:
  1. Writer, Sheets, Slides: the Home tab of the ribbon has the feature search button; in Writer a click opens the
     search popup.
  2. Writer: Shift+Esc opens it; searches typed without diacritics find accented labels ("chu ky" -> "Chữ ký số…",
     "dinh dang" -> "Định dạng"), the HST add-on commands ("van ban hanh chinh", "chuyen tcvn", "usb") and "đ" = "d";
     Enter on the "van ban hanh chinh" result opens the ND 30 wizard (add-on commands are dispatched).
  3. Writer with the classic menu bar: the HST menu offers "Tìm tính năng…" right before the last two items.
Exit status 1 on any FAIL. When started as root the script re-executes itself as the build user under
dbus-run-session (AT-SPI needs a session bus).
"""
import argparse
import importlib.util
import os
import re
import shutil
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import hst_gui  # noqa: E402

_spec = importlib.util.spec_from_file_location("nd30_entry", os.path.join(HERE, "check-nd30-entry.py"))
nd30 = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(nd30)

ROWS = []
OUT_DEFAULT = os.path.join(os.path.dirname(HERE), "output", "feature-search")
HST_ITEM = "Tìm tính năng…"  # the HST menu is Vietnamese in every UI language
# query -> (description, predicate over the result labels)
SEARCHES = {
    "chu ky": ("finds Tập tin ▸ … Chữ ký số", lambda rows: any(r.startswith("Tập tin ▸") and "Chữ ký số" in r for r in rows), {"vi"}),
    "dinh dang": ("finds a Định dạng command first", lambda rows: bool(rows) and "Định dạng" in rows[0], {"vi"}),
    "đinh dang": ("đ = d", lambda rows: bool(rows) and "Định dạng" in rows[0], {"vi"}),
    "chuyen tcvn": ("finds HST ▸ Chuyển TCVN3/VNI sang Unicode...",
                    lambda rows: "HST ▸ Chuyển TCVN3/VNI sang Unicode..." in rows, {"vi", "en"}),
    "usb": ("finds HST ▸ Thiết lập USB Token…", lambda rows: "HST ▸ Thiết lập USB Token…" in rows, {"vi", "en"}),
    "digital sig": ("finds Digital Signatures", lambda rows: any("Digital Signature" in r for r in rows), {"en"}),
    "van ban hanh chinh": ("finds HST ▸ Văn bản hành chính…", lambda rows: "HST ▸ Văn bản hành chính…" in rows, {"vi", "en"}),
}


def record(name, ok, detail=""):
    ROWS.append((name, ok))
    print("%s  %s  %s" % ("PASS" if ok else "FAIL", name, str(detail)[:300]), flush=True)


def xdo(display, *args):
    subprocess.run(["xdotool", *args], env=dict(os.environ, DISPLAY=display), check=False, timeout=20)


def walk(node, out, depth=0):
    """(depth, role, name, node) of the UI widgets; document content (a sheet exposes every cell) is skipped."""
    try:
        role = node.getRoleName()
        out.append((depth, role, node.name, node))
        if role.startswith("document") or node.childCount > 500:
            return out
        for index in range(node.childCount):
            walk(node.getChildAtIndex(index), out, depth + 1)
    except Exception:  # noqa: BLE001 - a widget may vanish while walking
        pass
    return out


def nodes(app):
    return walk(app, []) if app is not None else []


def hst_menu(app):
    """(menu accessible, [item names]) of the HST menu, like check-nd30-entry.py but with the pruned walk."""
    found = nodes(app)
    for position, (depth, role, name, node) in enumerate(found):
        if role == "menu" and name == "HST":
            items = []
            for later_depth, later_role, later_name, _ in found[position + 1:]:
                if later_depth <= depth:
                    break
                if later_depth == depth + 1 and "item" in later_role and later_name:
                    items.append(later_name)
            return node, items
    return None, []


def ribbon_box(office, factory):
    """UITest state of the toolbox that holds the feature search button (first item), or None. The VCL
    ribbon is not exposed through AT-SPI, the UITest service sees its widgets by .ui id."""
    box = "SectionBottomHstNd30" if factory == "swriter" else "SectionBottomHstFeatureSearch"
    for _ in range(10):  # the document window may take a moment to become the focused top window
        top = office.service("org.libreoffice.uitest.UITest").getTopFocusWindow()
        if box in top.getChildren():
            return {p.Name: p.Value for p in top.getChild(box).getState()}
        time.sleep(1)
    return None


def popup_entry(app):
    """The search entry of the open popup (its placeholder makes it the only focused text entry), or None."""
    import pyatspi
    for _depth, role, _name, node in nodes(app):
        if role == "text" and node.getState().contains(pyatspi.STATE_FOCUSED):
            return node
    return None


def results(app):
    """Labels of the result rows shown by the popup (table cells of its tree view)."""
    return [name for _depth, role, name, _node in nodes(app) if role == "table cell" and name]


def search(office, display, query, shot):
    xdo(display, "key", "shift+Escape")
    time.sleep(1.5)
    xdo(display, "type", "--delay", "60", query)
    time.sleep(2)
    rows = results(nd30.office_app())
    hst_gui.screenshot(shot, display)
    return rows


def close_popup(display):
    xdo(display, "key", "Escape")
    time.sleep(1)


def check_language(args, lang, label):
    import uno  # noqa: F401
    subprocess.run(["xprop", "-display", args.display, "-root", "-remove", "AT_SPI_BUS"], check=False)
    office = hst_gui.Office(args.instdir, os.path.join(args.out, "work-" + label), args.port, args.display, lang).start()
    shot = lambda name: os.path.join(args.out, "%s-%s.png" % (label, name))  # noqa: E731
    try:
        # 1. ribbon button in the three editors
        for factory, app_name in (("scalc", "sheets"), ("simpress", "slides"), ("swriter", "writer")):
            doc = office.load("private:factory/" + factory)
            time.sleep(7)
            office.raise_windows()
            box = ribbon_box(office, factory)
            hst_gui.screenshot(shot(app_name + "-ribbon"), args.display)
            record("%s %s: Home tab shows the feature search button" % (label, app_name),
                   box is not None and box["ReallyVisible"] == "true" and int(box["ItemCount"]) >= 1, box)
            if factory != "swriter":
                doc.close(True)
                time.sleep(2)
        if box is not None:
            bx, by = (int(v) for v in box["AbsPosition"].split("x"))  # screen coordinates (no window manager)
            height = int(box["Size"].split("x")[1])
            xdo(args.display, "mousemove", str(bx + 14), str(by + height // 2), "click", "1")  # first item's icon
            time.sleep(1.5)
            entry = popup_entry(nd30.office_app())
            hst_gui.screenshot(shot("writer-button-popup"), args.display)
            record(label + " writer: the ribbon button opens the search popup", entry is not None)
            close_popup(args.display)
        # 2. Shift+Esc and searches
        for query, (what, ok, langs) in SEARCHES.items():
            if label not in langs:
                continue
            rows = search(office, args.display, query, shot("search-" + re.sub(r"\W+", "-", query)))
            record("%s Shift+Esc %r %s" % (label, query, what), ok(rows), rows[:8])
            if query == "van ban hanh chinh" and ok(rows):
                for _ in range(rows.index("HST ▸ Văn bản hành chính…")):
                    xdo(args.display, "key", "Down")
                    time.sleep(0.3)
                xdo(args.display, "key", "Return")
                dialog, name = nd30.wait_window(office, r"^Văn bản hành chính$", 30)
                record(label + " Enter on the HST result opens the ND 30 wizard", dialog is not None, name)
                if dialog:
                    hst_gui.send_close_request(dialog, args.display)
                    time.sleep(2)
            else:
                close_popup(args.display)
        # 3. HST menu (classic menu bar shown for the check)
        frame = office.desktop().getCurrentFrame()
        office.dispatch(frame, ".uno:Menubar")
        time.sleep(3)
        menu, items = hst_menu(nd30.office_app())
        last = items[-3:] if len(items) >= 3 else items
        record(label + " HST menu offers Tìm tính năng… before the last two items",
               len(last) == 3 and last[0] == HST_ITEM and last[1].startswith("Giải pháp HASON TECH"), items)
        if menu is not None:
            nd30.open_menu_screenshot(menu, office, args, shot("hst-menu"))
    finally:
        office.stop()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--instdir", default=os.path.join(hst_gui.ROOT, "upstream", "libreoffice", "instdir"))
    parser.add_argument("--out", default=OUT_DEFAULT)
    parser.add_argument("--display", default=":93")
    parser.add_argument("--port", type=int, default=2161)
    args = parser.parse_args()
    if os.geteuid() == 0:
        os.makedirs(args.out, exist_ok=True)
        subprocess.run(["chown", "-R", hst_gui.BUILD_USER, args.out], check=False)
        os.execvp("runuser", ["runuser", "-u", hst_gui.BUILD_USER, "--", "dbus-run-session", "--", sys.executable] + sys.argv)
    args.instdir, args.out = os.path.abspath(args.instdir), os.path.abspath(args.out)
    os.makedirs(args.out, exist_ok=True)
    os.environ.update(NO_AT_BRIDGE="0", GTK_MODULES="gail:atk-bridge")
    hst_gui.setup_uno(args.instdir)
    for lang, label in (("vi_VN.UTF-8", "vi"), ("en_US.UTF-8", "en")):
        shutil.rmtree(os.path.join(args.out, "work-" + label), ignore_errors=True)
        try:
            check_language(args, lang, label)
        except Exception as error:  # noqa: BLE001
            record(label + " check crashed", False, repr(error))
    failed = [name for name, ok in ROWS if not ok]
    print("%d checks, %d failed" % (len(ROWS), len(failed)))
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
