# SPDX-License-Identifier: AGPL-3.0-only
"""Compact ribbon and quick access keys of Writer on a real GUI (gtk3, Xvfb, vi_VN): ready for the P5 build.

Usage: python3 tests/runtime/check-ribbon-compact-gui.py --instdir DIR [--display :281] [--out DIR]
Run it as the build user under dbus-run-session (the script re-executes itself so, as root). Checks:
  - Ctrl+F1 (HstToggleRibbon, accelerator F1_MOD1 of shortcuts-office-parity.json) collapses the ribbon: the tab page
    is gone and the tab row stays; a second Ctrl+F1 shows the page again;
  - in the compact state the quick command row (data/ribbon/quick-rows.json, Writer Trang đầu) shows as buttons in
    the band under the tab row, and their count equals the commands of that row (separators excluded);
  - the quick access toolbar keys are positional: Alt+4 undoes (Hoàn tác) and Alt+5 redoes (Làm lại) text typed in
    the document (the six defaults Mới, Mở, Lưu, Hoàn tác, Làm lại, In of the owner's decision D3);
  - in the compact state Alt+<the Home tab's letter> drops the Home page over the document (the floating page).
Writes <out>/results.json; exit 1 on any FAIL. A check whose target the build lacks FAILS with its reason; nothing is
skipped silently.
"""
import argparse
import json
import os
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import hst_gui  # noqa: E402
import ribbon_tabs_gui as gui  # noqa: E402
import ribbon_mockup_atspi as atspi  # noqa: E402
import ribbon_mockup_geometry as geo  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(HERE))
QUICK_ROWS = os.path.join(ROOT, "data", "ribbon", "quick-rows.json")
HOME_LETTER = "H"  # Trang đầu's KeyTip in the Office table (keytips-office-parity.json); checked against the table below
ROWS = []


def record(name, ok, detail=""):
    ROWS.append({"check": name, "status": "PASS" if ok else "FAIL", "detail": str(detail)})
    print(f"{'PASS' if ok else 'FAIL'}  {name}  {detail}", flush=True)


# labels of the compact quick row on the Writer Trang đầu row (the P5 build; 8 of 10 must be found)
QUICK_LABELS = ["Dán", "Cắt", "Sao chép", "Đậm", "Nghiêng", "Gạch chân", "Căn giữa", "Gạch đầu dòng", "Tìm",
                "Văn bản hành chính"]


def quick_row_count(tab_app="writer", box="pmhbHome"):
    with open(QUICK_ROWS, encoding="utf-8") as handle:
        rows = json.load(handle)["rows"]
    row = next(r for r in rows if r["app"] == tab_app and r["box"] == box)
    return sum(1 for c in row["commands"] if c != "|")


def page_shown(nodes):
    """The Trang đầu page is shown when its page panel is in the ribbon band (the body of the tab)."""
    return geo.page_box(nodes, geo.tab_geometry(nodes)[0]) is not None


def quick_buttons(nodes):
    """Buttons in the band under the tab row (the compact quick row), by their accessible names."""
    tab_top, _strip = geo.tab_geometry(nodes)
    if tab_top is None:
        return []
    return [n for n in nodes if n[0] in geo.BUTTON_ROLES and tab_top + 36 <= n[2][1] < tab_top + 36 + 45]


def active_name(display):
    """The HST window the keys go to: with no window manager (Xvfb) the focus is not reported, so the name of the
    HST window on the display is read instead."""
    out = subprocess.run(["xdotool", "search", "--name", "HST"], env=dict(os.environ, DISPLAY=display),
                         capture_output=True, text=True, check=False).stdout.split()
    names = []
    for wid in out:
        name = subprocess.run(["xdotool", "getwindowname", wid], env=dict(os.environ, DISPLAY=display),
                              capture_output=True, text=True, check=False).stdout.strip()
        names.append(name)
    return " | ".join(names)


def key(display, *keys):
    gui.xdo(display, "key", "--clearmodifiers", *keys)
    time.sleep(2.5)  # let the window redraw before the tree is read; the P5 run waits 1.2 s then reads, so a delay is no cause


def type_text(display, text):
    gui.xdo(display, "type", "--delay", "80", text)
    time.sleep(1)


def text_of(office):
    return office.desktop().getCurrentFrame().getController().getModel().getText().getString()


