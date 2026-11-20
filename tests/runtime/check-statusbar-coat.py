#!/usr/bin/env python3
# SPDX-License-Identifier: AGPL-3.0-only
"""Runtime check of the HST status bar (the StatusBar part of the frame coat) in Writer, Linux gtk3, on an Xvfb of
your own that this script never starts or stops:

    check-statusbar-coat.py --instdir DIR --work DIR [--display :147] [--out DIR] [--chars 1000]

Looks: coat-light and coat-dark (the coat on), plain (HST_UI_COAT=0) and contrast (the coat on, GTK theme
HighContrast in the profile's GTK settings).
- coat on: the bar's surface and top line are the frame tokens; the items a click acts on show the hover (a sweep
  over every item in Writer, Sheets and Slides), the zoom slider does not; off and in high contrast the bar keeps the
  platform's look.
- every look: a click on the zoom percentage opens the Zoom dialog; a click on the slider's middle sets 100 % and a
  drag to the right zooms in, to the same values with and without the coat.
- coat-light against plain: the bar's height and every item's place (the click areas) are equal, and typing --chars
  characters (the word count repaints on each) takes no longer than --slack times as long.
The pointer is moved and clicked with xdotool on the test display (real X events on this run's own Xvfb); keys are
posted through the office's toolkit (XToolkitRobot). Shots of the bar go to --out. Only the office started here is
stopped. Exit 0 when every check passes.
"""
import argparse
import os
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

# the frame tokens (vcl/source/hst/designtokens.cxx)
SURFACE = {"light": (0xF3, 0xF6, 0xFA), "dark": (0x1A, 0x22, 0x30)}
DIVIDER = {"light": (0x81, 0x8B, 0x9A), "dark": (0x6B, 0x76, 0x89)}
HOVER = {"light": (0xE1, 0xEC, 0xFB), "dark": (0x22, 0x30, 0x47)}

LOOKS = {
    "coat-light": {"HST_UI_COAT": "1", "GTK_THEME": "Adwaita"},
    "coat-dark": {"HST_UI_COAT": "1", "GTK_THEME": "Adwaita:dark"},
    "plain": {"HST_UI_COAT": "0", "GTK_THEME": "Adwaita"},
    "contrast": {"HST_UI_COAT": "1", "GTK_THEME": "HighContrast"},
}
# the hover sweep in the coat looks: per application its factory and the text that starts its page/sheet/slide
# position item, which a click acts on (Go to Page, the Navigator)
SWEEP = {
    "writer": ("swriter", ("Trang", "Page")),
    "sheets": ("scalc", ("Trang tính", "Sheet")),
    "slides": ("simpress", ("Trang chiếu", "Slide")),
}
NO_PROMPTS = [("/org.openoffice.Office.HSTUpdate", "AutoCheck", "false"),
              ("/org.hasontech.hstoffice.UpdateCheck", "AutoCheck", "false")]


class Failures(list):
    def check(self, ok, text):
        print(("ok    " if ok else "FAIL  ") + text, flush=True)
        if not ok:
            self.append(text)


def xdotool(display, *args):
    """Pointer input on the test display (an Xvfb of this run's own, no window manager): real X events."""
    subprocess.run(["xdotool", *[str(arg) for arg in args]], env={**os.environ, "DISPLAY": display}, check=True)


def move(display, x, y):
    xdotool(display, "mousemove", x, y)


def click(display, x, y):
    xdotool(display, "mousemove", x, y, "click", 1)


