#!/usr/bin/env python3
# SPDX-License-Identifier: AGPL-3.0-only
"""Runtime check that the ND 30 entry is findable in the real UI, in the vi and en UI languages.

Usage (needs a running X display; never started or stopped here; runs the office as the build user):
    python3 tests/runtime/check-nd30-entry.py [--instdir upstream/libreoffice/instdir] [--out tests/output/nd30-entry]
        [--display :92] [--shots <dir>]   # --shots keeps the two help-guide screenshots (nd30-where.png, nd30-wizard.png)

Per UI language:
  1. Start Center: the HST menu (read through AT-SPI, GTK3 menubar) offers "Văn bản hành chính…" and the CSV import.
  2. Writer: the HST menu offers it too; the Home tab of the ribbon shows the "Văn bản hành chính" button
     (a click on it opens the wizard, whose title and labels are Vietnamese in every UI language).
  3. Language rule: in the en UI only the update check is English; every other HST menu item stays Vietnamese.
Exit status 1 on any FAIL. When started as root the script re-executes itself as the build user under
dbus-run-session (AT-SPI needs a session bus).
"""
import argparse
import os
import re
import shutil
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import hst_gui  # noqa: E402

ROWS = []
ND30 = "Văn bản hành chính…"
WIZARD_TITLE = "Văn bản hành chính"
DESCRIPTION = "Tuân thủ Nghị định số 30/2020/NĐ-CP của Chính phủ về công tác văn thư."
ENGLISH_ITEMS = {"Check for Updates…"}  # the only HST menu item that follows the UI language


def record(name, ok, detail=""):
    ROWS.append((name, ok))
    print("%s  %s  %s" % ("PASS" if ok else "FAIL", name, str(detail)[:300]), flush=True)


def reexec_as_build_user():
    user = hst_gui.BUILD_USER
    os.makedirs(OUT_DEFAULT, exist_ok=True)
    subprocess.run(["chown", "-R", user, OUT_DEFAULT], check=False)
    os.execvp("runuser", ["runuser", "-u", user, "--", "dbus-run-session", "--", sys.executable] + sys.argv)


def walk(accessible, out=None, depth=0):
    out = out if out is not None else []
    try:
        out.append((depth, accessible.getRoleName(), accessible.name, accessible))
        for index in range(accessible.childCount):
            walk(accessible.getChildAtIndex(index), out, depth + 1)
    except Exception:  # noqa: BLE001 - a widget may vanish while walking
        pass
    return out


def office_app():
    import pyatspi
    desktop = pyatspi.Registry.getDesktop(0)
    for index in range(desktop.childCount):
        app = desktop.getChildAtIndex(index)
        if "office" in (app.name or "").lower():
            return app
    return None


def hst_menu(app):
    """(menu accessible, [item names]) of the HST menu in the current window, or (None, [])."""
    nodes = walk(app)
    for position, (depth, role, name, node) in enumerate(nodes):
        if role == "menu" and name == "HST":
            items = []
            for later_depth, later_role, later_name, _ in nodes[position + 1:]:
                if later_depth <= depth:
                    break
                if later_depth == depth + 1 and "item" in later_role and later_name:
                    items.append(later_name)
            return node, items
    return None, []


def window_geometry(wid, display):
    info = subprocess.run(["xwininfo", "-display", display, "-id", wid], capture_output=True, text=True).stdout
    values = [int(re.search(label + r":\s+(-?\d+)", info).group(1)) for label in
              ("Absolute upper-left X", "Absolute upper-left Y", "Width", "Height")]
    return tuple(values)


