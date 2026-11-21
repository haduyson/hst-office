#!/usr/bin/env python3
# SPDX-License-Identifier: AGPL-3.0-only
"""The frame's coat of popup and context menus (FrameCoat/Menus): shots of the menus a user opens most, a pixel
check of the menu's outline, and the menu-open latency with the part switched off and on.

"before" is the same package with FrameCoat/Menus=false (the menu items keep the dialogs' coat), "after" with it on.

Linux (gtk3 on an Xvfb of your own, started and stopped outside this script; run it through
tests/runtime/no-hst-telemetry.sh):
    check-context-menu-coat.py shoot --instdir DIR --work DIR --out DIR --display :161 [--look after-dark] [case ...]
    check-context-menu-coat.py latency --instdir DIR --work DIR --out DIR --display :161 [--rounds 4 --trials 15]
    check-context-menu-coat.py verify --out DIR [--platform windows]   (pixel checks of shots taken without Pillow)
Windows (the image's own python.exe in the console session; scaling is set outside, --scale names the files):
    python.exe check-context-menu-coat.py shoot --instdir IMG --work DIR --out DIR --scale 125
    python.exe check-context-menu-coat.py latency --instdir IMG --work DIR --out DIR

Cases: writer-text, writer-table, writer-graphic (the context menus of text, a table cell and a picture),
sheets-cell, slides-slide, and ribbon-dropdown (the Paste button's drop-down on Writer's Home tab). A context menu is
opened with Shift+F10 posted through XToolkitRobot (a VCL event inside the office, not an input event of the
operating system); the ribbon's drop-down through the button's accessible action togglePopup. Down highlights the
third item (GTK menus take the keys from the X server: xdotool on the test display).
Shots: <case>-<coat>-<theme>-<scale>.png, the menu's own window; on Windows also <...>-screen.png, the menu as shown
on the screen (the system's rounded corners, outline and shadow; needs an active console). "check" lines compare a
menu's edge pixels with the tokens; results.json has them all.

latency: alternating rounds of an office with the part off and one with it on; each round opens and closes the
Writer text menu --trials times and records the time from posting Shift+F10 to the menu's window being shown. The
result is the median of each side and their ratio (the phase's limit: at most 1.02).
"""
import argparse
import json
import os
import statistics
import subprocess
import sys
import threading
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, "..", "..", "scripts", "perf"))
from hst_frame_shots import LinuxScreen, WindowsScreen, press_key  # noqa: E402
from hst_frame_shot_cases import NO_PROMPTS  # noqa: E402

WINDOWS = sys.platform == "win32"
MENUS_SWITCH = ("/org.openoffice.Office.HSTAppearance/FrameCoat", "Menus")
TEXT = "Thử nghiệm menu chuột phải: Cắt, Sao chép, Dán và Định dạng đoạn văn."
CASES = ("writer-text", "writer-table", "writer-graphic", "sheets-cell", "slides-slide", "ribbon-dropdown")
FACTORY = {"writer": "swriter", "sheets": "scalc", "slides": "simpress", "ribbon": "swriter"}
PASTE = ("Dán", "Paste")
# the menus' tokens (include/vcl/hst/designtokens.hxx): surface and outline per theme
TOKENS = {"light": {"surface": (0xFF, 0xFF, 0xFF), "border": (0x81, 0x8B, 0x9A)},
          "dark": {"surface": (0x1E, 0x25, 0x32), "border": (0x6B, 0x76, 0x89)}}


def looks(args):
    scales = [args.scale] if WINDOWS else ["100", "125"]
    found = [(coat, theme, scale) for coat in ("before", "after") for theme in ("light", "dark") for scale in scales]
    return [look for look in found if not args.look or any("-".join(look).startswith(sel) for sel in args.look)]


