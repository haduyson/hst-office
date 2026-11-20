#!/usr/bin/env python3
# SPDX-License-Identifier: AGPL-3.0-only
"""The sidebar's frame in the HST coat (FrameCoat/Sidebar), before and after, on a real office: shots of the sidebar
and the facts the coat must not change.

Linux (gtk3, on an Xvfb of your own that this script never starts or stops):
    check-sidebar-coat.py shoot --instdir DIR --work DIR --out DIR [--display :147] [--look after-light-100 ...]
Windows (the image's own python.exe in the console user's session; display scaling is set and restored outside this
script, --scale only names the files):
    python.exe check-sidebar-coat.py shoot --instdir <img> --work DIR --out DIR --scale 100
Then, on any platform with Pillow:
    check-sidebar-coat.py compare --out DIR [--out DIR ...]     exit 1 when a fact differs
    check-sidebar-coat.py sheet --out DIR --png FILE            one before/after sheet of every shot

Both looks run with the coat itself on (HST_UI_COAT=1): "before" has FrameCoat/Sidebar=false, "after" the shipped
default, so a pair differs only by the sidebar's frame coat (and shows its rollback switch at work). For each case
(Writer: Properties, Styles, Gallery, Navigator; Sheets and Slides: Properties) the sidebar is cropped from the
window shot as <app>-<deck>-<coat>-<theme>-<scale>.png, and facts.json records, from the accessibility tree:
the tab bar's buttons (name, role, checked, place and size relative to the sidebar), the sidebar's size, and the
names the keyboard focus visits from Ctrl+F5 (into the sidebar) over Tab. `compare` requires the facts of each
before/after pair to be equal and, in "after", the selected-tab indicator beside the checked tab: the accent colour
of the design tokens left of its button, which "before" does not have. Only the office started here is stopped.
"""
import argparse
import json
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import hst_frame_shots as shots  # noqa: E402
from hst_frame_shot_cases import NO_PROMPTS  # noqa: E402

WINDOWS = sys.platform == "win32"
FACTS = "facts.json"

# (app, factory, deck id); the deck opens with .uno:SidebarDeck.<deck id>
CASES = [
    ("writer", "swriter", "PropertyDeck"),
    ("writer", "swriter", "StyleListDeck"),
    ("writer", "swriter", "GalleryDeck"),
    ("writer", "swriter", "NavigatorDeck"),
    ("sheets", "scalc", "PropertyDeck"),
    ("slides", "simpress", "PropertyDeck"),
]
LOOKS = [(coat, theme, scale) for coat in ("before", "after") for theme in ("light", "dark") for scale in ("100", "125")]
SWITCH = ("/org.openoffice.Office.HSTAppearance/FrameCoat", "Sidebar")
TAB_STOPS = 6  # Tab presses after Ctrl+F5

# The accent (aSelectedIndicator) of the design tokens, light and dark (vcl/source/hst/designtokens.cxx)
ACCENT = {"light": (0x1A, 0x56, 0xC8), "dark": (0x8A, 0xB4, 0xF8)}
PILL = {"light": (0xD5, 0xE5, 0xFA), "dark": (0x26, 0x3B, 0x5E)}


def case_name(app, deck, look):
    return f"{app}-{deck}-{'-'.join(look)}"