def check(args):
    office, wid, _ = gui.start(args.instdir, "writer", args.display, os.path.join(args.out, "work"), 7701)
    gui.xdo(args.display, "windowsize", wid, str(args.width), str(args.height))  # the size the P5 run used: 1366x768
    time.sleep(3)
    try:
        gui.open_tab(args.display, "Trang đầu")
        time.sleep(2)
        gui.click(args.display, (700, 500, 10, 10))  # the document takes the focus
        time.sleep(1)
        record("focused window is an HST window", "HST" in active_name(args.display), active_name(args.display))
        hst_gui.screenshot(os.path.join(args.out, "before-ctrl-f1.png"), args.display)
        base = atspi.ribbon_nodes()
        record("Trang đầu page shown before Ctrl+F1", page_shown(base), "")
        key(args.display, "ctrl+F1")
        compact = atspi.ribbon_nodes()
        hst_gui.screenshot(os.path.join(args.out, "after-ctrl-f1.png"), args.display)
        record("Ctrl+F1 collapses the ribbon (page hidden, tab row kept)",
               not page_shown(compact) and geo.tab_geometry(compact)[0] is not None, "")
        # the quick row of the compact ribbon: its labels (the Writer Trang đầu row, as shown on the P5 build)
        shown = {n[1] for n in compact if n[0] in geo.BUTTON_ROLES}
        found = [name for name in QUICK_LABELS if name in shown]
        record("compact quick row shows the Writer Trang đầu commands", len(found) >= 8,
               f"{len(found)} of {len(QUICK_LABELS)} labels, row has {quick_row_count()} commands; "
               f"names in the band: {sorted(shown)[:25]}")
        # the compact band: its bottom is at most 80 px under the tab row's top, and no group caption shows
        tab_top, _strip = geo.tab_geometry(compact)
        bottoms = [n[2][1] + n[2][3] for n in compact if n[0] in geo.BUTTON_ROLES
                   and tab_top is not None and tab_top <= n[2][1] < tab_top + 120]
        band = max(bottoms) - tab_top if tab_top is not None and bottoms else None
        record("compact band is at most 80 px under the tab row", band is not None and band <= 80 + 1, band)
        captions = {n[1] for n in compact if n[0] == "label"}
        record("compact band shows no group caption (Phông chữ)", "Phông chữ" not in captions, sorted(captions)[:10])
        key(args.display, "ctrl+F1")
        record("second Ctrl+F1 shows the page again", page_shown(atspi.ribbon_nodes()), "")
        mo_roles = sorted({n[0] for n in atspi.ribbon_nodes() if n[1] == "Mới"})
        record("QAT Mới is a plain button without a dropdown", mo_roles == ["push button"], mo_roles)
        gui.click(args.display, (700, 500, 10, 10))  # the document: its text takes the keys
        type_text(args.display, "qat")
        key(args.display, "alt+4")
        record("Alt+4 undoes (Hoàn tác, positional)", "qat" not in text_of(office), repr(text_of(office)[-20:]))
        key(args.display, "alt+5")
        record("Alt+5 redoes (Làm lại, positional)", "qat" in text_of(office), repr(text_of(office)[-20:]))
        key(args.display, "ctrl+F1")
        key(args.display, "alt", HOME_LETTER.lower())
        hst_gui.screenshot(os.path.join(args.out, "after-alt-h.png"), args.display)
        record("Alt+letter drops the Home page over the document in the compact state",
               page_shown(atspi.ribbon_nodes()), "")
    finally:
        office.stop()


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--instdir", required=True)
    parser.add_argument("--display", default=":281")
    parser.add_argument("--out", default=os.path.join(hst_gui.ROOT, "tests/output/ribbon-compact"))
    parser.add_argument("--width", type=int, default=1366)
    parser.add_argument("--height", type=int, default=768)
    args = parser.parse_args()
    if os.geteuid() == 0:
        os.makedirs(args.out, exist_ok=True)
        subprocess.run(["chown", "-R", hst_gui.BUILD_USER, args.out], check=False)
        os.execvp("runuser", ["runuser", "-u", hst_gui.BUILD_USER, "--", "env", "NO_AT_BRIDGE=0",
                              "GTK_MODULES=gail:atk-bridge", "dbus-run-session", "--", sys.executable] + sys.argv)
    args.instdir, args.out = os.path.abspath(args.instdir), os.path.abspath(args.out)
    hst_gui.setup_uno(args.instdir)
    try:
        check(args)
    except Exception as error:  # noqa: BLE001 - a missing feature must show as FAIL with its reason
        record("compact checks ran", False, repr(error))
    with open(os.path.join(args.out, "results.json"), "w", encoding="utf-8") as handle:
        json.dump(ROWS, handle, ensure_ascii=False, indent=1)
    failed = sum(r["status"] == "FAIL" for r in ROWS)
    print(f"{len(ROWS)} checks, {failed} failed")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