def drag(display, x, y, x2):
    xdotool(display, "mousemove", x, y, "mousedown", 1)
    time.sleep(0.5)
    # step by step, each motion handled before the next, so the last one is not lost before the release
    for step in range(1, 5):
        xdotool(display, "mousemove", x + (x2 - x) * step // 4, y)
        time.sleep(0.3)
    time.sleep(0.5)
    xdotool(display, "mouseup", 1)


def type_chars(office, doc, count):
    """`count` letters typed into the document view; returns the seconds until the text holds them all."""
    import uno
    from com.sun.star.awt import KeyEvent
    view = doc.getCurrentController().getFrame().getComponentWindow()
    view.setFocus()
    event = KeyEvent()
    event.Source, event.KeyChar, event.KeyCode = view, "a", uno.getConstantByName("com.sun.star.awt.Key.A")
    robot = office.service("com.sun.star.awt.Toolkit")
    start = time.monotonic()
    for _ in range(count):
        robot.keyPress(event)
        robot.keyRelease(event)
    deadline = start + 300
    while len(doc.getText().getString()) < count and time.monotonic() < deadline:
        time.sleep(0.05)
    return time.monotonic() - start


def bar_items(container):
    """(bar (x, y, w, h), [(x, y, w, h, text)] of its showing items) on the screen, from the accessibility tree."""
    import uno
    from windows_gui_a11y import showing, walk
    bar_role = uno.getConstantByName("com.sun.star.accessibility.AccessibleRole.STATUS_BAR")
    for context, _depth in walk(container.getProperty("XAccessible"), limit=4):
        try:
            if context.getAccessibleRole() != bar_role or not showing(context):
                continue
            where, size = context.getLocationOnScreen(), context.getSize()
            items = []
            for index in range(context.getAccessibleChildCount()):
                item = context.getAccessibleChild(index).getAccessibleContext()
                if not showing(item):
                    continue
                at, extent = item.getLocationOnScreen(), item.getSize()
                text = item.getText() if hasattr(item, "getText") else item.getAccessibleName()
                items.append((at.X, at.Y, extent.Width, extent.Height, text or item.getAccessibleName() or ""))
            return (where.X, where.Y, size.Width, size.Height), items
        except Exception:  # noqa: BLE001 - a node disposed while we looked
            continue
    return None, []


def zoom_value(doc):
    return doc.getCurrentController().getViewSettings().getPropertyValue("ZoomValue")


def set_zoom(doc, value):
    settings = doc.getCurrentController().getViewSettings()
    settings.setPropertyValue("ZoomType", 3)  # BY_VALUE
    settings.setPropertyValue("ZoomValue", value)


class Look:
    def __init__(self, args, name, failures):
        self.args, self.name, self.failures = args, name, failures
        self.result = {}

    def run(self):
        import hst_gui
        from hst_frame_shots import LinuxScreen
        env = dict(LOOKS[self.name])
        if self.name == "contrast":
            # the office reads the theme's name from GTK's settings (GTK_THEME alone does not set it)
            gtk = os.path.join(self.args.work, self.name, "home", ".config", "gtk-3.0")
            os.makedirs(gtk, exist_ok=True)
            with open(os.path.join(gtk, "settings.ini"), "w", encoding="utf-8") as out:
                out.write("[Settings]\ngtk-theme-name=HighContrast\n")
            env["XDG_CONFIG_HOME"] = os.path.dirname(gtk)
        office = hst_gui.Office(self.args.instdir, os.path.join(self.args.work, self.name), self.args.port,
                                display=self.args.display, config=NO_PROMPTS, env=env).start()
        screen = LinuxScreen(self.args.display)
        try:
            before = screen.windows()
            doc = office.load("private:factory/swriter")
            win = screen.frame_window(office, doc, before)
            self.failures.check(win is not None, f"{self.name}: a Writer window")
            if win is None:
                return self.result
            time.sleep(2)
            self.checks(office, doc, screen, win)
            if self.name.startswith("coat"):
                self.sweep(office, "writer", doc, screen, win)
            doc.setModified(False)
            doc.close(True)
            if self.name.startswith("coat"):
                for app in ("sheets", "slides"):
                    before = screen.windows()
                    doc = office.load(f"private:factory/{SWEEP[app][0]}")
                    win = screen.frame_window(office, doc, before)
                    self.failures.check(win is not None, f"{self.name}: a {app} window")
                    if win is not None:
                        time.sleep(2)
                        self.sweep(office, app, doc, screen, win)
                    doc.setModified(False)
                    doc.close(True)
        finally:
            office.stop()
        return self.result

    def sweep(self, office, app, doc, screen, win):
        """The pointer over each item of the bar in turn: which show the hover. The zoom percentage and the
        position item must, the zoom slider must not. Writes statusbar-<look>-sweep-<app>.png (one row per
        item, hovered)."""
        from PIL import Image
        display, theme = self.args.display, "dark" if self.name.endswith("dark") else "light"
        bar, items = bar_items(doc.getCurrentController().getFrame().getContainerWindow())
        if bar is None or len(items) < 3:
            self.failures.check(False, f"{self.name} {app}: the status bar and its items")
            return
        x0, y0 = screen.origin(win)
        rows, crops = [], []
        path = os.path.join(self.args.out, f"statusbar-{self.name}-sweep-{app}.png")
        for item in items:
            move(display, item[0] + item[2] // 2, item[1] + item[3] // 2)
            time.sleep(0.6)
            screen.capture(win, path)
            with Image.open(path) as image:
                crop = image.convert("RGB").crop((bar[0] - x0, bar[1] - y0, bar[0] - x0 + bar[2], bar[1] - y0 + bar[3]))
            crops.append(crop)
            # hovered: the hover colour shows somewhere along the item's middle row (beside its text or icon)
            row = [crop.getpixel((x, bar[3] // 2)) for x in range(item[0] - bar[0], item[0] - bar[0] + item[2])]
            rows.append((item[4], row.count(HOVER[theme]) >= 2))
        move(display, bar[0] + bar[2] // 2, bar[1] - 200)  # back over the document
        sheet = Image.new("RGB", (bar[2], (bar[3] + 2) * len(crops)), "white")
        for index, crop in enumerate(crops):
            sheet.paste(crop, (0, index * (bar[3] + 2)))
        sheet.save(path)
        print(f"{self.name} {app}: " + "; ".join(f"{text or '(icon)'}: {'hover' if on else '-'}"
                                                for text, on in rows), flush=True)
        prefixes = SWEEP[app][1]
        position = next((on for text, on in rows if text.startswith(prefixes)), None)
        self.failures.check(rows[-1][1] and not rows[-2][1] and position,
                            f"{self.name} {app}: hover on the zoom percentage and the position item, not on the slider")

    def checks(self, office, doc, screen, win):
        from PIL import Image
        frame = doc.getCurrentController().getFrame()
        container = frame.getContainerWindow()
        bar, items = bar_items(container)
        self.failures.check(bar is not None and len(items) >= 4, f"{self.name}: the status bar and its items")
        if bar is None or len(items) < 4:
            return
        zoom, slider = items[-1], items[-2]
        self.result["geometry"] = (bar[3], [item[:4] for item in items])
        self.failures.check(zoom[4].endswith("%"), f"{self.name}: the last item is the zoom percentage ({zoom[4]!r})")

        coat = self.name.startswith("coat")
        theme = "dark" if self.name.endswith("dark") else "light"

        def shot(name):
            path = os.path.join(self.args.out, f"statusbar-{self.name}-{name}.png")
            screen.capture(win, path)
            x, y = screen.origin(win)
            with Image.open(path) as image:
                crop = image.convert("RGB").crop((bar[0] - x, bar[1] - y, bar[0] - x + bar[2], bar[1] - y + bar[3]))
            crop.save(path)
            return crop, (bar[0], bar[1])

        # hover over the zoom percentage, then over the zoom slider (its own buttons: no hover)
        display = self.args.display
        mx, my = zoom[0] + zoom[2] // 2, zoom[1] + zoom[3] // 2
        move(display, mx, my)
        time.sleep(1)
        image, (bx, by) = shot("hover-zoom")
        in_zoom = (zoom[0] - bx + 3, zoom[1] - by + zoom[3] // 2)
        surface_at = (bar[2] - 3, bar[3] // 2)
        if coat:
            self.failures.check(image.getpixel(surface_at) == SURFACE[theme],
                                f"{self.name}: the bar's surface {image.getpixel(surface_at)} is the frame token")
            self.failures.check(image.getpixel((bar[2] // 2, 0)) == DIVIDER[theme],
                                f"{self.name}: the top line {image.getpixel((bar[2] // 2, 0))} is the frame divider")
            self.failures.check(image.getpixel(in_zoom) == HOVER[theme],
                                f"{self.name}: the zoom percentage shows the hover {image.getpixel(in_zoom)}")
        else:  # plain, and contrast (the coat switched on: high contrast turns it off)
            self.failures.check(image.getpixel(surface_at) != SURFACE["light"]
                                or image.getpixel((bar[2] // 2, 0)) != DIVIDER["light"],
                                f"{self.name}: the bar keeps the platform's look")
        move(display, slider[0] + slider[2] // 2, slider[1] + 2)
        time.sleep(1)
        image, _ = shot("hover-slider")
        in_slider = (slider[0] - bx + 2, slider[1] - by + slider[3] // 2)
        if coat:
            self.failures.check(image.getpixel(in_slider) == SURFACE[theme]
                                and image.getpixel(in_zoom) == SURFACE[theme],
                                f"{self.name}: no hover on the zoom slider, none left on the zoom percentage")

        # the slider: a click in its middle sets 100 %, a drag to the right zooms in
        set_zoom(doc, 150)
        time.sleep(1)
        sx, sy = slider[0] + slider[2] // 2, slider[1] + slider[3] // 2
        click(display, sx, sy)
        time.sleep(1)
        at_centre = zoom_value(doc)
        drag(display, sx, sy, sx + 20)
        time.sleep(1)
        dragged = zoom_value(doc)
        self.result["slider"] = (at_centre, dragged)
        self.failures.check(at_centre == 100 and dragged > 100,
                            f"{self.name}: slider click 150 % -> {at_centre} %, drag -> {dragged} %")

        # a click on the zoom percentage opens the Zoom dialog
        before = screen.windows()
        click(display, mx, my)
        deadline, dialog = time.time() + 15, None
        while dialog is None and time.time() < deadline:
            time.sleep(0.5)
            new = sorted(screen.windows() - before)
            dialog = new[-1] if new else None
        self.failures.check(dialog is not None, f"{self.name}: a click on the zoom percentage opens the Zoom dialog")
        if dialog is not None:
            import hst_gui
            hst_gui.send_close_request(dialog, self.args.display)
            time.sleep(1.5)

        if self.name in ("coat-light", "plain") and self.args.chars:
            set_zoom(doc, 100)
            self.result["typing"] = type_chars(office, doc, self.args.chars)
            print(f"{self.name}: {self.args.chars} characters typed in {self.result['typing']:.2f} s", flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--instdir", required=True)
    parser.add_argument("--work", required=True)
    parser.add_argument("--out", default=None, help="shots of the bar (default: WORK/shots)")
    parser.add_argument("--display", default=":147")
    parser.add_argument("--port", type=int, default=0)
    parser.add_argument("--chars", type=int, default=1000, help="characters typed for the timing (0: none)")
    parser.add_argument("--slack", type=float, default=1.10, help="allowed ratio of the typing times, coat / plain")
    parser.add_argument("--look", action="append", choices=list(LOOKS), default=[])
    args = parser.parse_args()
    import hst_gui
    os.environ["HST_VCLPLUGIN"] = "gtk3"
    hst_gui.setup_uno(args.instdir)
    args.port = args.port or hst_gui.free_port()
    args.out = args.out or os.path.join(args.work, "shots")
    os.makedirs(args.out, exist_ok=True)

    failures = Failures()
    results = {name: Look(args, name, failures).run() for name in (args.look or list(LOOKS))}
    coat, plain = results.get("coat-light", {}), results.get("plain", {})
    if "geometry" in coat and "geometry" in plain:
        failures.check(coat["geometry"] == plain["geometry"],
                       f"the bar's height and the items' places are unchanged: {coat['geometry'] == plain['geometry']}")
    if "slider" in coat and "slider" in plain:
        failures.check(coat["slider"] == plain["slider"],
                       f"the slider zooms alike: {coat['slider']} / {plain['slider']}")
    if "typing" in coat and "typing" in plain:
        ratio = coat["typing"] / plain["typing"]
        failures.check(ratio <= args.slack, f"typing with the coat takes {ratio:.3f} times as long (<= {args.slack})")
    print("PASS" if not failures else f"{len(failures)} FAILED", flush=True)
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
