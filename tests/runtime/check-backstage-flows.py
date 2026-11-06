#!/usr/bin/env python3
# SPDX-License-Identifier: AGPL-3.0-only
"""Runtime check of the File view paths check-backstage.py does not press, on GTK3 in the vi UI of HST Writer.

Usage (needs a running X display; never started or stopped here; runs the office as the build user):
    python3 tests/runtime/check-backstage-flows.py [--instdir upstream/libreoffice/instdir]
        [--out tests/output/backstage-flows] [--display :93] [--port 2165]

  0. the left column shows a hover highlight that ends when the pointer leaves;
  1. New: the template view shows on the page background, without upstream's language samples; the administrative document wizard runs from the page and from the Home tile;
  2. Recent: a right click and the Menu key open the file menu; Pin moves the file to the pinned list;
  3. Save As: activating a format closes the view and opens the save dialog;
  4. classic menu bar: its File menu opens with Alt+T as before.
Screenshots stay in --out. Exit status 1 on any FAIL. When started as root the script re-executes itself as the build
user under dbus-run-session (AT-SPI needs a session bus).
"""
import argparse
import os
import shutil
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import hst_gui  # noqa: E402
import backstage_gui as gui  # noqa: E402
from backstage_visual import check_hover, pixel  # noqa: E402

ND30 = "org.hst.office.vi:Nd30Wizard"
OUT_DEFAULT = os.path.join(os.path.dirname(HERE), "output", "backstage-flows")


def found(role=None):
    return [(name, node) for got, name, node in gui.showing(gui.walk(gui.nd30.office_app(), []))
            if role is None or got == role]


def named(name, role=None):
    return [node for got, node in found(role) if got == name]


def menu_items():
    return [name for name, _node in found("menu item") if name]


def check_new(office, frame, interceptor, out):
    gui.reopen(office, frame)
    gui.press(gui.view_items()["Mới"])
    time.sleep(3)
    hst_gui.screenshot(os.path.join(out, "moi.png"), office.display)
    gui.record("New shows the template view", bool(named("Mẫu")))
    shot = os.path.join(out, "moi.png")
    box = named("Mẫu")[0].queryComponent().getExtents(0)
    page, gallery = pixel(shot, (box.x - 20, box.y + 8)), pixel(shot, (box.x + 8, box.y + 8))
    gui.record("the gallery has the page background", page == gallery, "%s %s" % (page, gallery))
    samples = os.path.join(office.program, "..", "share", "template", "common", "l10n")
    gui.record("the upstream language samples are not installed", not os.path.exists(samples))
    gui.press(gui.view_items()["Văn bản hành chính (NĐ 30)"])
    gui.record("New: the Decree 30 button runs the wizard", gui.expect_call(interceptor, ND30))
    gui.wait_state(False)
    interceptor.calls.clear()
    gui.reopen(office, frame)
    gui.press(gui.view_items()["Văn bản hành chính (NĐ 30)"])
    gui.record("Home: the Decree 30 tile runs the wizard", gui.expect_call(interceptor, ND30))
    gui.wait_state(False)


def check_pin(office, frame, recent, out):
    display = office.display
    gui.reopen(office, frame)
    cell = named(recent)
    gui.record("Recent lists the saved file", bool(cell), recent)
    box = cell[0].queryComponent().getExtents(0)
    gui.xdo(display, "mousemove", str(box.x + 20), str(box.y + 8))
    time.sleep(0.4)
    gui.xdo(display, "click", "3")
    time.sleep(1.2)
    items = menu_items()
    hst_gui.screenshot(os.path.join(out, "menu-chuot-phai.png"), display)
    gui.record("a right click opens the file menu", {"Mở", "Ghim", "Xóa khỏi danh sách"} <= set(items), items[:6])
    gui.xdo(display, "key", "Escape")
    time.sleep(0.6)
    gui.reopen(office, frame)
    gui.xdo(display, "click", "1")
    time.sleep(0.3)
    gui.xdo(display, "key", "Menu")
    time.sleep(1.2)
    gui.record("the Menu key opens the file menu", "Ghim" in menu_items())
    if named("Ghim"):
        gui.press(named("Ghim")[0])
    time.sleep(1)
    tab = named("Đã ghim", "page tab")
    if tab:
        box = tab[0].queryComponent().getExtents(0)
        gui.xdo(display, "mousemove", str(box.x + 10), str(box.y + 8), "click", "1")
        time.sleep(0.8)
    hst_gui.screenshot(os.path.join(out, "da-ghim.png"), display)
    gui.record("Pin moves the file to the pinned list", bool(named(recent)), recent)


