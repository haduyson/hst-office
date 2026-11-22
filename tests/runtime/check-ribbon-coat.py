#!/usr/bin/env python3
# SPDX-License-Identifier: LicenseRef-HST-Proprietary
# Copyright (C) 2026 HASON TECH
"""The ribbon in the HST frame coat (FrameCoat/Ribbon), before and after, on a real office: shots of the ribbon and
the facts the coat must not change.

Linux (gtk3, on an Xvfb of your own that this script never starts or stops):
    check-ribbon-coat.py shoot --instdir DIR --work DIR --out DIR [--display :152] [--look after-light-100 ...]
Windows (the image's own python.exe in the console user's session; display scaling is set and restored outside this
script, --scale only names the files):
    python.exe check-ribbon-coat.py shoot --instdir <img> --work DIR --out DIR --scale 100
Then, on any platform with Pillow:
    check-ribbon-coat.py crop --out DIR                        Windows shots: cut the ribbon out of the window shots
    check-ribbon-coat.py compare --out DIR [--out DIR ...]     exit 1 when a fact differs or the coat is missing
    check-ribbon-coat.py sheet --out DIR [--out DIR ...] --png FILE   one before/after sheet

Both looks run with the coat itself on (HST_UI_COAT=1): "before" has FrameCoat/Ribbon=false, "after" the shipped
default, so a pair differs only by the ribbon's frame coat (and shows its rollback switch at work). Cases: Writer
Home, Insert, Layout and the contextual Table tab; Sheets Home and Formulas; Slides Home. Per case the ribbon (the
notebookbar's page tab list) is cropped from the window shot as <app>-<tab>-<coat>-<theme>-<scale>.png, and
facts.json records from the accessibility tree the ribbon's size, the tab names, and every showing element inside
it (role, name, rectangle relative to the ribbon): the commands, boxes, captions and the banner. `compare` requires
those facts to be equal in each pair (no size, place, order or accessible-name change; nothing cut at 125 %
that was not before), and in "after" the frame surface of the design tokens over a large part of the ribbon and a
row of its divider colour at the ribbon's bottom, which "before" does not have. Only the office started here is
stopped.
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

# (app, factory, case, tab name prefix in Vietnamese); "table" first puts the cursor in a new table, so that its
# contextual Table Design tab shows
CASES = [
    ("writer", "swriter", "home", "Trang đầu"),
    ("writer", "swriter", "insert", "Chèn"),
    ("writer", "swriter", "layout", "Bố cục"),
    ("writer", "swriter", "table", "Thiết kế bảng"),
    ("sheets", "scalc", "home", "Trang đầu"),
    ("sheets", "scalc", "formulas", "Công thức"),
    ("slides", "simpress", "home", "Trang đầu"),
]
LOOKS = [(coat, theme, scale) for coat in ("before", "after") for theme in ("light", "dark") for scale in ("100", "125")]
SWITCH = ("/org.openoffice.Office.HSTAppearance/FrameCoat", "Ribbon")

# aFrameSurface and aFrameDivider of the design tokens, light and dark (vcl/source/hst/designtokens.cxx)
SURFACE = {"light": (0xF3, 0xF6, 0xFA), "dark": (0x1A, 0x22, 0x30)}
DIVIDER = {"light": (0x81, 0x8B, 0x9A), "dark": (0x6B, 0x76, 0x89)}


def case_name(app, case, look):
    return f"{app}-{case}-{'-'.join(look)}"


def ribbon_context(frame):
    """The notebookbar's page tab list (the tabs and the selected tab's commands) and its rectangle on the screen."""
    import uno
    from windows_gui_a11y import showing, walk
    tab_list = uno.getConstantByName("com.sun.star.accessibility.AccessibleRole.PAGE_TAB_LIST")
    best = None
    for context, _depth in walk(frame.getContainerWindow().getProperty("XAccessible"), limit=6):
        try:
            if context.getAccessibleRole() != tab_list or not showing(context):
                continue
            where, size = context.getLocationOnScreen(), context.getSize()
            if best is None or size.Width * size.Height > best[1][2] * best[1][3]:
                best = (context, (where.X, where.Y, size.Width, size.Height))
        except Exception:  # noqa: BLE001 - a node disposed while we looked
            continue
    return best


def tab_names(context):
    """The names of the showing tabs (a contextual tab is a child while hidden too)."""
    from windows_gui_a11y import showing
    names = []
    for index in range(context.getAccessibleChildCount()):
        try:
            child = context.getAccessibleChild(index).getAccessibleContext()
            if showing(child):
                names.append(child.getAccessibleName())
        except Exception:  # noqa: BLE001
            continue
    return names


def select_tab(context, prefix, known):
    """Open the showing tab whose name starts with prefix (None: the first showing tab not in known, a contextual
    tab) through its accessible action (a click), else through the tab list's selection."""
    from windows_gui_a11y import showing
    for index in range(context.getAccessibleChildCount()):
        try:
            child = context.getAccessibleChild(index).getAccessibleContext()
            name = child.getAccessibleName()
            if not showing(child) or not name:
                continue
            if (prefix is None and name not in known) or (prefix is not None and name.startswith(prefix)):
                try:
                    child.doAccessibleAction(0)
                except Exception:  # noqa: BLE001 - no action: the selection
                    context.selectAccessibleChild(index)
                return name
        except Exception:  # noqa: BLE001 - a node disposed while we looked
            continue
    return None


