#!/usr/bin/env python3
# SPDX-License-Identifier: LicenseRef-HST-Proprietary
# Copyright (C) 2026 HASON TECH
"""Before/after screenshots of the HST coat on lists and trees, sliders, progress bars, group frames, separators and
tooltips, in Writer.

Linux (gtk3, on an Xvfb of your own that this script never starts or stops; launch it through no-hst-telemetry.sh):
    coat-controls-shots.py --instdir DIR --work DIR --out DIR [--display :151] [--look after-light-100 ...] [case ...]
Windows (the image's own python.exe in the console user's session; the display scaling is set and restored outside
this script, --scale only names the files):
    python.exe coat-controls-shots.py --instdir <img> --work DIR --out DIR --scale 100 [--look after-dark ...]

"before" runs with HST_UI_COAT=0, "after" with the coat on; light/dark and 125 % as in hst_frame_shots.py. Each look
opens one Writer document with 80 headings (a long Navigator tree) and an image, then shoots every case:
<case>-<coat>-<theme>-<scale>.png. Window cases also write the cropped part, <case>-part-<look>.png. Cases that
could not be shot are listed in failures.txt (the part's box is in <case>-part-<look>.json, so shots taken
where Pillow is missing can be cropped later). The mouse is only moved (for the tooltip), never clicked. Only the
office started here is stopped.
"""
import argparse
import glob
import json
import os
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import hst_frame_shots  # noqa: E402
from hst_frame_shot_cases import LOOKS  # noqa: E402

WINDOWS = hst_frame_shots.WINDOWS

# case: (kind, command, frame part to crop or None)
CASES = {
    "navigator": ("deck", ".uno:SidebarDeck.NavigatorDeck", "sidebar"),  # a long tree
    "styles": ("deck", ".uno:SidebarDeck.StyleListDeck", "sidebar"),  # a list
    "styles-hover": ("deck-hover", ".uno:SidebarDeck.StyleListDeck", "sidebar"),  # a list row under the mouse
    "progress": ("progress", None, "statusbar"),  # the status bar's progress bar, as while saving a large file
    "tooltip": ("tooltip", None, None),  # a status bar item's tooltip
    "compress-image": ("dialog", ".uno:CompressGraphic", None),  # sliders and group frames
    "tip-of-the-day": ("dialog", ".uno:TipOfTheDay", None),  # a separator line
}


def fill_document(office, doc, instdir):
    """80 headings on two levels with a line of text each, and an image at the end (selected)."""
    import uno
    from com.sun.star.beans import PropertyValue
    text = doc.getText()
    cursor = text.createTextCursor()
    paragraph_break = uno.getConstantByName("com.sun.star.text.ControlCharacter.PARAGRAPH_BREAK")
    for chapter in range(1, 21):
        for level, title in ((1, f"Chương {chapter}: Tổng quan"), (2, "Mục tiêu"), (2, "Phạm vi"),
                             (2, "Kết quả")):
            cursor.ParaStyleName = f"Heading {level}"
            text.insertString(cursor, title, False)
            text.insertControlCharacter(cursor, paragraph_break, False)
            cursor.ParaStyleName = "Standard"
            text.insertString(cursor, "Nội dung thử nghiệm lớp áo giao diện HST.", False)
            text.insertControlCharacter(cursor, paragraph_break, False)
    images = sorted(glob.glob(os.path.join(instdir, "share", "gallery", "**", "*.png"), recursive=True))
    if not images:
        return None
    url = PropertyValue()
    url.Name, url.Value = "URL", uno.systemPathToFileUrl(os.path.abspath(images[0]))
    graphic = office.service("com.sun.star.graphic.GraphicProvider").queryGraphic((url,))
    image = doc.createInstance("com.sun.star.text.TextGraphicObject")
    image.Graphic = graphic
    text.insertTextContent(text.getEnd(), image, False)
    return image


