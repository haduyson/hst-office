# SPDX-License-Identifier: AGPL-3.0-only
"""Check the Office-style collapse ladder of the ribbon on a real GUI (gtk3, vi_VN).

Usage: python3 tests/runtime/check-ribbon-scaling.py [--instdir DIR] [--display :71] [--shots DIR]
           [--apps writer,calc,impress] [--out DIR]

Per app, on the Home tab (Trang đầu), the window is narrowed through 1920, 1600, 1485, 1366, 1280, 1100,
1000 and 900 px (900 px high). Each ribbon toolbar is identified by the names of its first items:
  - no toolbar is clipped: it lies inside the window and left of the banner slot;
  - groups shrink before anything folds: at the first width with the chevron, some group still on the
    ribbon is narrower than at the widest width, and whenever the chevron is shown every toolbar
    still on the ribbon is at the narrowest width it has anywhere in the sweep (the fold is the last rung);
  - narrowing never widens a toolbar that stays on the ribbon (monotone, no oscillation);
  - the ribbon height (frame top to the document tab bar) does not change with the width.
Runs as the build user under dbus-run-session (AT-SPI); writes evidence.json and, with --shots, one
screenshot per app and width.
"""
import argparse
import json
import os
import subprocess
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import hst_gui  # noqa: E402
import ribbon_banner_probe as probe  # noqa: E402
import ribbon_tabs_gui as gui  # noqa: E402

WIDTHS = [1920, 1600, 1485, 1366, 1280, 1100, 1000, 900]
PORTS = {"writer": 7430, "calc": 7431, "impress": 7432}
ROWS = []


def record(name, ok, detail=""):
    ROWS.append({"check": name, "status": "PASS" if ok else "FAIL", "detail": str(detail)})
    print(f"{'PASS' if ok else 'FAIL'}  {name}  {str(detail)[:200]}", flush=True)


def showing(node):
    import pyatspi
    return node.getState().contains(pyatspi.STATE_SHOWING)


def scan(display):
    """{toolbar key: box} of the ribbon groups, the chevron box or None, the banner box or None, ribbon height.

    The ribbon groups are the toolbars between the tab row and the bottom of the banner slot (which is
    centred on the ribbon page), so the formula bar and the drawing toolbar below the ribbon are not."""
    found, chevron, banner = [], None, None
    for node in gui.walk(gui.office_app()):
        try:
            if not showing(node):
                continue
            role, name, box = node.getRoleName(), node.name or "", gui.extents(node)
        except Exception:  # noqa: BLE001 - widgets come and go
            continue
        if role == "tool bar" and 40 <= box[1] and box[1] + box[3] <= 260 and box[2] > 0:
            names = []
            for index in range(min(node.childCount, 3)):
                try:
                    names.append(node.getChildAtIndex(index).name or "?")
                except Exception:  # noqa: BLE001
                    names.append("?")
            found.append(("|".join(names) + f"@{node.childCount}", box))
        elif role == "push button" and not name and box[2] <= 30 and box[3] >= 60 and box[1] < 260:
            chevron = box
        elif role == "link" and box[1] < 260 and box[3] >= 40:
            banner = box
    limit = banner[1] + banner[3] + 8 if banner else 175
    bars = {key: box for key, box in found if box[1] + box[3] <= limit}
    top, tabs = probe.doc_tabs_top(display, timeout=5)
    return bars, chevron, banner, (tabs - top) if tabs is not None else None


