#!/usr/bin/env python3
# SPDX-License-Identifier: LicenseRef-HST-Proprietary
# Copyright (C) 2026 HASON TECH
"""Screenshots of the HST frame (ribbon, File tab, sidebar, status bar, context menu, document tabs) in Writer,
Sheets and Slides: the baseline and the before/after pairs of the frame coat.

Linux (gtk3, on an Xvfb of your own that this script never starts or stops):
    hst_frame_shots.py shoot --instdir DIR --work DIR --out DIR [--display :147] [--look after-light-100 ...] [app ...]
Windows (the image's own python.exe in the console user's session; display scaling is set and restored outside this
script, --scale only names the files):
    python.exe hst_frame_shots.py shoot --instdir <img> --work DIR --out DIR --scale 100 [--look after-dark ...]
Crop the frame parts out of the window shots (any platform with Pillow; Linux shoot crops by itself):
    hst_frame_shots.py crop --out DIR

"before" runs with HST_UI_COAT=0, "after" with the coat on. Linux: light/dark from GTK_THEME (Adwaita /
Adwaita:dark), 125 % from GDK_DPI_SCALE=1.25. Windows: light/dark from the profile's ApplicationAppearance, so the
user's Windows theme is never changed. Each application gives three shots per look,
<app>-<window|backstage|context-menu>-<coat>-<theme>-<scale>.png; regions.json holds where each frame part lies in
them (from the accessibility tree), and crop writes <app>-<part>-<coat>-<theme>-<scale>.png. Parts or shots that
could not be taken are listed in failures.txt. Only the office started here is stopped.
"""
import argparse
import json
import os
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from hst_frame_shot_cases import (APPS, BACKSTAGE_COMMAND, LOOKS, NO_PROMPTS, REGIONS,  # noqa: E402
                                  SIDEBAR_COMMAND, STATES, crop_name, matches, shot_name)

WINDOWS = sys.platform == "win32"
REGIONS_FILE = "regions.json"


class LinuxScreen:
    """Top-level X windows of the test display, their origins and shots."""

    def __init__(self, display):
        self.display = display

    def windows(self):
        import hst_gui
        return {wid for wid, _name in hst_gui.toplevels(self.display)}

    def origin(self, wid):
        out = subprocess.run(["xwininfo", "-display", self.display, "-id", wid], capture_output=True, text=True).stdout
        values = dict(line.strip().split(":", 1) for line in out.splitlines() if ":" in line)
        return int(values["Absolute upper-left X"]), int(values["Absolute upper-left Y"])

    def capture(self, wid, path):
        return subprocess.run(["import", "-display", self.display, "-window", wid, path]).returncode == 0

    def frame_window(self, office, doc, before):
        deadline = time.time() + 45
        while time.time() < deadline:
            new = sorted(self.windows() - before)
            if new:
                time.sleep(1.5)  # the first paint
                return new[-1]
            time.sleep(0.5)
        return None


class WindowsScreen:
    """Top-level VCL windows (class SAL*) in physical pixels, shot through PrintWindow (coat-window-shot.ps1)."""

    def __init__(self):
        import ctypes
        ctypes.windll.user32.SetProcessDPIAware()  # physical pixels, as the office and PrintWindow use

    def windows(self):
        import windows_gui_win32
        return {window[0] for window in windows_gui_win32.office_windows()}

    def origin(self, hwnd):
        import windows_gui_win32
        return windows_gui_win32.window_rect(hwnd)[:2]

    def capture(self, hwnd, path):
        result = subprocess.run(["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File",
                                 os.path.join(HERE, "coat-window-shot.ps1"), "-Hwnd", str(hwnd), "-Path", path],
                                capture_output=True, text=True, timeout=120)
        return result.returncode == 0

    def frame_window(self, office, doc, before):
        import windows_gui_dialogs
        time.sleep(2)
        return windows_gui_dialogs.dialog_hwnd(doc.getCurrentController().getFrame().getContainerWindow())


