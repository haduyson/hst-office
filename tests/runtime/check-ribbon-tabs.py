# SPDX-License-Identifier: AGPL-3.0-only
"""Check the ribbon structure of HST Writer, Sheets and Slides on a real GUI (gtk3, vi_VN).

Usage: python3 tests/runtime/check-ribbon-tabs.py [--instdir DIR] [--baseline-instdir DIR] [--display :71] [--shots DIR]
The X display must already run. For each app at 1485x900:
  - the always-visible tabs have the Word/Excel/PowerPoint order and the Vietnamese names of docs/L10N_GLOSSARY.md;
  - clicking each tab selects it, Right/Left on the focused tab strip move to the next and previous tab;
  - every command added for the ribbon (btnHst*) resolves to a dispatch in that module;
  - the ribbon height and the banner slot equal the baseline build (--baseline-instdir, a build without this change).
Runs as the build user under dbus-run-session (AT-SPI); writes evidence.json.
"""
import argparse
import json
import os
import subprocess
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import hst_gui  # noqa: E402
from ribbon_added_commands import added_commands  # noqa: E402

HEAD = ["Tệp tin", "Trang đầu", "Chèn"]
# 1.0.0: Trợ giúp after Xem; the Developer tab is merged into Phần mở rộng, which stays last (owner, 2026-11-07)
TAIL_1_0 = ["Xem lại", "Xem", "Trợ giúp", "Phần mở rộng"]
TABS = {"writer": HEAD + ["Thiết kế", "Bố cục", "Tham khảo", "Gửi thư"] + TAIL_1_0,
        "calc": HEAD + ["Bố trí Trang", "Công thức", "Dữ liệu"] + TAIL_1_0,
        "impress": HEAD + ["Thiết kế", "Chuyển tiếp", "Hoạt hình", "Trình chiếu"] + TAIL_1_0,
        # HST Draw edits PDFs (hst-ribbon-draw.patch): its own tabs, Xem before Xuất/PDF and Xem lại
        "draw": HEAD + ["Sắp xếp", "Trang", "Xem", "Xuất/PDF", "Xem lại", "Trợ giúp", "Phần mở rộng"]}
NAMES = {"writer": "HST Writer", "calc": "HST Sheets", "impress": "HST Slides", "draw": "HST Draw"}
DOCS = {"writer": "com.sun.star.text.TextDocument", "calc": "com.sun.star.sheet.SpreadsheetDocument",
        "impress": "com.sun.star.presentation.PresentationDocument", "draw": "com.sun.star.drawing.DrawingDocument"}
ROWS = []


def record(name, ok, detail=""):
    ROWS.append({"check": name, "status": "PASS" if ok else "FAIL", "detail": str(detail)})
    print(f"{'PASS' if ok else 'FAIL'}  {name}  {detail}", flush=True)


def xdo(display, *args):
    subprocess.run(["xdotool", *args], env=dict(os.environ, DISPLAY=display), check=False, timeout=15)