def sweep(args, app, wid, office):
    observed = []
    for width in WIDTHS:
        gui.xdo(args.display, "windowsize", wid, str(width), "900")
        time.sleep(3)
        bars, chevron, banner, bottom = scan(args.display)
        observed.append((width, bars, chevron, banner, bottom))
        if args.shots:
            office.screenshot(os.path.join(args.shots, f"scaling-{app}-{width}.png"))
    narrowest = {}
    for _width, bars, *_ in observed:
        for key, box in bars.items():
            narrowest[key] = min(narrowest.get(key, box[2]), box[2])
    clipped, early, widened, previous = [], [], [], {}
    for width, bars, chevron, banner, _bottom in observed:
        right = min(width, banner[0]) if banner else width
        for key, box in bars.items():
            if box[0] < 0 or box[0] + box[2] > right + 1:
                clipped.append((width, key, box, right))
            # a one-item toolbar is a control that fills its room (the Styles gallery), not a state
            if key in previous and box[2] > previous[key] + 1 and not key.endswith("@1"):
                widened.append((width, key, previous[key], box[2]))
        if chevron:
            early += [(width, key, box[2], narrowest[key]) for key, box in bars.items() if box[2] > narrowest[key] + 1]
        previous = {k: b[2] for k, b in bars.items()}
    first = next(((w, b) for w, b, c, _n, _x in observed if c), None)
    if first:
        widest = observed[0][1]
        shrunk = [k for k, box in first[1].items() if k in widest and box[2] < widest[k][2] - 1]
        record(f"[{app}] groups shrink before the first fold ({first[0]} px)", bool(shrunk), shrunk or "no group narrower")
    record(f"[{app}] no ribbon group is clipped at {WIDTHS[0]}..{WIDTHS[-1]} px", not clipped, clipped or len(observed))
    record(f"[{app}] the chevron comes only after every group on the ribbon is at its smallest", not early,
           early or [(w, bool(c)) for w, _b, c, _n, _x in observed])
    record(f"[{app}] narrowing never widens a group (monotone)", not widened, widened)
    bottoms = sorted({b for *_, b in observed if b is not None})
    record(f"[{app}] ribbon height independent of the width", len(bottoms) <= 1 or bottoms[-1] - bottoms[0] <= 1, bottoms)
    return [{"width": w, "groups": len(b), "chevron": bool(c), "banner": n} for w, b, c, n, _x in observed]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--instdir", default=os.path.join(hst_gui.ROOT, "upstream/libreoffice/instdir"))
    parser.add_argument("--display", default=":71")
    parser.add_argument("--apps", default="writer,calc,impress")
    parser.add_argument("--out", default=os.path.join(hst_gui.ROOT, "tests/output/ribbon-scaling"))
    parser.add_argument("--shots")
    args = parser.parse_args()
    if os.geteuid() == 0:
        for path in filter(None, (args.out, args.shots)):
            os.makedirs(path, exist_ok=True)
            subprocess.run(["chown", "-R", hst_gui.BUILD_USER, path], check=False)
        os.execvp("runuser", ["runuser", "-u", hst_gui.BUILD_USER, "--", "dbus-run-session", "--", sys.executable] + sys.argv)
    args.instdir, args.out = os.path.abspath(args.instdir), os.path.abspath(args.out)
    os.environ.update(NO_AT_BRIDGE="0", GTK_MODULES="gail:atk-bridge")
    hst_gui.setup_uno(args.instdir)
    report = {}
    for app in filter(None, args.apps.split(",")):
        office, wid, _windows = gui.start(args.instdir, app, args.display, os.path.join(args.out, app), PORTS[app])
        try:
            gui.xdo(args.display, "windowmove", wid, "0", "0")
            home = next(t for t in gui.ribbon_tabs() if t[0] == "Trang đầu")
            if not home[2]:
                gui.click(args.display, home[1])
            report[app] = sweep(args, app, wid, office)
        except Exception as error:  # noqa: BLE001
            record(f"[{app}] crashed", False, repr(error))
        finally:
            office.stop()
    with open(os.path.join(args.out, "evidence.json"), "w", encoding="utf-8") as handle:
        json.dump({"checks": ROWS, "sweep": report}, handle, ensure_ascii=False, indent=1)
    failed = sum(r["status"] != "PASS" for r in ROWS)
    print(f"{len(ROWS)} checks, {failed} failed")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