def office_for(args, coat, theme, scale, tag=""):
    work = os.path.join(args.work, "-".join((coat, theme, scale)) + tag)
    config = list(NO_PROMPTS) + [(MENUS_SWITCH[0], MENUS_SWITCH[1], "false" if coat == "before" else "true")]
    if WINDOWS:
        import hst_gui_windows
        config.append(("/org.openoffice.Office.Common/Appearance", "ApplicationAppearance",
                       "2" if theme == "dark" else "1"))
        return hst_gui_windows.Office(args.instdir, work, args.port, config=config, env={"HST_UI_COAT": "1"}, ui=True)
    import hst_gui
    env = {"HST_UI_COAT": "1", "GTK_THEME": "Adwaita:dark" if theme == "dark" else "Adwaita"}
    if scale == "125":
        env["GDK_DPI_SCALE"] = "1.25"
    return hst_gui.Office(args.instdir, work, args.port, display=args.display, config=config, env=env)


class Keys:
    """Keys for an open menu: GTK menus grab the X keyboard, VCL menus take XToolkitRobot events."""

    def __init__(self, args, office, doc):
        self.args, self.office, self.doc = args, office, doc

    def menu(self, key):
        if WINDOWS:
            press_key(self.office, self.doc, key.upper())
        else:
            subprocess.run(["xdotool", "key", "--clearmodifiers", key.capitalize()],
                           env=dict(os.environ, DISPLAY=self.args.display), check=False)


def toggle_ribbon_popup(doc, names):
    """Open the drop-down of the first showing ribbon button named one of `names` through its accessible action
    "togglePopup" (the action a screen reader uses; inside the office, not an input event)."""
    from windows_gui_a11y import showing, walk
    window = doc.getCurrentController().getFrame().getContainerWindow()
    for context, _depth in walk(window.getProperty("XAccessible"), limit=12):
        try:
            if context.getAccessibleName() not in names or not showing(context):
                continue
            actions = [context.getAccessibleActionDescription(i) for i in range(context.getAccessibleActionCount())]
            if "togglePopup" in actions:
                # the drop-down's menu runs its own modal loop: the call returns when the menu closes
                index = actions.index("togglePopup")
                threading.Thread(target=context.doAccessibleAction, args=(index,), daemon=True).start()
                return True
        except Exception:  # noqa: BLE001 - a node disposed while we looked, or no actions
            continue
    return False


def picture(work):
    """A small PNG for the picture case: a blue field with a yellow disc, written without any imaging library
    (the office's own Python has none)."""
    import struct
    import zlib
    path = os.path.join(work, "menu-picture.png")
    if os.path.exists(path):
        return path
    width, height = 160, 100
    rows = bytearray()
    for y in range(height):
        rows.append(0)  # no filter
        for x in range(width):
            inside = (x - 80) ** 2 + (y - 50) ** 2 <= 30 ** 2
            rows += bytes((0xFF, 0xC1, 0x07) if inside else (0x2E, 0x6F, 0xD8))

    def chunk(kind, data):
        return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", zlib.crc32(kind + data) & 0xFFFFFFFF)
    os.makedirs(work, exist_ok=True)
    with open(path, "wb") as out:
        out.write(b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0))
                  + chunk(b"IDAT", zlib.compress(bytes(rows))) + chunk(b"IEND", b""))
    return path


