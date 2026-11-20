#!/usr/bin/env python3
# SPDX-License-Identifier: AGPL-3.0-only
"""Screenshots of the document tab strip with 1, 3 and 8 documents open in one window of Writer, Sheets and
Slides (8 overflows the strip), plus Writer + Sheets + Slides in the HST Office window (Linux), one inactive tab
under the pointer: the before/after pairs of the strip's frame coat.

Linux (gtk3, on an Xvfb of your own that this script never starts or stops; the pointer is moved with xdotool):
    hst_doctabs_shots.py shoot --instdir DIR --work DIR --out DIR [--display :171] [--look after-light] [case ...]
Windows (the image's own python.exe in the console user's session; display scaling is set and restored outside
this script, --scale only names the files; the pointer is moved with SetCursorPos, nothing is clicked):
    python.exe hst_doctabs_shots.py shoot --instdir <img> --work DIR --out DIR --scale 125 [--look before-dark]

"before" runs with FrameCoat/DocumentTabs=false, "after" with it on; pass the build before the strip's coat as
--instdir for "before" (its strip also keeps the old application colours, which the coat build changes in both
looks). Each case writes <case>-window-<look>.png (the window) and
<case>-doctabs-<look>.png (the strip, cut out where the accessibility tree places it). Cases or parts that could
not be shot are listed in failures.txt. Only the office started here is stopped.
"""
import argparse
import os
import subprocess
import sys
import threading
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from hst_frame_shot_cases import NO_PROMPTS  # noqa: E402

WINDOWS = sys.platform == "win32"
FACTORIES = {"writer": "swriter", "sheets": "scalc", "slides": "simpress"}
# case: the documents to open, in order, in one window ("mixed" starts from the Start Center, so the documents
# share the HST Office window, which takes every kind)
CASES = {f"{app}-{count}": [app] * count for app in FACTORIES for count in (1, 3, 8)}
CASES["mixed-3"] = ["writer", "sheets", "slides"]
LOOKS = [(coat, theme, scale) for coat in ("before", "after") for theme in ("light", "dark") for scale in ("100", "125")]
STRIP_NAMES = ("thẻ tài liệu", "document tabs")
STRIP_ROLES = ("PANEL", "PAGE_TAB_LIST")


def look_name(look):
    return "-".join(look)


def strip_and_tabs(container):
    """((x, y, w, h) of the strip on the screen, [(x, y, w, h) of each tab]) from the accessibility tree."""
    import uno
    from windows_gui_a11y import showing, walk
    roles = {uno.getConstantByName("com.sun.star.accessibility.AccessibleRole." + name) for name in STRIP_ROLES}
    tab_role = uno.getConstantByName("com.sun.star.accessibility.AccessibleRole.PAGE_TAB")
    for context, _depth in walk(container.getProperty("XAccessible"), limit=4):
        try:
            if context.getAccessibleRole() not in roles or not showing(context):
                continue
            if not any(name in (context.getAccessibleName() or "").lower() for name in STRIP_NAMES):
                continue
            where, size = context.getLocationOnScreen(), context.getSize()
            tabs = []
            for i in range(context.getAccessibleChildCount()):
                child = context.getAccessibleChild(i).getAccessibleContext()
                if child.getAccessibleRole() == tab_role:
                    at, extent = child.getLocationOnScreen(), child.getSize()
                    tabs.append((at.X, at.Y, extent.Width, extent.Height, child.getAccessibleStateSet()))
            return (where.X, where.Y, size.Width, size.Height), tabs
        except Exception:  # noqa: BLE001 - a node disposed while we looked
            continue
    return None, []