def tab_buttons(container, sidebar):
    """The tab bar's buttons: [name, role, checked, x, y, width, height] relative to the sidebar (x, y, w, h on the
    screen), top to bottom: the showing buttons inside the sidebar in its rightmost column (the menu button and
    the deck tabs)."""
    import uno
    from windows_gui_a11y import showing, walk
    role = {uno.getConstantByName("com.sun.star.accessibility.AccessibleRole." + name): name
            for name in ("TOGGLE_BUTTON", "PUSH_BUTTON", "BUTTON_MENU", "MENU_BUTTON") if _has_role(name)}
    checked = uno.getConstantByName("com.sun.star.accessibility.AccessibleStateType.CHECKED")
    pressed = uno.getConstantByName("com.sun.star.accessibility.AccessibleStateType.PRESSED")
    sx, sy, sw, sh = sidebar
    found = []
    for context, _depth in walk(container, limit=16):
        try:
            if context.getAccessibleRole() not in role or not showing(context):
                continue
            where, size = context.getLocationOnScreen(), context.getSize()
            if not (sx <= where.X < sx + sw and sy <= where.Y < sy + sh):
                continue
            states = context.getAccessibleStateSet()
            found.append([context.getAccessibleName(), role[context.getAccessibleRole()],
                          bool(states & (checked | pressed)), where.X - sx, where.Y - sy, size.Width, size.Height])
        except Exception:  # noqa: BLE001 - a node disposed while we looked
            continue
    if not found:
        return []
    # the tab bar: the buttons in the rightmost column
    right = max(button[3] for button in found)
    return sorted((button for button in found if button[3] >= right - 4), key=lambda button: button[4])


def _has_role(name):
    import uno
    try:
        uno.getConstantByName("com.sun.star.accessibility.AccessibleRole." + name)
        return True
    except Exception:  # noqa: BLE001 - not in this office's API
        return False


def focus_walk(office, doc):
    """The accessible names the keyboard focus visits: Ctrl+F5 (the sidebar), then TAB_STOPS times Tab."""
    import uno
    from com.sun.star.awt import KeyEvent
    toolkit = office.service("com.sun.star.awt.Toolkit")
    window = doc.getCurrentController().getFrame().getContainerWindow()

    def key(name, ctrl=False):
        event = KeyEvent()
        event.Source = doc.getCurrentController().getFrame().getComponentWindow()
        event.KeyCode = uno.getConstantByName("com.sun.star.awt.Key." + name)
        event.Modifiers = uno.getConstantByName("com.sun.star.awt.KeyModifier.MOD1") if ctrl else 0
        toolkit.keyPress(event)
        toolkit.keyRelease(event)
        time.sleep(0.6)

    def focused():
        from windows_gui_a11y import walk
        focus = uno.getConstantByName("com.sun.star.accessibility.AccessibleStateType.FOCUSED")
        for context, _depth in walk(window.getProperty("XAccessible"), limit=16):
            try:
                if context.getAccessibleStateSet() & focus:
                    return context.getAccessibleName()
            except Exception:  # noqa: BLE001
                continue
        return None

    doc.getCurrentController().getFrame().getComponentWindow().setFocus()
    key("F5", ctrl=True)
    names = [focused()]
    for _ in range(TAB_STOPS):
        key("TAB")
        names.append(focused())
    key("ESCAPE")
    return names


class Run(shots.Run):
    def __init__(self, args, screen):
        super().__init__(args, screen)
        self.facts = {}

    def case(self, office, app, factory, deck, look):
        name = case_name(app, deck, look)
        before = self.screen.windows()
        doc = office.load(f"private:factory/{factory}")
        win = self.screen.frame_window(office, doc, before)
        if win is None:
            self.note(f"{name}: no document window")
            return
        try:
            frame = doc.getCurrentController().getFrame()
            shots.press_key(office, doc, "ESCAPE")  # a start-up hint (Slides)
            office.dispatch(frame, ".uno:SidebarDeck." + deck)
            time.sleep(4)
            parts = shots.find_parts(frame.getContainerWindow(), ("sidebar",))
            if "sidebar" not in parts:
                self.note(f"{name}: sidebar not found in the accessibility tree")
                return
            x, y, w, h = parts["sidebar"]
            origin = self.screen.origin(win)
            facts = {"sidebar": [w, h],
                     "tabs": tab_buttons(frame.getContainerWindow().getProperty("XAccessible"), parts["sidebar"])}
            if not facts["tabs"] and WINDOWS:
                self.note(f"{name}: no tab bar buttons found")
            path = os.path.join(self.args.out, name + "-window.png")
            if self.screen.capture(win, path):
                from PIL import Image
                with Image.open(path) as image:
                    box = (x - origin[0], y - origin[1], x - origin[0] + w, y - origin[1] + h)
                    image.crop(box).save(os.path.join(self.args.out, name + ".png"))
                os.remove(path)
                print("shot", name, flush=True)
            else:
                self.note(f"{name}: capture failed")
            if deck == "PropertyDeck" and WINDOWS:  # gtk3's sidebar is outside the office's accessibility tree
                facts["focus"] = focus_walk(office, doc)
            self.facts[name] = facts
        finally:
            try:
                doc.close(True)
            except Exception as error:  # noqa: BLE001 - the office is stopped after this look anyway
                self.note(f"{name}: document did not close ({error})")

    def save(self):
        path = os.path.join(self.args.out, FACTS)
        known = {}
        if os.path.exists(path):
            with open(path, encoding="utf-8") as src:
                known = json.load(src)
        known.update(self.facts)
        with open(path, "w", encoding="utf-8") as out:
            json.dump(known, out, indent=1, sort_keys=True, ensure_ascii=False)
        with open(os.path.join(self.args.out, "failures.txt"), "w", encoding="utf-8") as out:
            out.write("".join(line + "\n" for line in self.failures))