def prepare(office, case, doc, work):
    """Put the case's object under the keyboard: text, a table cell, a selected picture, a cell, the slide."""
    import uno
    controller = doc.getCurrentController()
    if case.startswith("writer") or case == "ribbon-dropdown":
        doc.getText().setString(TEXT)
    if case == "ribbon-dropdown":  # something on the clipboard, so the Paste drop-down lists its formats
        frame = controller.getFrame()
        office.dispatch(frame, ".uno:SelectAll")
        office.dispatch(frame, ".uno:Copy")
        office.dispatch(frame, ".uno:GoToEndOfDoc")
    if case == "writer-table":
        table = doc.createInstance("com.sun.star.text.TextTable")
        table.initialize(3, 3)
        text = doc.getText()
        text.insertTextContent(text.getEnd(), table, False)
        table.getCellByName("B2").setString("Ô bảng")
        controller.getViewCursor().gotoRange(table.getCellByName("B2").getStart(), False)
    elif case == "writer-graphic":
        from com.sun.star.beans import PropertyValue
        provider = office.service("com.sun.star.graphic.GraphicProvider")
        url = PropertyValue()
        url.Name, url.Value = "URL", uno.systemPathToFileUrl(picture(work))
        graphic = doc.createInstance("com.sun.star.text.TextGraphicObject")
        graphic.Graphic = provider.queryGraphic((url,))
        text = doc.getText()
        text.insertTextContent(text.getEnd(), graphic, False)
        controller.select(graphic)
    elif case == "sheets-cell":
        sheet = doc.getSheets().getByIndex(0)
        sheet.getCellRangeByName("B2").setString("Ô tính")
        controller.select(sheet.getCellRangeByName("B2"))
    time.sleep(1)