def elements(context, rect):
    """[role, name, x, y, w, h] of the showing elements inside the ribbon, relative to it, in tree order (role: the
    AccessibleRole number)."""
    from windows_gui_a11y import showing, walk
    found = []
    rx, ry, _rw, _rh = rect
    for node, _depth in walk(context, limit=24):
        try:
            if not showing(node):
                continue
            where, size = node.getLocationOnScreen(), node.getSize()
            found.append([node.getAccessibleRole(), node.getAccessibleName(), where.X - rx, where.Y - ry,
                          size.Width, size.Height])
        except Exception:  # noqa: BLE001 - a node disposed while we looked
            continue
    return found


class Run(shots.Run):
    def __init__(self, args, screen):
        super().__init__(args, screen)
        self.facts = {}

    def case(self, office, app, factory, case, prefix, look):
        name = case_name(app, case, look)
        before = self.screen.windows()
        doc = office.load(f"private:factory/{factory}")
        win = self.screen.frame_window(office, doc, before)
        if win is None:
            self.note(f"{name}: no document window")
            return
        try:
            frame = doc.getCurrentController().getFrame()
            shots.press_key(office, doc, "ESCAPE")  # a start-up hint (Slides)
            time.sleep(1)
            found = ribbon_context(frame)
            if found is None:
                self.note(f"{name}: ribbon not found in the accessibility tree")
                return
            known = tab_names(found[0])
            if case == "table":  # the cursor in a table opens the contextual Table tabs
                text = doc.getText()
                table = doc.createInstance("com.sun.star.text.TextTable")
                table.initialize(3, 3)
                text.insertTextContent(text.getEnd(), table, False)
                # the view cursor into the first cell: the Table context opens its contextual tab
                cursor = doc.getCurrentController().getViewCursor()
                cursor.gotoRange(table.getCellByName("A1").getText().getStart(), False)
                time.sleep(3)
                found = ribbon_context(frame) or found
            tab = select_tab(found[0], prefix, known)
            if tab is None:
                self.note(f"{name}: tab {prefix or 'contextual'} not found in {tab_names(found[0])}")
                return
            time.sleep(3)  # the page lays out (ladder, banner)
            context, rect = ribbon_context(frame) or found
            origin = self.screen.origin(win)
            facts = {"tab": tab, "tabs": tab_names(context), "ribbon": [rect[2], rect[3]],
                     "rect": [rect[0] - origin[0], rect[1] - origin[1], rect[2], rect[3]],
                     "elements": elements(context, rect)}
            path = os.path.join(self.args.out, name + "-window.png")
            if self.screen.capture(win, path):
                print("shot", name, flush=True)
                if not WINDOWS:  # the Windows image's python has no Pillow: crop there later (crop)
                    crop_ribbon(path, facts["rect"], os.path.join(self.args.out, name + ".png"))
                    os.remove(path)
            else:
                self.note(f"{name}: capture failed")
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


def crop_ribbon(window_png, rect, out_png):
    from PIL import Image
    x, y, w, h = rect
    with Image.open(window_png) as image:
        image.crop((max(0, x), max(0, y), min(image.width, x + w), min(image.height, y + h))).save(out_png)


def crop(out_dir):
    """Crop the ribbon out of every <name>-window.png left by a Windows run; returns the number cropped."""
    with open(os.path.join(out_dir, FACTS), encoding="utf-8") as src:
        facts = json.load(src)
    done = 0
    for name, fact in facts.items():
        window = os.path.join(out_dir, name + "-window.png")
        if os.path.exists(window) and "rect" in fact:
            crop_ribbon(window, fact["rect"], os.path.join(out_dir, name + ".png"))
            os.remove(window)
            done += 1
    return done


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
            for app, factory, case, prefix in CASES:
                if args.case and case_name(app, case, ()).rstrip("-") not in args.case:
                    continue
                try:
                    run.case(office, app, factory, case, prefix, look)
                except Exception as error:  # noqa: BLE001 - the other cases still run
                    run.note(f"{case_name(app, case, look)}: {error!r}")
        finally:
            office.stop()
            run.save()
    return 1 if run.failures else 0


def _close(pixel, want, tolerance):
    return all(abs(pixel[i] - want[i]) <= tolerance for i in range(3))


def surface_share(image_path, surface, tolerance=2):
    """The share of the ribbon's pixels in the surface colour."""
    from PIL import Image
    with Image.open(image_path) as image:
        data = list(image.convert("RGB").getdata())
    return sum(1 for pixel in data if _close(pixel, surface, tolerance)) / max(1, len(data))