def check_format(office, frame, out):
    display = office.display
    gui.reopen(office, frame)
    gui.press(gui.view_items()["Lưu thành"])
    time.sleep(0.6)
    row = [node for name, node in found() if name and name.startswith("Văn bản ODF")]
    gui.record("Save As lists the ODF format", bool(row))
    box = row[0].queryComponent().getExtents(0)
    gui.xdo(display, "mousemove", str(box.x + 30), str(box.y + 8), "click", "--repeat", "2", "--delay", "60", "1")
    time.sleep(3)
    titles = [name for _wid, name in hst_gui.toplevels(display, office.pid)]
    hst_gui.screenshot(os.path.join(out, "hop-thoai-luu.png"), display)
    gui.record("a format opens the save dialog", "Lưu" in titles, titles)
    gui.xdo(display, "key", "Escape")
    time.sleep(1.5)
    gui.record("the view stays closed after the dialog", not gui.is_open())


def check_classic(office, frame, out):
    from com.sun.star.beans import PropertyValue
    display = office.display
    mode = PropertyValue()
    mode.Name, mode.Value = "Mode", "Default"
    office.dispatch(frame, ".uno:ToolbarMode", (mode,))
    time.sleep(3)
    gui.record("the classic menu bar has Tệp tin", bool(named("Tệp tin", "menu")))
    gui.xdo(display, "key", "alt+t")
    time.sleep(1.5)
    hst_gui.screenshot(os.path.join(out, "menu-tap-tin.png"), display)
    gui.record("Alt+T opens the File menu", bool(menu_items()), menu_items()[:5])
    gui.xdo(display, "key", "Escape")
    time.sleep(0.5)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--instdir", default=os.path.join(hst_gui.ROOT, "upstream", "libreoffice", "instdir"))
    parser.add_argument("--out", default=OUT_DEFAULT)
    parser.add_argument("--display", default=":93")
    parser.add_argument("--port", type=int, default=2165)
    parser.add_argument("--dark", action="store_true", help="in the dark GTK theme")
    args = parser.parse_args()
    if os.geteuid() == 0:
        os.makedirs(args.out, exist_ok=True)
        subprocess.run(["chown", "-R", hst_gui.BUILD_USER, args.out], check=False)
        os.execvp("runuser", ["runuser", "-u", hst_gui.BUILD_USER, "--", "dbus-run-session", "--", sys.executable] + sys.argv)
    args.instdir, args.out = os.path.abspath(args.instdir), os.path.abspath(args.out)
    os.environ.update(NO_AT_BRIDGE="0", GTK_MODULES="gail:atk-bridge")
    hst_gui.setup_uno(args.instdir)
    work = os.path.join(args.out, "work")
    shutil.rmtree(work, ignore_errors=True)
    office = hst_gui.Office(args.instdir, work, args.port, display=args.display,
                            env={"GTK_THEME": "Adwaita:dark"} if args.dark else None)
    office.start()
    try:
        files = os.path.join(args.out, "files")
        os.makedirs(files, exist_ok=True)
        recent = gui.seed_recent(office, files, "swriter", ".docx", "MS Word 2007 XML")
        document = office.load("private:factory/swriter")
        frame = document.CurrentController.Frame
        time.sleep(3)
        office.raise_windows()
        interceptor = gui.make_interceptor({ND30, ".uno:SaveAs"})
        frame.registerDispatchProviderInterceptor(interceptor)
        for step in (lambda: check_hover(office, frame, args.out),
                     lambda: check_new(office, frame, interceptor, args.out),
                     lambda: check_pin(office, frame, recent, args.out),
                     lambda: check_format(office, frame, args.out),
                     lambda: check_classic(office, frame, args.out)):
            try:
                step()
            except Exception as error:  # noqa: BLE001
                gui.record("step crashed", False, repr(error))
        frame.releaseDispatchProviderInterceptor(interceptor)
        gui.close_document(document)
    finally:
        office.stop()
    failed = [name for name, ok in gui.ROWS if not ok]
    print("%d checks, %d failed" % (len(gui.ROWS), len(failed)))
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