def click(display, box):
    xdo(display, "mousemove", str(box[0] + box[2] // 2), str(box[1] + box[3] // 2), "click", "1")
    time.sleep(0.8)


def office_app():
    import pyatspi
    desktop = pyatspi.Registry.getDesktop(0)
    apps = (desktop.getChildAtIndex(index) for index in range(desktop.childCount))
    return next((app for app in apps if app and "office" in (app.name or "").lower()), None)


def walk(node, depth=0):
    yield node
    try:  # widgets come and go
        children = [node.getChildAtIndex(i) for i in range(min(node.childCount, 400))] if depth < 14 else []
    except Exception:  # noqa: BLE001
        children = []
    for child in children:
        if child is not None:
            yield from walk(child, depth + 1)


def extents(node):
    import pyatspi
    box = node.queryComponent().getExtents(pyatspi.DESKTOP_COORDS)
    return box.x, box.y, box.width, box.height


def ribbon_tabs():
    """[(name, box, selected, node)] of the visible tabs in the ribbon (top row), left to right."""
    import pyatspi
    nodes = [n for n in walk(office_app()) if n.getRoleName() == "page tab" and 0 < extents(n)[2] and extents(n)[1] < 100]
    found = [(n.name, extents(n), n.getState().contains(pyatspi.STATE_SELECTED), n) for n in nodes]
    return sorted(found, key=lambda t: t[1][0])


def selected():
    return [t[0] for t in ribbon_tabs() if t[2]]


def geometry():
    top, doc_tabs, banner = None, None, None
    for node in walk(office_app()):
        role = node.getRoleName()
        if role == "frame" and top is None:
            top = extents(node)[1]
        elif role == "panel" and node.name == "Thẻ tài liệu":
            doc_tabs = extents(node)[1]
        elif role == "link" and banner is None and extents(node)[2] > 100:
            banner = extents(node)
    return top, doc_tabs, banner


def start(instdir, app, args, tag, port):
    subprocess.run(["xprop", "-display", args.display, "-root", "-remove", "AT_SPI_BUS"], check=False, stderr=subprocess.DEVNULL)
    office = hst_gui.Office(instdir, os.path.join(args.out, tag), port, display=args.display, extra_args=[f"--{app}"],
                            nodefault=False, config=[("/org.openoffice.Office.Impress/Misc/NewDoc", "AutoPilot", "false")])
    office.start()
    time.sleep(8)
    windows = [w for w, n in hst_gui.toplevels(args.display, office.pid) if NAMES[app] in n]
    xdo(args.display, "windowmove", windows[0], "0", "0")
    xdo(args.display, "windowsize", windows[0], "1485", "900")
    time.sleep(4)
    return office, windows[0]


def check_commands(office, instdir, app):
    frame = office.desktop().getCurrentFrame() or office.desktop().getFrames().getByIndex(0)
    parser = office.service("com.sun.star.util.URLTransformer")
    from com.sun.star.util import URL
    missing, commands = [], added_commands(instdir, app)
    labels = office.service("com.sun.star.frame.UICommandDescription").getByName(DOCS[app])
    for command in commands:
        url = URL()
        props = {p.Name: p.Value for p in labels.getByName(command)} if labels.hasByName(command) else {}
        url.Complete = props.get("TargetURL") or command  # aliases such as .uno:SlideSetup
        _, url = parser.parseStrict(url)
        if frame.queryDispatch(url, "", 0) is None:
            missing.append(command)
    record(f"[{app}] {len(commands)} commands added to the ribbon resolve", not missing, missing)


def check_app(app, args, port):
    office, _wid = start(args.instdir, app, args, f"new-{app}", port)
    measured = {}
    try:
        tabs = ribbon_tabs()
        names = [t[0] for t in tabs]
        record(f"[{app}] tab order and names", names == TABS[app], names)
        for name, box, _sel, _node in tabs:
            if name == "Tệp tin":  # opens the File view, see check-backstage.py
                continue
            click(args.display, box)
            if args.shots:
                office.screenshot(os.path.join(args.shots, f"{app}-{names.index(name):02d}.png"))
            record(f"[{app}] click selects '{name}'", selected() == [name], selected())
        first = names.index("Trang đầu")
        click(args.display, tabs[first][1])
        tabs[first][3].queryComponent().grabFocus()
        time.sleep(0.5)
        for key, want in (("Right", first + 1), ("Left", first)):
            xdo(args.display, "key", key)
            time.sleep(0.8)
            record(f"[{app}] {key} on the tab strip selects '{names[want]}'", selected() == [names[want]], selected())
        check_commands(office, args.instdir, app)
        measured = geometry()
    finally:
        office.stop()
    if args.baseline_instdir:
        base, _wid = start(args.baseline_instdir, app, args, f"base-{app}", port + 1)
        try:
            old = geometry()
        finally:
            base.stop()
        record(f"[{app}] ribbon height unchanged", measured[1] - measured[0] == old[1] - old[0],
               f"new {measured[1] - measured[0]} old {old[1] - old[0]}")
        record(f"[{app}] banner slot unchanged", measured[2] == old[2], f"new {measured[2]} old {old[2]}")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--instdir", default=os.path.join(hst_gui.ROOT, "upstream/libreoffice/instdir"))
    parser.add_argument("--baseline-instdir")
    parser.add_argument("--display", default=":71")
    parser.add_argument("--out", default=os.path.join(hst_gui.ROOT, "tests/output/ribbon-tabs"))
    parser.add_argument("--shots")
    parser.add_argument("--apps", default="writer,calc,impress")
    args = parser.parse_args()
    if os.geteuid() == 0:
        for path in filter(None, (args.out, args.shots)):
            os.makedirs(path, exist_ok=True)
            subprocess.run(["chown", "-R", hst_gui.BUILD_USER, path], check=False)
        os.execvp("runuser", ["runuser", "-u", hst_gui.BUILD_USER, "--", "dbus-run-session", "--", sys.executable] + sys.argv)
    args.instdir, args.out = os.path.abspath(args.instdir), os.path.abspath(args.out)
    os.environ.update(NO_AT_BRIDGE="0", GTK_MODULES="gail:atk-bridge")
    hst_gui.setup_uno(args.instdir)
    for index, app in enumerate(args.apps.split(",")):
        try:
            check_app(app, args, 7200 + 2 * index)
        except Exception as error:  # noqa: BLE001
            record(f"[{app}] crashed", False, repr(error))
    with open(os.path.join(args.out, "evidence.json"), "w", encoding="utf-8") as handle:
        json.dump(ROWS, handle, ensure_ascii=False, indent=1)
    failed = sum(r["status"] != "PASS" for r in ROWS)
    print(f"{len(ROWS)} checks, {failed} failed")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