def open_menu_screenshot(menu, office, args, target):
    """Click the HST menu (position from AT-SPI) and save a screenshot of the open menu; never fails the run."""
    import pyatspi
    try:
        box = menu.queryComponent().getExtents(pyatspi.DESKTOP_COORDS)
        env = dict(os.environ, DISPLAY=args.display)
        os.makedirs(os.path.dirname(target), exist_ok=True)
        subprocess.run(["xdotool", "mousemove", str(box.x + box.width // 2), str(box.y + box.height // 2), "click", "1"], env=env, check=False)
        time.sleep(1.5)
        hst_gui.screenshot(target, args.display)
        subprocess.run(["xdotool", "key", "Escape"], env=env, check=False)
        time.sleep(1)
    except Exception as error:  # noqa: BLE001
        print("menu screenshot skipped:", error)


def crop_window(full, geometry, target):
    from PIL import Image
    x, y, width, height = geometry
    Image.open(full).crop((max(x, 0), max(y, 0), x + width, y + height)).save(target)


def crop_ribbon(full, geometry, target):
    """Top of the Writer window (tabs and Home ribbon) with a red frame around the ND 30 button, for the help guide."""
    from PIL import Image, ImageDraw
    x, y, width, _height = geometry
    image = Image.open(full).convert("RGB")
    left = x + width - 150  # button measured on the 1366x768 test display
    ImageDraw.Draw(image).rectangle((left, y + 122, x + width - 6, y + 148), outline=(220, 30, 30), width=3)
    image.crop((x, y, x + width, y + 160)).save(target)


def wait_window(office, pattern, timeout=40):
    deadline = time.time() + timeout
    while time.time() < deadline:
        for wid, name in hst_gui.toplevels(office.display, office.pid):
            if re.search(pattern, name):
                return wid, name
        time.sleep(1)
    return None, None


def check_language(args, lang, label):
    import uno  # noqa: F401
    # A stale AT_SPI_BUS root property of an earlier run points at a socket that no longer exists.
    subprocess.run(["xprop", "-display", args.display, "-root", "-remove", "AT_SPI_BUS"], check=False)
    office = hst_gui.Office(args.instdir, os.path.join(args.out, "work-" + label), args.port, args.display, lang, nodefault=False).start()
    try:
        time.sleep(6)
        app = office_app()
        import pyatspi
        desktop = pyatspi.Registry.getDesktop(0)
        record(label + " AT-SPI sees the office", app is not None, [desktop.getChildAtIndex(i).name for i in range(desktop.childCount)])
        menu, items = hst_menu(app)
        open_menu_screenshot(menu, office, args, os.path.join(args.shots or args.out, label + "-hst-menu.png"))
        record(label + " Start Center HST menu offers the ND 30 entry", ND30 in items, items)
        record(label + " Start Center HST menu offers CSV import", any("CSV" in i for i in items), items)
        doc = office.load("private:factory/swriter")
        time.sleep(6)
        menu, items = hst_menu(office_app())
        record(label + " Writer HST menu offers the ND 30 entry", ND30 in items, items)
        others = [i for i in items if i not in ENGLISH_ITEMS and not re.search(r"[À-ỹ]|HST|CSV|HASON|NĐ", i)]
        record(label + " every HST menu item is Vietnamese except the update check", not others, others)
        if label == "en":
            record("en: the update check follows the UI language", "Check for Updates…" in items, items)
        shots = os.path.join(args.shots or args.out, "")
        os.makedirs(shots, exist_ok=True)
        office.screenshot(os.path.join(args.out, label + "-writer-ribbon.png"))
        wid, _ = wait_window(office, r"HST Writer", 5)
        record(label + " Writer window found", wid is not None)
        if wid is not None:
            x, y, width, _height = window_geometry(wid, args.display)
            # The button sits at the right end of the Home tab, below "Find & Replace" (measured on the 1366x768 test display).
            subprocess.run(["xdotool", "mousemove", str(x + width - 70), str(y + 135), "click", "1"], env=dict(os.environ, DISPLAY=args.display), check=False)
            crop_ribbon(os.path.join(args.out, label + "-writer-ribbon.png"), (x, y, width, _height), os.path.join(shots, label + "-nd30-where.png"))
            dialog, name = wait_window(office, r"^Văn bản hành chính$", 30)
            record(label + " ribbon button opens the wizard (Vietnamese title)", dialog is not None and WIZARD_TITLE in (name or ""), name)
            if dialog:
                time.sleep(1)
                env = dict(os.environ, DISPLAY=args.display)
                subprocess.run(["xdotool", "windowmove", dialog, "0", "0"], env=env, check=False)  # no window manager: keep it on screen
                subprocess.run(["xdotool", "mousemove", "5", "760"], env=env, check=False)  # no tooltip over the dialog
                time.sleep(2)
                office.raise_windows()
                full = hst_gui.screenshot(os.path.join(args.out, label + "-with-wizard.png"), args.display)
                crop_window(full, window_geometry(dialog, args.display), os.path.join(shots, label + "-nd30-wizard.png"))
                hst_gui.send_close_request(dialog, args.display)
                time.sleep(2)
        try:
            doc.close(True)
        except Exception:  # noqa: BLE001 - the office may already be closing after the wizard test
            pass
    finally:
        office.stop()


OUT_DEFAULT = os.path.join(os.path.dirname(HERE), "output", "nd30-entry")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--instdir", default=os.path.join(os.path.dirname(os.path.dirname(HERE)), "upstream", "libreoffice", "instdir"))
    parser.add_argument("--out", default=OUT_DEFAULT)
    parser.add_argument("--display", default=":92")
    parser.add_argument("--port", type=int, default=2151)
    parser.add_argument("--shots", help="directory that also receives the wizard screenshots")
    args = parser.parse_args()
    if os.geteuid() == 0:
        reexec_as_build_user()
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