class Shots:
    def __init__(self, args, screen):
        self.args, self.screen = args, screen
        self.failures = []

    def note(self, text):
        print("FAILED", text, flush=True)
        self.failures.append(text)

    def path(self, case, look, part=False):
        return os.path.join(self.args.out, f"{case}{'-part' if part else ''}-{'-'.join(look)}.png")

    def shoot(self, win, case, look, part=None, office=None, doc=None):
        path = self.path(case, look)
        if not self.screen.capture(win, path):
            self.note(f"{case} {'-'.join(look)}: capture failed")
            return
        print("shot", path, flush=True)
        if not part:
            return
        container = doc.getCurrentController().getFrame().getContainerWindow()
        found = hst_frame_shots.find_parts(container, [part])
        if part not in found:
            self.note(f"{case} {'-'.join(look)}: no {part} found to crop")
            return
        x, y, w, h = hst_frame_shots.relative(found, self.screen.origin(win))[part]
        with open(self.path(case, look, part=True)[:-4] + ".json", "w", encoding="utf-8") as out:
            json.dump([x, y, w, h], out)
        try:
            from PIL import Image
        except ImportError:  # the Windows image's python: crop later from the .json
            return
        with Image.open(path) as image:
            box = (max(0, x), max(0, y), min(image.width, x + w), min(image.height, y + h))
            if box[2] > box[0] and box[3] > box[1]:
                image.crop(box).save(self.path(case, look, part=True))

    def new_window(self, before, timeout=25):
        deadline = time.time() + timeout
        while time.time() < deadline:
            new = sorted(self.screen.windows() - before)
            if new:
                time.sleep(1.5)  # its first paint
                return new[-1]
            time.sleep(0.5)
        return None

    def close(self, win):
        if WINDOWS:
            import windows_gui_dialogs
            return windows_gui_dialogs.close_hwnd(win)
        import hst_gui
        hst_gui.send_close_request(win, self.args.display)
        time.sleep(1.5)
        return win not in self.screen.windows()

    def move_mouse(self, x, y):
        """Only a move (the tooltip shows under it): no button is pressed."""
        if WINDOWS:
            import ctypes
            ctypes.windll.user32.SetCursorPos(int(x), int(y))
        else:
            subprocess.run(["xdotool", "mousemove", str(int(x)), str(int(y))],
                           env=dict(os.environ, DISPLAY=self.args.display), check=False)

    def case(self, office, ui, doc, win, image, name, look):
        kind, command, part = CASES[name]
        frame = doc.getCurrentController().getFrame()
        if kind == "deck":
            office.dispatch(frame, command)
            time.sleep(3)
            self.shoot(win, name, look, part, office, doc)
        elif kind == "deck-hover":
            office.dispatch(frame, command)
            time.sleep(3)
            found = hst_frame_shots.find_parts(frame.getContainerWindow(), [part])
            if part not in found:
                self.note(f"{name} {'-'.join(look)}: no {part} to hover")
                return
            x, y, w, h = found[part]
            self.move_mouse(x + w // 4, y + h // 2)  # over a row in the middle of the deck's list
            time.sleep(1.5)
            self.shoot(win, name, look, part, office, doc)
            self.move_mouse(x + w // 4, y - 200)
            time.sleep(1)
        elif kind == "progress":
            indicator = frame.createStatusIndicator()
            indicator.start("Đang lưu tệp lớn…", 100)
            indicator.setValue(45)
            time.sleep(2)
            self.shoot(win, name, look, part, office, doc)
            indicator.end()
        elif kind == "tooltip":
            found = hst_frame_shots.find_parts(frame.getContainerWindow(), ["statusbar"])
            if "statusbar" not in found:
                self.note(f"{name} {'-'.join(look)}: no status bar to hover")
                return
            x, y, _w, h = found["statusbar"]
            before = self.screen.windows()
            self.move_mouse(x + 40, y + h // 2)  # the page number item, which has a tooltip
            tip = self.new_window(before, timeout=8)
            if tip is None:
                self.note(f"{name} {'-'.join(look)}: no tooltip appeared")
            else:
                self.shoot(tip, name, look)
            self.move_mouse(x + 40, y - 200)
            time.sleep(1)
        elif kind == "dialog":
            if command == ".uno:CompressGraphic":
                if image is None:
                    self.note(f"{name} {'-'.join(look)}: no image to compress")
                    return
                doc.getCurrentController().select(image)
                time.sleep(1)
            before = self.screen.windows()
            ui.executeDialog(command)
            dialog = self.new_window(before)
            if dialog is None:
                self.note(f"{name} {'-'.join(look)}: no dialog window")
                return
            self.shoot(dialog, name, look)
            if not self.close(dialog):
                self.note(f"{name} {'-'.join(look)}: dialog did not close")

    def look(self, office, look, names):
        before = self.screen.windows()
        doc = office.load("private:factory/swriter")
        win = self.screen.frame_window(office, doc, before)
        if win is None:
            self.note(f"writer {'-'.join(look)}: no document window")
            return
        image = fill_document(office, doc, self.args.instdir)
        time.sleep(2)
        ui = office.service("com.sun.star.ui.test.UITest")
        for name in names:
            try:
                self.case(office, ui, doc, win, image, name, look)
            except Exception as error:  # noqa: BLE001 - one case failing must not stop the other shots
                self.note(f"{name} {'-'.join(look)}: {error}")
        try:
            doc.close(True)
        except Exception as error:  # noqa: BLE001 - the office is stopped after this look anyway
            self.note(f"writer {'-'.join(look)}: document did not close ({error})")


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--instdir", required=True)
    parser.add_argument("--work", required=True)
    parser.add_argument("--out", required=True)
    parser.add_argument("--display", default=":151")
    parser.add_argument("--port", type=int, default=2351 if WINDOWS else 0)
    parser.add_argument("--scale", choices=["100", "125"], default="100", help="Windows: the display scaling now set")
    parser.add_argument("--look", action="append", default=[], help="only looks starting so, e.g. before-light")
    parser.add_argument("cases", nargs="*", help=", ".join(CASES))
    args = parser.parse_args()
    unknown = [name for name in args.cases if name not in CASES]
    if unknown:
        parser.error("unknown case: " + ", ".join(unknown))
    if WINDOWS:
        looks = [(coat, theme, args.scale) for coat, theme, scale in LOOKS if scale == "100"]
        screen = hst_frame_shots.WindowsScreen()
    else:
        import hst_gui
        os.environ["HST_VCLPLUGIN"] = "gtk3"
        hst_gui.setup_uno(args.instdir)
        args.port = args.port or hst_gui.free_port()
        looks = list(LOOKS)
        screen = hst_frame_shots.LinuxScreen(args.display)
    looks = [look for look in looks if not args.look or any("-".join(look).startswith(sel) for sel in args.look)]
    if not looks:
        parser.error("no look matches " + ", ".join(args.look))
    os.makedirs(args.out, exist_ok=True)
    shots = Shots(args, screen)
    for look in looks:
        office = hst_frame_shots.office_for(args, look).start()
        try:
            shots.look(office, look, args.cases or list(CASES))
        finally:
            office.stop()
    with open(os.path.join(args.out, "failures.txt"), "w", encoding="utf-8") as out:
        out.write("".join(line + "\n" for line in shots.failures))
    return 1 if shots.failures else 0


if __name__ == "__main__":
    sys.exit(main())