class Run:
    def __init__(self, args, screen):
        self.args, self.screen = args, screen
        self.results, self.failures = [], []

    def note(self, text):
        self.failures.append(text)
        print("FAILED", text, flush=True)

    def open_menu(self, office, case, doc):
        """The menu's window, opened from the keyboard, or None."""
        view = doc.getCurrentController().getFrame().getComponentWindow()
        if case != "ribbon-dropdown":
            view.setFocus()
            press_key(office, doc, "ESCAPE")  # a start-up hint (Slides) would take the key
            time.sleep(1)
            if case == "writer-graphic":  # Escape dropped the picture's selection
                prepare_select_graphic(doc)
        before = self.screen.windows()
        if case == "ribbon-dropdown":
            if not toggle_ribbon_popup(doc, PASTE):
                self.note(f"{case}: the Paste button's drop-down was not found")
                return None
        else:
            press_key(office, doc, "F10", shift=True)
        deadline = time.time() + 10
        while time.time() < deadline:
            time.sleep(0.3)
            new = sorted(self.screen.windows() - before)
            if new:
                time.sleep(1)
                return new[-1]
        return None

    def case(self, office, case, look):
        coat, theme, scale = look
        name = f"{case}-{coat}-{theme}-{scale}"
        before = self.screen.windows()
        doc = office.load(f"private:factory/{FACTORY[case.split('-')[0]]}")
        win = self.screen.frame_window(office, doc, before)
        if win is None:
            self.note(f"{name}: no document window")
            return
        prepare(office, case, doc, self.args.work)
        menu = self.open_menu(office, case, doc)
        if menu is None:
            self.note(f"{name}: no menu window appeared")
        else:
            keys = Keys(self.args, office, doc)
            for _ in range(3):
                keys.menu("down")
                time.sleep(0.3)
            time.sleep(0.7)
            path = os.path.join(self.args.out, name + ".png")
            screen = os.path.join(self.args.out, name + "-screen.png") if WINDOWS else None
            if screen and not screen_shot(menu, screen):
                screen = None
                self.note(f"{name}: screen capture failed")
            if self.screen.capture(menu, path):
                print("shot", path, flush=True)
                self.check(name, path, coat, theme, screen)
            else:
                self.note(f"{name}: capture failed")
            keys.menu("escape")
            time.sleep(1)
        try:
            doc.close(True)
        except Exception as error:  # noqa: BLE001 - the office stops after the look anyway
            self.note(f"{name}: document did not close ({error})")

    def check(self, name, path, coat, theme, screen=None):
        """The middle of the menu's left edge: Windows (VCL menus) after: the window's ring in the surface, and the
        outline either rounded just inside it (the coat's) or drawn by the system on the screen (Windows 11);
        Linux (GTK): the menu's surface colour inside its border."""
        try:
            from PIL import Image
        except ImportError:  # the office's own Python (Windows): checked afterwards with `verify`
            self.results.append({"shot": name, "coat": coat, "theme": theme, "screen": bool(screen), "ok": None})
            return
        with Image.open(path) as image:
            rgb = image.convert("RGB")
            y = rgb.height // 2
            edge = [rgb.getpixel((x, y)) for x in range(6)]
        token = TOKENS[theme]
        near = lambda a, b: all(abs(p - q) <= 3 for p, q in zip(a, b))  # noqa: E731
        system_outline = None
        if screen:
            with Image.open(screen) as image:
                shown = image.convert("RGB")
                # the window's top edge, mid-way, as shown (SCREEN_MARGIN around the window)
                system_outline = near(shown.getpixel((shown.width // 2, SCREEN_MARGIN)), token["border"])
        if WINDOWS:
            outline = any(near(p, token["border"]) for p in edge[1:4]) or bool(system_outline)
            ring_is_surface = near(edge[0], token["surface"])
            ok = (outline and ring_is_surface) if coat == "after" else not ring_is_surface
        else:
            ok = near(rgb.getpixel((rgb.width // 2, 2)), token["surface"]) if coat == "after" else True
        self.results.append({"shot": name, "coat": coat, "theme": theme, "screen": bool(screen), "edge": edge,
                             "system_outline": system_outline, "ok": ok})
        print("check", name, "PASS" if ok else "FAIL", edge, flush=True)
        if not ok:
            self.note(f"{name}: menu edge {edge} does not match the {coat} look")

    def save(self, extra=None):
        data = {"results": self.results, "failures": self.failures}
        data.update(extra or {})
        with open(os.path.join(self.args.out, "results.json"), "w", encoding="utf-8") as out:
            json.dump(data, out, indent=1, ensure_ascii=False)


SCREEN_MARGIN = 16


def screen_shot(hwnd, path):
    """The menu as shown on the screen, SCREEN_MARGIN pixels around its window (the system's corners and shadow)."""
    import windows_gui_win32
    left, top, right, bottom = windows_gui_win32.window_rect(hwnd)
    m = SCREEN_MARGIN
    result = subprocess.run(["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File",
                             os.path.join(HERE, "coat-screen-shot.ps1"), "-Left", str(left - m), "-Top", str(top - m),
                             "-Width", str(right - left + 2 * m), "-Height", str(bottom - top + 2 * m), "-Path", path],
                            capture_output=True, text=True, timeout=120)
    return result.returncode == 0


def prepare_select_graphic(doc):
    graphics = doc.getGraphicObjects()
    if graphics.getCount():
        doc.getCurrentController().select(graphics.getByIndex(0))
        time.sleep(0.5)


def screen_for(args):
    if WINDOWS:
        return WindowsScreen()
    import hst_gui
    os.environ["HST_VCLPLUGIN"] = "gtk3"
    hst_gui.setup_uno(args.instdir)
    args.port = args.port or hst_gui.free_port()
    return LinuxScreen(args.display)


def shoot(args):
    screen = screen_for(args)
    os.makedirs(args.out, exist_ok=True)
    run = Run(args, screen)
    for look in looks(args):
        office = office_for(args, *look).start()
        try:
            for case in args.cases or CASES:
                run.case(office, case, look)
        finally:
            office.stop()
            run.save()
    return 1 if run.failures else 0


class MenuWatch:
    """Fast snapshots of the shown top-level windows (X11 through Xlib, Windows through EnumWindows)."""

    def __init__(self, args):
        if WINDOWS:
            import windows_gui_win32
            self.snapshot = lambda: {w[0] for w in windows_gui_win32.office_windows()}
        else:
            from context_menu_x11 import X11Driver
            self.driver = X11Driver(args.display)
            self.snapshot = lambda: set(self.driver.viewable_windows())


def latency_round(args, coat, round_no, watch):
    office = office_for(args, coat, "light", args.scale or "100", tag=f"-latency-{round_no}").start()
    times = []
    try:
        before = watch.snapshot()
        doc = office.load("private:factory/swriter")
        LinuxScreen(args.display).frame_window(office, doc, before) if not WINDOWS else time.sleep(3)
        prepare(office, "writer-text", doc, args.work)
        view = doc.getCurrentController().getFrame().getComponentWindow()
        view.setFocus()
        keys = Keys(args, office, doc)
        for trial in range(args.trials + 1):  # the first opening warms up and is not counted
            before = watch.snapshot()
            start = time.perf_counter()
            press_key(office, doc, "F10", shift=True)
            shown = None
            while time.perf_counter() - start < 5:
                if watch.snapshot() - before:
                    shown = time.perf_counter() - start
                    break
            if shown is not None and trial:
                times.append(shown * 1000)
            time.sleep(0.3)
            keys.menu("escape")
            time.sleep(0.5)
        doc.close(True)
    finally:
        office.stop()
    return times


def latency(args):
    screen_for(args)
    os.makedirs(args.out, exist_ok=True)
    watch = MenuWatch(args)
    samples = {"before": [], "after": []}
    rounds = []
    for round_no in range(args.rounds):
        order = ("before", "after") if round_no % 2 == 0 else ("after", "before")
        for coat in order:
            times = latency_round(args, coat, round_no, watch)
            samples[coat].extend(times)
            rounds.append({"round": round_no, "coat": coat, "ms": times})
            print(coat, round_no, "median", round(statistics.median(times), 2) if times else None, flush=True)
    medians = {coat: statistics.median(values) for coat, values in samples.items() if values}
    ratio = medians["after"] / medians["before"] if len(medians) == 2 else None
    result = {"medians_ms": medians, "ratio": ratio, "limit": 1.02, "n": {k: len(v) for k, v in samples.items()},
              "rounds": rounds}
    with open(os.path.join(args.out, "latency.json"), "w", encoding="utf-8") as out:
        json.dump(result, out, indent=1)
    print("latency medians", medians, "ratio", ratio, flush=True)
    return 0 if ratio is not None and ratio <= 1.02 else 1


def verify(args):
    """The pixel checks of shots taken where Pillow was missing (Windows), from their results.json."""
    global WINDOWS
    WINDOWS = args.platform == "windows"
    with open(os.path.join(args.out, "results.json"), encoding="utf-8") as src:
        taken = json.load(src)["results"]
    run = Run(args, None)
    for shot in taken:
        name = shot["shot"]
        screen = os.path.join(args.out, name + "-screen.png")
        run.check(name, os.path.join(args.out, name + ".png"), shot["coat"], shot["theme"],
                  screen if os.path.exists(screen) else None)
    run.save({"verified_from": "results.json"})
    return 1 if run.failures else 0


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="command", required=True)
    for name in ("shoot", "latency"):
        cmd = sub.add_parser(name)
        cmd.add_argument("--instdir", required=True)
        cmd.add_argument("--work", required=True)
        cmd.add_argument("--out", required=True)
        cmd.add_argument("--display", default=":161")
        cmd.add_argument("--port", type=int, default=2349 if WINDOWS else 0)
        cmd.add_argument("--scale", choices=["100", "125"], default="100" if WINDOWS else None)
    shot = sub.choices["shoot"]
    shot.add_argument("--look", action="append", default=[], help="only looks starting so, e.g. after-dark")
    shot.add_argument("cases", nargs="*", help=", ".join(CASES))
    ver = sub.add_parser("verify")
    ver.add_argument("--out", required=True)
    ver.add_argument("--platform", choices=["windows", "linux"], default="windows")
    lat = sub.choices["latency"]
    lat.add_argument("--rounds", type=int, default=4)
    lat.add_argument("--trials", type=int, default=15)
    args = parser.parse_args()
    if args.command == "verify":
        return verify(args)
    if args.command == "shoot":
        unknown = [case for case in args.cases if case not in CASES]
        if unknown:
            parser.error("unknown case: " + ", ".join(unknown))
        return shoot(args)
    return latency(args)


if __name__ == "__main__":
    sys.exit(main())
