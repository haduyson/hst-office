# SPDX-License-Identifier: AGPL-3.0-only
"""Check where the HST commands sit in HST Writer, Sheets and Slides (gtk3, vi_VN), as in Microsoft Office.

Usage: python3 tests/runtime/check-ribbon-hst-commands.py [--instdir DIR] [--display :79] [--shots DIR] [--apps writer,calc,impress]
On a running X display, per app at 1485x900: Xem lại ▸ Ngôn ngữ has the "Ngôn ngữ giao diện" drop-down (Tiếng Việt /
English / Theo máy); Nhà phát triển has "Macro VBA" first in Writer and Sheets (Slides has no VBA, see vba.py);
Phần mở rộng shows only that app's HST tools; Tệp tin ▸ Thông tin has "Thiết lập USB Token…" right of "Chữ ký số…";
the ≡ menu has the update check before About; the moved commands resolve on the document frame.
Runs as the build user under dbus-run-session (AT-SPI); writes evidence.json; --shots saves one PNG per tab.
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

VI = "org.hst.office.vi:"
LANGUAGE_ITEMS = ["Tiếng Việt", "English", "Theo máy"]
MOVED = {"Kiểm tra cập nhật…", "Thiết lập USB Token…", "Macro VBA", "Ngôn ngữ giao diện"}
EXTENSION_TAB = {
    "writer": {"Văn bản hành chính", "Chuyển TCVN3/VNI sang Unicode", "Giải pháp HASON TECH"},
    "calc": {"Văn bản hành chính", "Định dạng ngày (dd/mm/yyyy)", "Định dạng tiền VND", "Định dạng phần trăm",
             "Nhập CSV (UTF-8)", "Giải pháp HASON TECH"},
    "impress": {"Văn bản hành chính", "Giải pháp HASON TECH"},
}
# Every tool name the Extension tab can show, to tell its items from the rest of the ribbon.
KNOWN = set().union(*EXTENSION_TAB.values()) | MOVED
BUTTONS = ("push button", "toggle button", "push button menu", "menu button")
MODULES = {"writer": "swriter", "calc": "scalc", "impress": "simpress"}
ROWS = []


def record(name, ok, detail=""):
    ROWS.append({"check": name, "status": "PASS" if ok else "FAIL", "detail": str(detail)})
    print(f"{'PASS' if ok else 'FAIL'}  {name}  {detail}", flush=True)
    return ok


def shot(args, office, name):
    if args.shots:
        office.screenshot(os.path.join(args.shots, name + ".png"))


def check_review(args, office, app):
    if not record(f"[{app}] Xem lại opens", gui.open_tab(args.display, "Xem lại")):
        return
    shot(args, office, f"{app}-xem-lai")
    buttons = [n for n in gui.ribbon_nodes(BUTTONS) if n[0] == "Ngôn ngữ giao diện"]
    labels = [n for n in gui.ribbon_nodes(("label",)) if n[0] == "Ngôn ngữ"]
    record(f"[{app}] Xem lại has the 'Ngôn ngữ' group", bool(labels), [n[2] for n in labels])
    if not record(f"[{app}] Xem lại has the 'Ngôn ngữ giao diện' drop-down", len(buttons) == 1, [n[1:3] for n in buttons]):
        return
    proofing = [n for n in gui.ribbon_nodes(("label",)) if n[0] == "Soát lỗi"]
    if proofing and labels:
        record(f"[{app}] 'Ngôn ngữ' comes right after 'Soát lỗi'", proofing[0][2][0] < labels[0][2][0],
               (proofing[0][2], labels[0][2]))
    gui.click(args.display, buttons[0][2])
    time.sleep(1.5)
    items = [n[0] for n in gui.ribbon_nodes(("menu item", "check menu item", "radio menu item"), band=2000)]
    shot(args, office, f"{app}-xem-lai-ngon-ngu")
    record(f"[{app}] the drop-down lists {', '.join(LANGUAGE_ITEMS)}", [i for i in items if i in LANGUAGE_ITEMS] == LANGUAGE_ITEMS, items)
    gui.xdo(args.display, "key", "Escape")
    time.sleep(1)


def check_developer(args, office, app):
    if not record(f"[{app}] Nhà phát triển opens", gui.open_tab(args.display, "Nhà phát triển")):
        return
    shot(args, office, f"{app}-nha-phat-trien")
    names = [n[0] for n in gui.ribbon_nodes(BUTTONS)]
    if app == "impress":
        record("[impress] no Macro VBA (VBA runs in Writer and Sheets only)", "Macro VBA" not in names, names)
        return
    vba = [n for n in gui.ribbon_nodes(BUTTONS) if n[0] == "Macro VBA"]
    record(f"[{app}] Nhà phát triển has 'Macro VBA' once", len(vba) == 1, names)
    macro = [n for n in gui.ribbon_nodes(BUTTONS) if n[0] in ("Chạy macro", "Chạy Macro", "Chạy vĩ lệnh")]
    if vba and macro:
        record(f"[{app}] 'Macro VBA' comes first, before the macro buttons", vba[0][2][0] < macro[0][2][0],
               (vba[0][2], macro[0][2]))


def check_extension_tab(args, office, app):
    if not record(f"[{app}] Phần mở rộng opens", gui.open_tab(args.display, "Phần mở rộng")):
        return
    shot(args, office, f"{app}-phan-mo-rong")
    # the items of the addon toolbars report no extents of their own: take the children of the showing toolbars
    names = set()
    for _name, _role, _box, bar in gui.ribbon_nodes(("tool bar",)):
        names.update(bar.getChildAtIndex(i).name for i in range(bar.childCount))
    names = (names | {n[0] for n in gui.ribbon_nodes(BUTTONS)}) & KNOWN
    record(f"[{app}] Phần mở rộng shows exactly the HST tools", names == EXTENSION_TAB[app], sorted(names))


def check_backstage(args, office, app):
    tabs = {t[0]: t for t in gui.ribbon_tabs()}
    gui.click(args.display, tabs["Tệp tin"][1])
    time.sleep(2.5)
    info = [n for n in gui.ribbon_nodes(BUTTONS + ("list item", "page tab", "radio button"), band=2000) if n[0] == "Thông tin"]
    if not record(f"[{app}] File view has 'Thông tin'", bool(info)):
        gui.xdo(args.display, "key", "Escape")
        return
    gui.click(args.display, info[0][2])
    time.sleep(1.5)
    buttons = {n[0]: n for n in gui.ribbon_nodes(BUTTONS, band=2000)}
    shot(args, office, f"{app}-tap-tin-thong-tin")
    token, sign = buttons.get("Thiết lập USB Token…"), buttons.get("Chữ ký số…")
    record(f"[{app}] Thông tin has 'Thiết lập USB Token…'", token is not None, sorted(buttons))
    if token and sign:
        record(f"[{app}] 'Thiết lập USB Token…' sits right of 'Chữ ký số…'",
               token[2][0] > sign[2][0] and abs(token[2][1] - sign[2][1]) < 5, (sign[2], token[2]))
    gui.xdo(args.display, "key", "Escape")
    time.sleep(1.5)


def check_static(args, office, app):
    path = os.path.join(args.instdir, f"share/config/soffice.cfg/modules/{MODULES[app]}/popupmenu/notebookbar.xml")
    with open(path, encoding="utf-8") as handle:
        text = handle.read()
    update, about = text.find('menu:id="org.hst.office.update:Check"'), text.find('menu:id=".uno:About"')
    record(f"[{app}] ≡ menu: update check before About", 0 <= update < about, path)
    frame = office.desktop().getCurrentFrame() or office.desktop().getFrames().getByIndex(0)
    parser = office.service("com.sun.star.util.URLTransformer")
    from com.sun.star.util import URL
    commands = ["org.hst.office.update:Check", VI + "SetupUsbToken", VI + "UILanguageVi", VI + "UILanguageEn",
                VI + "UILanguageSystem"] + ([VI + "EditVba"] if app != "impress" else [])
    missing = []
    for command in commands:
        url = URL()
        url.Complete = command
        if frame.queryDispatch(parser.parseStrict(url)[1], "", 0) is None:
            missing.append(command)
    record(f"[{app}] {len(commands)} moved commands resolve", not missing, missing)


def check_app(app, args, port):
    office, _wid, _windows = gui.start(args.instdir, app, args.display, os.path.join(args.out, app), port)
    try:
        check_static(args, office, app)
        check_review(args, office, app)
        check_developer(args, office, app)
        check_extension_tab(args, office, app)
        check_backstage(args, office, app)
    finally:
        office.stop()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--instdir", default=os.path.join(hst_gui.ROOT, "upstream/libreoffice/instdir"))
    parser.add_argument("--display", default=":79")
    parser.add_argument("--out", default=os.path.join(hst_gui.ROOT, "tests/output/ribbon-hst-commands"))
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
            check_app(app, args, 7400 + 2 * index)
        except Exception as error:  # noqa: BLE001
            record(f"[{app}] crashed", False, repr(error))
    with open(os.path.join(args.out, "evidence.json"), "w", encoding="utf-8") as handle:
        json.dump(ROWS, handle, ensure_ascii=False, indent=1)
    failed = sum(r["status"] != "PASS" for r in ROWS)
    print(f"{len(ROWS)} checks, {failed} failed")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