def find_parts(container, parts):
    """{part: (x, y, width, height) on the screen} of the showing frame parts under a frame's container window (the
    largest showing match of each)."""
    import uno
    from windows_gui_a11y import showing, walk
    if not parts:
        return {}
    roles = {uno.getConstantByName("com.sun.star.accessibility.AccessibleRole." + name): name
             for name in {role for part in parts for role in REGIONS[part][0]}}
    found = {}
    # toolkit windows hand their XAccessible out as a property (VCLXWindow); the frame parts lie near the root
    for context, _depth in walk(container.getProperty("XAccessible"), limit=4):
        try:
            role = roles.get(context.getAccessibleRole())
            if role is None or not showing(context):
                continue
            name = context.getAccessibleName()
            for part in parts:
                if matches(part, role, name):
                    where, size = context.getLocationOnScreen(), context.getSize()
                    area = size.Width * size.Height
                    # the largest match: Sheets has a small split pane of its own beside the sidebar's
                    if area > 0 and (part not in found or area > found[part][2] * found[part][3]):
                        found[part] = (where.X, where.Y, size.Width, size.Height)
        except Exception:  # noqa: BLE001 - a node disposed while we looked
            continue
    return found


def relative(parts, origin):
    return {part: [x - origin[0], y - origin[1], w, h] for part, (x, y, w, h) in parts.items()}


def press_key(office, doc, key, shift=False):
    """A key on the document view, posted through the office's toolkit (XToolkitRobot: a VCL event inside the office,
    handled like typed input, so Shift+F10 opens the context menu; not an input event of the operating system)."""
    import uno
    from com.sun.star.awt import KeyEvent
    event = KeyEvent()
    event.Source = doc.getCurrentController().getFrame().getComponentWindow()
    event.KeyCode = uno.getConstantByName("com.sun.star.awt.Key." + key)
    event.Modifiers = uno.getConstantByName("com.sun.star.awt.KeyModifier.SHIFT") if shift else 0
    toolkit = office.service("com.sun.star.awt.Toolkit")
    toolkit.keyPress(event)
    toolkit.keyRelease(event)


class Run:
    def __init__(self, args, screen):
        self.args, self.screen = args, screen
        self.failures, self.regions = [], {}

    def note(self, text):
        self.failures.append(text)
        print("FAILED", text, flush=True)

    def shoot(self, win, name):
        path = os.path.join(self.args.out, name + ".png")
        if self.screen.capture(win, path):
            print("shot", path, flush=True)
            return True
        self.note(f"{name}: capture failed")
        return False

    def window_state(self, office, app, doc, win, state, look):
        frame = doc.getCurrentController().getFrame()
        name = shot_name(app, state, look)
        if state == "backstage":
            office.dispatch(frame, BACKSTAGE_COMMAND)
            time.sleep(8)  # the File tab lays out its pages and pictures
        parts = find_parts(frame.getContainerWindow(), STATES[state])
        for part in STATES[state]:
            if part not in parts:
                self.note(f"{name}: {part} not found in the accessibility tree")
        if self.shoot(win, name):
            self.regions[name] = relative(parts, self.screen.origin(win))
        if state == "backstage":
            office.dispatch(frame, BACKSTAGE_COMMAND)  # back to the document
            time.sleep(2)

    def context_menu(self, office, app, doc, look):
        name = shot_name(app, "context-menu", look)
        # the document view, not the sidebar or the ribbon, has the keyboard focus
        view = doc.getCurrentController().getFrame().getComponentWindow()
        view.setFocus()
        # Escape first: it closes a start-up hint (Slides shows one) that would take the context-menu key
        press_key(office, doc, "ESCAPE")
        time.sleep(1)
        before = self.screen.windows()
        press_key(office, doc, "F10", shift=True)
        deadline, menu = time.time() + 10, None
        while menu is None and time.time() < deadline:
            time.sleep(0.5)
            new = sorted(self.screen.windows() - before)
            menu = new[-1] if new else None
        if menu is None:
            self.note(f"{name}: no menu window appeared")
            return
        time.sleep(1)
        self.shoot(menu, name)
        press_key(office, doc, "ESCAPE")
        time.sleep(1)

    def look(self, office, look, apps):
        for app in apps:
            factory, text = APPS[app]
            before = self.screen.windows()
            doc = office.load(f"private:factory/{factory}")
            win = self.screen.frame_window(office, doc, before)
            if win is None:
                self.note(f"{app} {'-'.join(look)}: no document window")
                continue
            if text:
                doc.getText().setString(text)
            # the context menu first: once the sidebar is open it keeps the keyboard focus
            self.context_menu(office, app, doc, look)
            office.dispatch(doc.getCurrentController().getFrame(), SIDEBAR_COMMAND)
            time.sleep(3)
            self.window_state(office, app, doc, win, "window", look)
            self.window_state(office, app, doc, win, "backstage", look)
            try:
                doc.close(True)
            except Exception as error:  # noqa: BLE001 - the office is stopped after this look anyway
                self.note(f"{app} {'-'.join(look)}: document did not close ({error})")

    def save(self):
        path = os.path.join(self.args.out, REGIONS_FILE)
        known = {}
        if os.path.exists(path):
            with open(path, encoding="utf-8") as src:
                known = json.load(src)
        known.update(self.regions)
        with open(path, "w", encoding="utf-8") as out:
            json.dump(known, out, indent=1, sort_keys=True)
        with open(os.path.join(self.args.out, "failures.txt"), "w", encoding="utf-8") as out:
            out.write("".join(line + "\n" for line in self.failures))