def office_for(args, look):
    coat, theme, scale = look
    work = os.path.join(args.work, "-".join(look))
    config = list(NO_PROMPTS) + [(SWITCH[0], SWITCH[1], "false" if coat == "before" else "true")]
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
    return hst_gui.Office(args.instdir, work, args.port, display=args.display, config=config, env=env)


def shoot(args):
    if WINDOWS:
        looks = [(coat, theme, args.scale) for coat, theme, scale in LOOKS if scale == "100"]
        screen = shots.WindowsScreen()
    else:
        import hst_gui
        os.environ["HST_VCLPLUGIN"] = "gtk3"
        hst_gui.setup_uno(args.instdir)
        args.port = args.port or hst_gui.free_port()
        looks = list(LOOKS)
        screen = shots.LinuxScreen(args.display)
    looks = [look for look in looks if not args.look or any("-".join(look).startswith(sel) for sel in args.look)]
    if not looks:
        raise SystemExit("no look matches " + ", ".join(args.look))
    os.makedirs(args.out, exist_ok=True)
    run = Run(args, screen)
    for look in looks:
        office = office_for(args, look).start()
        try:
            for app, factory, deck in CASES:
                run.case(office, app, factory, deck, look)
        finally:
            office.stop()
            run.save()
    return 1 if run.failures else 0


