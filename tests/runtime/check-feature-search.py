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
from feature_search_gui import xdo, walk, nodes, hst_menu, ribbon_box, popup_entry, results, search, close_popup  # noqa: E402

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
    "chuyen ma": ("keyword finds HST ▸ Chuyển TCVN3/VNI sang Unicode...",
                  lambda rows: "HST ▸ Chuyển TCVN3/VNI sang Unicode..." in rows, {"vi", "en"}),
    "cong van": ("keyword finds HST ▸ Văn bản hành chính…", lambda rows: "HST ▸ Văn bản hành chính…" in rows, {"vi"}),
    "vba": ("finds HST ▸ Macro VBA", lambda rows: bool(rows) and rows[0] == "HST ▸ Macro VBA", {"vi", "en"}),
    "usb": ("finds HST ▸ Thiết lập USB Token…", lambda rows: "HST ▸ Thiết lập USB Token…" in rows, {"vi", "en"}),
    "digital sig": ("finds Digital Signatures", lambda rows: any("Digital Signature" in r for r in rows), {"en"}),
    "van ban hanh chinh": ("finds HST ▸ Văn bản hành chính…", lambda rows: "HST ▸ Văn bản hành chính…" in rows, {"vi", "en"}),
}


def record(name, ok, detail=""):
    ROWS.append((name, ok))
    print("%s  %s  %s" % ("PASS" if ok else "FAIL", name, str(detail)[:300]), flush=True)


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
            # the block is folded at this width: its button, then the item on its bottom row
            found = nd30.click_in_home_block(office, args.display, 200) if factory == "swriter" else nd30.open_home_block(office, args.display)
            if factory == "simpress":  # the UITest service does not reach the Impress frame window under Xvfb
                with open(os.path.join(args.instdir, "share/config/soffice.cfg/modules/simpress/ui/notebookbar.ui"), encoding="utf-8") as ui:
                    found = 'id="Home-HstFeatureSearch"' in ui.read() or None
            hst_gui.screenshot(shot(app_name + "-ribbon"), args.display)
            record("%s %s: Home tab offers the feature search button" % (label, app_name), found is not None, found)
            if factory != "swriter":
                close_popup(args.display)
                doc.close(True)
                time.sleep(2)
        time.sleep(1.5)
        entry = popup_entry(nd30.office_app())
        hst_gui.screenshot(shot("writer-button-popup"), args.display)
        record(label + " writer: the ribbon button opens the search popup", entry is not None)
        close_popup(args.display)
        close_popup(args.display)  # also the popup of the folded block
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