def crop(out_dir):
    """Write every frame part of regions.json as its own PNG; returns the number written."""
    from PIL import Image
    with open(os.path.join(out_dir, REGIONS_FILE), encoding="utf-8") as src:
        regions = json.load(src)
    written = 0
    for shot, parts in regions.items():
        app, _state, look = shot.split("-", 2)  # menus have no regions: only window and backstage shots
        path = os.path.join(out_dir, shot + ".png")
        if not os.path.exists(path):
            continue
        with Image.open(path) as image:
            for part, (x, y, w, h) in parts.items():
                box = (max(0, x), max(0, y), min(image.width, x + w), min(image.height, y + h))
                if box[2] <= box[0] or box[3] <= box[1]:
                    continue
                image.crop(box).save(os.path.join(out_dir, crop_name(app, part, look.split("-"))
                                                  + ".png"))
                written += 1
    return written


def office_for(args, look):
    coat, theme, scale = look
    work = os.path.join(args.work, "-".join(look))
    env = {"HST_UI_COAT": "0" if coat == "before" else "1"}
    if WINDOWS:
        import hst_gui_windows
        config = list(NO_PROMPTS) + [("/org.openoffice.Office.Common/Appearance", "ApplicationAppearance",
                                      "2" if theme == "dark" else "1")]
        return hst_gui_windows.Office(args.instdir, work, args.port, config=config, env=env, ui=True)
    import hst_gui
    env["GTK_THEME"] = "Adwaita:dark" if theme == "dark" else "Adwaita"
    if scale == "125":
        env["GDK_DPI_SCALE"] = "1.25"
    return hst_gui.Office(args.instdir, work, args.port, display=args.display, config=NO_PROMPTS, env=env)


def shoot(args):
    if WINDOWS:
        looks = [(coat, theme, args.scale) for coat, theme, scale in LOOKS if scale == "100"]
        screen = WindowsScreen()
    else:
        import hst_gui
        os.environ["HST_VCLPLUGIN"] = "gtk3"
        hst_gui.setup_uno(args.instdir)
        args.port = args.port or hst_gui.free_port()
        looks = list(LOOKS)
        screen = LinuxScreen(args.display)
    looks = [look for look in looks if not args.look or any("-".join(look).startswith(sel) for sel in args.look)]
    if not looks:
        raise SystemExit("no look matches " + ", ".join(args.look))
    os.makedirs(args.out, exist_ok=True)
    run = Run(args, screen)
    for look in looks:
        office = office_for(args, look).start()
        try:
            run.look(office, look, args.apps or list(APPS))
        finally:
            office.stop()
            run.save()
    if not WINDOWS:
        print("cropped", crop(args.out), "frame parts", flush=True)
    return 1 if run.failures else 0


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="command", required=True)
    shot = sub.add_parser("shoot")
    shot.add_argument("--instdir", required=True)
    shot.add_argument("--work", required=True)
    shot.add_argument("--out", required=True)
    shot.add_argument("--display", default=":147")
    shot.add_argument("--port", type=int, default=2347 if WINDOWS else 0)
    shot.add_argument("--scale", choices=["100", "125"], default="100", help="Windows: the display scaling now set")
    shot.add_argument("--look", action="append", default=[], help="only looks starting so, e.g. before-light")
    shot.add_argument("apps", nargs="*", help=", ".join(APPS))
    cut = sub.add_parser("crop")
    cut.add_argument("--out", required=True)
    args = parser.parse_args()
    if args.command == "crop":
        print("cropped", crop(args.out), "frame parts")
        return 0
    unknown = [app for app in args.apps if app not in APPS]
    if unknown:
        parser.error("unknown application: " + ", ".join(unknown))
    return shoot(args)


if __name__ == "__main__":
    sys.exit(main())
