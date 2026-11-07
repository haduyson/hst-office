# SPDX-License-Identifier: AGPL-3.0-only
"""Check the Office-style collapse ladder of the ribbon on a real GUI (gtk3, vi_VN).

Usage: python3 tests/runtime/check-ribbon-scaling.py [--instdir DIR] [--display :71] [--shots DIR]
           [--apps writer,calc,impress] [--out DIR]

Per app, on the Home tab (Trang đầu), the window is narrowed through 1920, 1600, 1485, 1366, 1280, 1100,
1000 and 900 px (900 px high). Each ribbon toolbar is identified by the names of its first items:
  - no toolbar is clipped: it lies inside the window and left of the banner slot;
  - the fold is the last rung: where a group (the panel holding a group's toolbars) goes into the
    chevron, the room left between the groups and the chevron is narrower than that group at its
    smallest width in the sweep; a folded group stays folded at every narrower width, unless the
    ribbon got more room there (the banner went compact) or a wider group folds there instead;
  - narrowing never widens a toolbar that stays on the ribbon (monotone, no oscillation), except at
    a width where a group folds: the groups that stay may take back the room it leaves;
  - the ribbon height (frame top to the document tab bar) does not change with the width;
  - after the chevron popup is opened and closed at the narrowest width and the window is widened
    again, the groups are in the order they had at the widest width.
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
import ribbon_tabs_gui as gui  # noqa: E402
from ribbon_scaling_scan import scan  # noqa: E402

WIDTHS = [1920, 1600, 1485, 1366, 1280, 1100, 1000, 900]
PORTS = {"writer": 7430, "calc": 7431, "impress": 7432}
ROWS = []


def record(name, ok, detail=""):
    ROWS.append({"check": name, "status": "PASS" if ok else "FAIL", "detail": str(detail)})
    print(f"{'PASS' if ok else 'FAIL'}  {name}  {str(detail)[:200]}", flush=True)


def order(groups):
    return [key for key, _box in sorted(groups.items(), key=lambda item: item[1][0])]


def chevron_round_trip(args, app, wid, observed):
    """Open and close the chevron popup at the narrowest width, then widen: the groups that came back
    from the popup are in their authored order (as at the widest width), not appended at the end."""
    chevron = observed[-1][2]
    if not chevron:
        return
    x, y, w, h = chevron
    gui.xdo(args.display, "mousemove", str(x + w // 2), str(y + h // 2))
    gui.xdo(args.display, "click", "1")
    time.sleep(2)
    gui.xdo(args.display, "key", "Escape")
    time.sleep(1)
    gui.xdo(args.display, "windowsize", wid, str(WIDTHS[0]), "900")
    time.sleep(3)
    bars, _chevron, _banner, _bottom = scan(args.display)
    record(f"[{app}] groups keep their order after the chevron popup", order(bars.pop("__groups__", {})) == order(observed[0][5]),
           (order(observed[0][5]),))


def sweep(args, app, wid, office):
    observed = []
    for width in WIDTHS:
        gui.xdo(args.display, "windowsize", wid, str(width), "900")
        time.sleep(3)
        bars, chevron, banner, bottom = scan(args.display)
        groups = bars.pop("__groups__", {})
        observed.append((width, bars, chevron, banner, bottom, groups))
        if args.shots:
            office.screenshot(os.path.join(args.shots, f"scaling-{app}-{width}.png"))
    narrowest = {}
    for _width, bars, *_rest in observed:
        for key, box in bars.items():
            narrowest[key] = min(narrowest.get(key, box[2]), box[2])
    narrowest_group = {}
    for *_head, groups in observed:
        for key, box in groups.items():
            narrowest_group[key] = min(narrowest_group.get(key, box[2]), box[2])
    clipped, early, widened, returned, previous, seen, folded = [], [], [], [], {}, set(), set()
    last_right = None
    for width, bars, chevron, banner, _bottom, groups in observed:
        right = min(width, banner[0]) if banner else width
        if last_right is not None and right > last_right:
            folded = set()  # the banner went compact: the ribbon has more room than at the wider width
        last_right = right
        # groups that were on the ribbon at a wider width and are gone now went into the chevron
        newly = (seen - set(groups)) - folded if chevron else set()
        # a narrower group may come back where a wider one folds (the ladder refits the row)
        if not newly:
            returned += [(width, key) for key in folded & set(groups)]
        folded = (folded - set(groups)) | newly
        seen |= set(groups)
        for key, box in bars.items():
            if box[0] < 0 or box[0] + box[2] > right + 1:
                clipped.append((width, key, box, right))
            # a one-item toolbar is a control that fills its room (the Styles gallery), not a state;
            # where a group folds, the groups that stay may take back the room it leaves
            if key in previous and box[2] > previous[key] + 1 and not key.endswith("@1") and not newly:
                widened.append((width, key, previous[key], box[2]))
        if newly and chevron and groups:
            # the fold is the last rung: the group that folded here would not fit, even at its
            # smallest, into the room left between the groups and the chevron
            gap = chevron[0] - max(box[0] + box[2] for box in groups.values())
            need = max(narrowest_group[key] for key in newly)
            if gap >= need:
                early.append((width, sorted(newly), gap, need))
        previous = {k: b[2] for k, b in bars.items()}
    # nothing is judged on an empty scan: every width must have found ribbon toolbars, their groups,
    # the banner and the ribbon height, or the invariants below would pass vacuously
    blind = [w for w, b, _c, n, x, g in observed if not b or not g or n is None or x is None]
    record(f"[{app}] the ribbon was measured at every width", bool(observed) and not blind,
           blind or [(w, len(b), len(g)) for w, b, _c, _n, _x, g in observed])
    if blind or not observed:
        return [{"width": w, "toolbars": len(b), "groups": len(g), "chevron": bool(c), "banner": n}
                for w, b, c, n, _x, g in observed]
    record(f"[{app}] the chevron shows at {observed[-1][0]} px", observed[-1][2] is not None, observed[-1][2])
    record(f"[{app}] no ribbon group is clipped at {WIDTHS[0]}..{WIDTHS[-1]} px", not clipped, clipped or len(observed))
    record(f"[{app}] a group folds only when it would not fit at its smallest", not early,
           early or [(w, bool(c)) for w, _b, c, _n, _x, _g in observed])
    record(f"[{app}] a folded group stays folded as the window narrows", not returned, returned)
    record(f"[{app}] narrowing never widens a group (monotone)", not widened, widened)
    chevron_round_trip(args, app, wid, observed)
    bottoms = sorted({o[4] for o in observed if o[4] is not None})
    record(f"[{app}] ribbon height independent of the width", len(bottoms) <= 1 or bottoms[-1] - bottoms[0] <= 1, bottoms)
    return [{"width": w, "toolbars": len(b), "groups": len(g), "chevron": bool(c), "banner": n}
            for w, b, c, n, _x, g in observed]


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