def hover_target(strip, tabs):
    """A screen point over an inactive tab beside the selected one (its title, not its close button); without
    accessible tabs (a build before the strip's accessible tree) the second tab of an even split."""
    import uno
    selected = uno.getConstantByName("com.sun.star.accessibility.AccessibleStateType.SELECTED")
    if tabs:
        order = sorted(range(len(tabs)), key=lambda i: tabs[i][0])
        active = next((i for i in order if tabs[i][4] & selected), order[-1])
        pos = order.index(active)
        other = order[pos - 1] if pos > 0 else (order[pos + 1] if len(order) > 1 else None)
        if other is None:
            return None
        x, y, w, h, _states = tabs[other]
        return x + w // 3, y + h // 2
    x, y, w, h = strip
    return x + min(w // 4, 160), y + h // 2


class Linux:
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

    def window_of(self, frame):
        import hst_gui
        title = frame.Title
        for wid, name in hst_gui.toplevels(self.display):
            if name.startswith(title):
                return wid
        return None

    def pointer(self, x, y):
        env = dict(os.environ, DISPLAY=self.display)
        subprocess.run(["xdotool", "mousemove", str(x), str(y)], env=env, check=False, timeout=15)


class Windows:
    def __init__(self):
        import ctypes
        ctypes.windll.user32.SetProcessDPIAware()  # physical pixels, as the office and PrintWindow use

    def origin(self, hwnd):
        import windows_gui_win32
        return windows_gui_win32.window_rect(hwnd)[:2]

    def capture(self, hwnd, path):
        result = subprocess.run(["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File",
                                 os.path.join(HERE, "coat-window-shot.ps1"), "-Hwnd", str(hwnd), "-Path", path],
                                capture_output=True, text=True, timeout=120)
        return result.returncode == 0

    def window_of(self, frame):
        import windows_gui_dialogs
        return windows_gui_dialogs.dialog_hwnd(frame.getContainerWindow())

    def pointer(self, x, y):
        import ctypes
        ctypes.windll.user32.SetCursorPos(int(x), int(y))


def office_for(args, look, nodefault):
    coat, theme, scale = look
    work = os.path.join(args.work, look_name(look))
    config = list(NO_PROMPTS) + [("/org.openoffice.Office.HSTAppearance/FrameCoat", "DocumentTabs",
                                  "false" if coat == "before" else "true"),
                                 # no tooltip over the hovered tab: it would cover the strip in the shot
                                 ("/org.openoffice.Office.Common/Help", "Tip", "false"),
                                 ("/org.openoffice.Office.Common/Help", "ExtendedTip", "false")]
    env = {"HST_UI_COAT": "1"}
    if WINDOWS:
        import hst_gui_windows
        config.append(("/org.openoffice.Office.Common/Appearance", "ApplicationAppearance",
                       "2" if theme == "dark" else "1"))
        return hst_gui_windows.Office(args.instdir, work, args.port, config=config, env=env, ui=True)
    import hst_gui
    env["GTK_THEME"] = "Adwaita:dark" if theme == "dark" else "Adwaita"
    if scale == "125":
        env["GDK_DPI_SCALE"] = "1.25"
    return hst_gui.Office(args.instdir, work, args.port, display=args.display, config=config, env=env,
                          nodefault=nodefault)


def quit_office(office, frame):
    """.uno:Quit on the office's own dispatch (as the Quit command does), then stop() as the fallback."""
    if frame is not None:
        threading.Thread(target=office.dispatch, args=(frame, ".uno:Quit"), daemon=True).start()
        time.sleep(5)
    office.stop()


def shoot_case(args, screen, look, case, failures):
    import uno_main_thread_load
    name = f"{case}-%s-{look_name(look)}"
    mixed = case.startswith("mixed")
    office = office_for(args, look, nodefault=not mixed).start()
    frame = None
    try:
        if mixed:
            time.sleep(6)  # the Start Center: the first document replaces it and keeps the HST Office window
        for i, app in enumerate(CASES[case]):
            target = "_default" if mixed and i == 0 else "_blank"
            doc = uno_main_thread_load.load(office.desktop(), f"private:factory/{FACTORIES[app]}", target)
            frame = doc.getCurrentController().getFrame()
            time.sleep(1.5)
        time.sleep(3)  # the strip lays out and the last document paints
        win = screen.window_of(frame)
        if win is None:
            failures.append(f"{name % 'window'}: no window")
            return
        strip, tabs = strip_and_tabs(frame.getContainerWindow())
        if strip is None:
            failures.append(f"{name % 'doctabs'}: strip not found in the accessibility tree")
        elif len(CASES[case]) > 1:
            point = hover_target(strip, tabs)
            if point:
                screen.pointer(*point)
                time.sleep(1.5)
        path = os.path.join(args.out, name % "window" + ".png")
        if not screen.capture(win, path):
            failures.append(f"{name % 'window'}: capture failed")
            return
        print("shot", path, flush=True)
        if strip is not None:
            from PIL import Image
            ox, oy = screen.origin(win)
            x, y, w, h = strip
            with Image.open(path) as image:
                box = (max(0, x - ox), max(0, y - oy), min(image.width, x - ox + w), min(image.height, y - oy + h))
                image.crop(box).save(os.path.join(args.out, name % "doctabs" + ".png"))
        screen.pointer(5, 5)
    except Exception as error:  # noqa: BLE001 - recorded, the next case gets a fresh office
        failures.append(f"{name % 'window'}: {error}")
    finally:
        quit_office(office, frame)


def shoot(args):
    if WINDOWS:
        import hst_gui_windows
        hst_gui_windows.install()
        looks = [(coat, theme, args.scale) for coat, theme, scale in LOOKS if scale == "100"]
        screen = Windows()
        cases = [case for case in CASES if not case.startswith("mixed")]  # no Start Center start on Windows
    else:
        import hst_gui
        os.environ["HST_VCLPLUGIN"] = "gtk3"
        hst_gui.setup_uno(args.instdir)
        args.port = args.port or hst_gui.free_port()
        looks = list(LOOKS)
        screen = Linux(args.display)
        cases = list(CASES)
    looks = [look for look in looks if not args.look or any(look_name(look).startswith(sel) for sel in args.look)]
    cases = [case for case in cases if not args.cases or case in args.cases]
    if not looks or not cases:
        raise SystemExit("nothing selected")
    os.makedirs(args.out, exist_ok=True)
    failures = []
    for look in looks:
        for case in cases:
            shoot_case(args, screen, look, case, failures)
    with open(os.path.join(args.out, f"failures-{os.getpid()}.txt"), "w", encoding="utf-8") as out:
        out.write("".join(line + "\n" for line in failures))
    for line in failures:
        print("FAILED", line, flush=True)
    return 1 if failures else 0


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="command", required=True)
    shot = sub.add_parser("shoot")
    shot.add_argument("--instdir", required=True)
    shot.add_argument("--work", required=True)
    shot.add_argument("--out", required=True)
    shot.add_argument("--display", default=":171")
    shot.add_argument("--port", type=int, default=2347 if WINDOWS else 0)
    shot.add_argument("--scale", choices=["100", "125"], default="100", help="Windows: the display scaling now set")
    shot.add_argument("--look", action="append", default=[], help="only looks starting so, e.g. after-dark")
    shot.add_argument("cases", nargs="*", help=", ".join(CASES))
    args = parser.parse_args()
    return shoot(args)


if __name__ == "__main__":
    sys.exit(main())