def divider_rows(image_path, divider, tolerance=2, rows=3):
    """The share of divider-coloured pixels in the best of the ribbon's last `rows` pixel rows."""
    from PIL import Image
    with Image.open(image_path) as image:
        rgb = image.convert("RGB")
        best = 0.0
        for y in range(max(0, rgb.height - rows), rgb.height):
            row = [rgb.getpixel((x, y)) for x in range(rgb.width)]
            best = max(best, sum(1 for pixel in row if _close(pixel, divider, tolerance)) / max(1, len(row)))
    return best


def _steady(value):
    """value with the banner's accessible name (its artwork rotates at every start: "<brand> — <tagline>") as one
    placeholder, so that only what this coat could change is compared."""
    def name(text):
        return "<banner>" if isinstance(text, str) and " — " in text else text
    if isinstance(value, list):
        return [_steady(item) if isinstance(item, list) else name(item) for item in value]
    return name(value)


def compare(out_dirs):
    """Problems found in the facts and pixels of every before/after pair of the given output directories."""
    problems = []
    for out in out_dirs:
        with open(os.path.join(out, FACTS), encoding="utf-8") as src:
            facts = json.load(src)
        for name, after in sorted(facts.items()):
            app, case, coat, theme, scale = name.split("-")
            if coat != "after":
                continue
            before_name = "-".join((app, case, "before", theme, scale))
            before = facts.get(before_name)
            if before is None:
                problems.append(f"{out}: {name}: no before")
                continue
            for key in ("tab", "tabs", "ribbon", "rect", "elements"):
                if _steady(before.get(key)) != _steady(after.get(key)):
                    detail = "" if key == "elements" else f": before {before.get(key)} after {after.get(key)}"
                    if key == "elements":
                        changed = [pair for pair in zip(before[key], after[key]) if pair[0] != pair[1]]
                        detail = f": {len(before[key])} vs {len(after[key])} elements, first change {changed[:1]}"
                    problems.append(f"{out}: {name}: {key} differs{detail}")
            for look_name, want in ((name, True), (before_name, False)):
                path = os.path.join(out, look_name + ".png")
                if not os.path.exists(path):
                    problems.append(f"{out}: {look_name}: no ribbon shot")
                    continue
                share = surface_share(path, SURFACE[theme])
                if (share >= 0.25) != want:
                    problems.append(f"{out}: {look_name}: frame surface on {share:.0%} of the ribbon")
                rows = divider_rows(path, DIVIDER[theme])
                if want and rows < 0.5:
                    problems.append(f"{out}: {look_name}: divider row on {rows:.0%} of the bottom edge")
    return problems


def sheet(out_dirs, png):
    """One PNG: per case and look a row with the before and after ribbon, one above the other."""
    from PIL import Image, ImageDraw
    rows = []
    for out in out_dirs:
        label = os.path.basename(os.path.normpath(out))
        for app, _factory, case, _prefix in CASES:
            for _coat, theme, scale in [look for look in LOOKS if look[0] == "after"]:
                pair = [os.path.join(out, case_name(app, case, (coat, theme, scale)) + ".png")
                        for coat in ("before", "after")]
                if all(os.path.exists(path) for path in pair):
                    rows.append((f"{label} {app} {case} {theme} {scale}", pair))
    if not rows:
        raise SystemExit("no before/after pairs")
    images = [[Image.open(path).convert("RGB") for path in pair] for _title, pair in rows]
    cell_w = max(image.width for pair in images for image in pair)
    pad, title_h = 10, 16
    height = sum(title_h + pair[0].height + pair[1].height + 3 * pad for pair in images) + pad
    out = Image.new("RGB", (cell_w + 2 * pad, height), "white")
    draw = ImageDraw.Draw(out)
    top = pad
    for (title, _pair), pair in zip(rows, images):
        draw.text((pad, top), title + "  (before above, after below)", fill="black")
        top += title_h
        for image in pair:
            out.paste(image, (pad, top))
            top += image.height + pad
        top += pad
    out.save(png)
    return len(rows)


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="command", required=True)
    shot = sub.add_parser("shoot")
    shot.add_argument("--instdir", required=True)
    shot.add_argument("--work", required=True)
    shot.add_argument("--out", required=True)
    shot.add_argument("--display", default=":152")
    shot.add_argument("--port", type=int, default=2348 if WINDOWS else 0)
    shot.add_argument("--scale", choices=["100", "125"], default="100", help="Windows: the display scaling now set")
    shot.add_argument("--look", action="append", default=[], help="only looks starting so, e.g. before-light")
    shot.add_argument("--case", action="append", default=[], help="only these cases, e.g. writer-table")
    check = sub.add_parser("compare")
    check.add_argument("--out", action="append", required=True)
    cut = sub.add_parser("crop")
    cut.add_argument("--out", required=True)
    pairs = sub.add_parser("sheet")
    pairs.add_argument("--out", action="append", required=True)
    pairs.add_argument("--png", required=True)
    args = parser.parse_args()
    if args.command == "shoot":
        return shoot(args)
    if args.command == "crop":
        print("cropped", crop(args.out))
        return 0
    if args.command == "sheet":
        print("rows", sheet(args.out, args.png))
        return 0
    problems = compare(args.out)
    for problem in problems:
        print("FAIL", problem)
    print("compare:", "PASS" if not problems else f"{len(problems)} problem(s)")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