def has_indicator(image_path, tab, accent, tolerance=40):
    """Whether accent-coloured pixels lie in the strip left of the checked tab button (its left edge to 8 px before),
    over the middle half of its height."""
    from PIL import Image
    _name, _role, _checked, x, y, _w, h = tab
    with Image.open(image_path) as image:
        rgb = image.convert("RGB")
        for px in range(max(0, x - 8), min(rgb.width, x + 2)):
            for py in range(y + h // 4, min(rgb.height, y + 3 * h // 4)):
                pixel = rgb.getpixel((px, py))
                if all(abs(pixel[i] - accent[i]) <= tolerance for i in range(3)):
                    return True
    return False


def has_pill(image_path, pill, column=48, tolerance=6, least=200):
    """Whether at least `least` pixels of the pill colour lie in the rightmost `column` pixels (the tab bar)."""
    from PIL import Image
    with Image.open(image_path) as image:
        rgb = image.convert("RGB")
        box = rgb.crop((max(0, rgb.width - column), 0, rgb.width, rgb.height))
        return sum(1 for pixel in box.getdata()
                   if all(abs(pixel[i] - pill[i]) <= tolerance for i in range(3))) >= least


def compare(out_dirs):
    """Problems found in the facts of every before/after pair of the given output directories."""
    problems = []
    for out in out_dirs:
        with open(os.path.join(out, FACTS), encoding="utf-8") as src:
            facts = json.load(src)
        for name, after in sorted(facts.items()):
            app, deck, coat, theme, scale = name.split("-")
            if coat != "after":
                continue
            before_name = "-".join((app, deck, "before", theme, scale))
            before = facts.get(before_name)
            if before is None:
                problems.append(f"{out}: {name}: no before")
                continue
            for key in ("sidebar", "tabs", "focus"):
                if before.get(key) != after.get(key):
                    problems.append(f"{out}: {name}: {key} differs: before {before.get(key)} after {after.get(key)}")
            if not after.get("tabs") and not before.get("tabs"):
                # gtk3: the sidebar is native GTK, outside the office's accessibility tree; the open deck's
                # pill is looked for in the tab bar column instead
                for look_name, want in ((name, True), (before_name, False)):
                    path = os.path.join(out, look_name + ".png")
                    if os.path.exists(path) and has_pill(path, PILL[theme]) != want:
                        problems.append(f"{out}: {look_name}: open-deck pill {'missing' if want else 'present'}")
                continue
            checked = [tab for tab in after.get("tabs", []) if tab[2]]
            if len(checked) != 1:
                problems.append(f"{out}: {name}: {len(checked)} checked tabs")
                continue
            for look_name, want in ((name, True), (before_name, False)):
                path = os.path.join(out, look_name + ".png")
                if os.path.exists(path) and has_indicator(path, checked[0], ACCENT[theme]) != want:
                    problems.append(f"{out}: {look_name}: selected-tab indicator {'missing' if want else 'present'}")
    return problems


def sheet(out_dirs, png):
    """One PNG: per case and look a row with the before and after sidebar side by side."""
    from PIL import Image, ImageDraw
    rows = []
    for out in out_dirs:
        label = os.path.basename(os.path.normpath(out))
        for app, _factory, deck in CASES:
            for _coat, theme, scale in [look for look in LOOKS if look[0] == "after"]:
                pair = [os.path.join(out, case_name(app, deck, (coat, theme, scale)) + ".png")
                        for coat in ("before", "after")]
                if all(os.path.exists(path) for path in pair):
                    rows.append((f"{label} {app} {deck} {theme} {scale}", pair))
    if not rows:
        raise SystemExit("no before/after pairs")
    images = [[Image.open(path).convert("RGB") for path in pair] for _title, pair in rows]
    cell_w = max(image.width for pair in images for image in pair)
    cell_h = max(image.height for pair in images for image in pair)
    per_row = 4  # pairs per sheet row
    pad, title_h = 12, 18
    cols = min(per_row, len(rows))
    sheet_rows = (len(rows) + per_row - 1) // per_row
    out = Image.new("RGB", (cols * (2 * cell_w + 3 * pad), sheet_rows * (cell_h + title_h + pad) + pad), "white")
    draw = ImageDraw.Draw(out)
    for index, ((title, _pair), pair) in enumerate(zip(rows, images)):
        left = (index % per_row) * (2 * cell_w + 3 * pad) + pad
        top = (index // per_row) * (cell_h + title_h + pad) + pad
        draw.text((left, top), title + "  (before | after)", fill="black")
        for column, image in enumerate(pair):
            out.paste(image, (left + column * (cell_w + pad), top + title_h))
    out.save(png)
    return len(rows)


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
    check = sub.add_parser("compare")
    check.add_argument("--out", action="append", required=True)
    pairs = sub.add_parser("sheet")
    pairs.add_argument("--out", action="append", required=True)
    pairs.add_argument("--png", required=True)
    args = parser.parse_args()
    if args.command == "compare":
        problems = compare(args.out)
        for problem in problems:
            print("FAILED", problem)
        print("compare:", "ok" if not problems else f"{len(problems)} problem(s)")
        return 1 if problems else 0
    if args.command == "sheet":
        print("pairs", sheet(args.out, args.png))
        return 0
    return shoot(args)


if __name__ == "__main__":
    sys.exit(main())
