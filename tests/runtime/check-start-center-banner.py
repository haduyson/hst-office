# SPDX-License-Identifier: AGPL-3.0-only
"""Check the Start Center banner: one real, separately clickable button per HASON TECH solution.

Usage: python3 tests/runtime/check-start-center-banner.py [--instdir upstream/libreoffice/instdir]
           [--out tests/output/start-center-banner] [--shots tests/output/screenshots-banner]
           [--display :95] [--no-gui]

Static part: the C++ table in patches/libreoffice/hst-start-center-banner.patch mirrors
data/hst/solutions.json (name, tagline, URL, same order), the installed startcenter.ui has the six
buttons and no leftover donation widgets, and the installed program carries the texts.
GUI part (unless --no-gui, needs a running X display; the test never starts or stops it): Start
Center under an en-US and a vi UI with a fake xdg-open that logs the opened URL. Every button is
clicked and must open url + "?utm_source=hst-office&utm_medium=start-center&utm_campaign=hst-office-1-0";
Tab moves the focus through the six buttons; in a narrow window the artwork is hidden and the six
buttons and the text link are still clickable. Screenshots are kept. Exit 1 when a check fails.
"""
import argparse
import glob
import json
import os
import re
import stat
import subprocess
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import hst_gui  # noqa: E402

ROOT = hst_gui.ROOT
UTM = "utm_source=hst-office&utm_medium=start-center&utm_campaign=hst-office-1-0"
MORE = "https://hasontech.vn?" + UTM
PATCH = os.path.join(ROOT, "patches/libreoffice/hst-start-center-banner.patch")
NARROW = (800, 620)


def solutions():
    with open(os.path.join(ROOT, "data/hst/solutions.json"), encoding="utf-8") as handle:
        return json.load(handle)["solutions"]


def decode(literal):
    """C++ u"..." body with \\uXXXX escapes -> text."""
    return re.sub(r"\\u([0-9A-Fa-f]{4})", lambda m: chr(int(m.group(1), 16)), literal)


def patch_table():
    """[(name, tagline, url)] of the solution table added by the patch."""
    text = open(PATCH, encoding="utf-8").read()
    rows = re.findall(r'^\+\s*\{ u"([^"]*)"_ustr,\n\+\s*u"([^"]*)"_ustr,\n\+\s*u"([^"]*)"_ustr \},', text, re.M)
    return [tuple(decode(part) for part in row) for row in rows]


def static_checks(instdir, check):
    expected = [(s["name"], s["tagline"], s["url"]) for s in solutions()]
    check("patch table mirrors data/hst/solutions.json (name, tagline, url, order)",
          patch_table() == expected, repr(patch_table())[:200])
    ui_path = os.path.join(instdir, "share/config/soffice.cfg/sfx/ui/startcenter.ui")
    ui = open(ui_path, encoding="utf-8").read() if os.path.isfile(ui_path) else ""
    for index in range(len(expected)):
        check(f"startcenter.ui has btnSolution{index}", f'id="btnSolution{index}"' in ui)
    check("startcenter.ui has no donation widgets left",
          not any(name in ui for name in ("btnDonateLink", "lbDonateTitle", "lbDonateText", "imgDonationRight")))
    libs = [path for path in glob.glob(os.path.join(instdir, "program/lib*.so")) if os.path.getsize(path) > 1000]
    blobs = [open(path, "rb").read() for path in libs]
    for name, tagline, url in expected:
        for what, text in (("name", name), ("tagline", tagline), ("url", url)):
            found = any(text.encode("utf-16-le") in blob for blob in blobs)
            check(f"program carries solution {what}: {text[:40]}", found)
    check("program carries the start-center UTM tail",
          any(UTM.encode("utf-16-le") in blob for blob in blobs))
    check("program carries the more-solutions link text and the old link text is gone",
          any("Xem thêm các giải pháp khác →".encode("utf-16-le") in blob for blob in blobs)
          and not any("Xem các giải pháp tại hasontech.vn".encode("utf-16-le") in blob for blob in blobs))
    check("startcenter.ui has btnMoreSolutions", 'id="btnMoreSolutions"' in ui)
    banner = os.path.join(ROOT, "branding/libreoffice/hst-banner.png")
    installed = os.path.join(instdir, "program/shell/donate1.png")
    check("installed donate1.png is the HST banner",
          os.path.isfile(installed) and open(installed, "rb").read() == open(banner, "rb").read())


# ---- GUI helpers -------------------------------------------------------------------------------

def xdo(display, *args):
    subprocess.run(["xdotool", *args], env=dict(os.environ, DISPLAY=display), check=False, timeout=15)


def geometry(display, wid):
    info = subprocess.run(["xwininfo", "-display", display, "-id", wid], capture_output=True, text=True).stdout
    return tuple(int(re.search(pattern, info).group(1)) for pattern in
                 (r"Absolute upper-left X:\s+(-?\d+)", r"Absolute upper-left Y:\s+(-?\d+)",
                  r"Width: (\d+)", r"Height: (\d+)"))


def start_center_window(display, pid):
    windows = hst_gui.toplevels(display, pid)
    return max(windows, key=lambda w: geometry(display, w[0])[2] * geometry(display, w[0])[3])[0]


def differs_at(shot, background, x, y):
    return sum(abs(a - b) for a, b in zip(shot.getpixel((x, y)), background)) > 24


def banner_buttons(image_path, display, wid):
    """Screen centers of the six solution buttons plus the "more" link (7 points) and the number
    of artwork runs, from a screenshot.

    The banner strip is the bottom of the Start Center window, above the recent-documents pane.
    Non-background column runs are separated by gaps; the last run is the button grid (3x2
    buttons, the text link below), any run before it is the artwork."""
    from PIL import Image
    x0, y0, width, height = geometry(display, wid)
    hst_gui.screenshot(image_path, display)
    shot = Image.open(image_path).convert("RGB")
    background = shot.getpixel((x0 + width - 3, y0 + height - 3))
    bottom, left = y0 + height - 2, x0 + 265
    top = bottom
    while top > y0 + 100 and not differs_at(shot, background, x0 + width - 40, top):
        top -= 1
    top += 3

    def differs(x, y):
        return differs_at(shot, background, x, y)

    columns = [x for x in range(left, x0 + width - 4) if any(differs(x, y) for y in range(top, bottom))]
    runs, start = [], None
    for previous, x in zip([None] + columns, columns):
        if previous is None or x - previous > 8:
            if start is not None:
                runs.append((start, previous))
            start = x
    if start is not None:
        runs.append((start, columns[-1]))
    if not runs:
        return [], 0
    gx0, gx1 = runs[-1]
    rows = [y for y in range(top, bottom) if any(differs(x, y) for x in range(gx0, gx1 + 1))]
    bands, begin = [], rows[0]
    for previous, y in zip(rows, rows[1:]):
        if y - previous > 3:
            bands.append((begin, previous))
            begin = y
    bands.append((begin, rows[-1]))
    if len(bands) != 3:
        return [], len(runs) - 1
    # button columns from the two button bands only (the link text is narrower than the grid)
    cell_w = (gx1 - gx0 + 1) / 3
    centers = [(round(gx0 + cell_w * (i % 3 + 0.5)), (bands[i // 3][0] + bands[i // 3][1]) // 2) for i in range(6)]
    link = bands[2]
    link_x = [x for x in range(gx0, gx1 + 1) if any(differs(x, y) for y in range(link[0], link[1] + 1))]
    centers.append(((link_x[0] + link_x[-1]) // 2, (link[0] + link[1]) // 2))
    return centers, len(runs) - 1


class Opener:
    """Fake xdg-open on PATH that appends every opened URL to a log file."""

    def __init__(self, directory):
        os.makedirs(directory, exist_ok=True)
        self.log = os.path.join(directory, "opened-urls.log")
        open(self.log, "w").close()
        script = os.path.join(directory, "xdg-open")
        with open(script, "w", encoding="utf-8") as handle:
            handle.write(f'#!/bin/sh\necho "$*" >> "{self.log}"\n')
        os.chmod(script, os.stat(script).st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
        self.directory = directory

    def opened(self):
        return [line.strip() for line in open(self.log, encoding="utf-8") if line.strip()]

    def wait_for(self, count, timeout=15):
        deadline = time.time() + timeout
        while time.time() < deadline and len(self.opened()) < count:
            time.sleep(0.3)
        return self.opened()


def click(display, center):
    xdo(display, "mousemove", str(center[0]), str(center[1]), "click", "1")


def gui_run(args, lang, tag, check):
    expected = [s["url"] + "?" + UTM for s in solutions()]
    workdir = os.path.join(args.out, f"gui-{tag}")
    opener = Opener(os.path.join(workdir, "fakebin"))
    office = hst_gui.Office(args.instdir, workdir, 21996 if tag == "en" else 21997, display=args.display, lang=lang,
                            nodefault=False, env={"PATH": opener.directory + ":" + os.environ["PATH"]})
    office.start()
    try:
        time.sleep(8)
        wid = start_center_window(args.display, office.pid)
        x0, y0, width, height = geometry(args.display, wid)
        office.raise_windows()
        shot = lambda name: os.path.join(args.shots, f"{tag}-{name}.png")  # noqa: E731
        centers, art = banner_buttons(shot("01-start-center"), args.display, wid)
        check(f"[{tag}] wide window ({width}x{height}): six buttons and the more link found, artwork shown", len(centers) == 7 and art == 1,
              f"art={art}")
        if len(centers) != 7:
            return
        for index, center in enumerate(centers[:6]):
            click(args.display, center)
            opened = opener.wait_for(index + 1)
            got = opened[index] if len(opened) > index else None
            check(f"[{tag}] click {solutions()[index]['name']} opens its URL with UTM", got == expected[index], repr(got))
        click(args.display, centers[6])
        opened = opener.wait_for(7)
        got = opened[6] if len(opened) > 6 else None
        check(f"[{tag}] click \"Xem thêm các giải pháp khác\" opens hasontech.vn with UTM", got == MORE, repr(got))
        # keyboard: a click focuses the button; Tab then Space activates the next ones
        before = len(opener.opened())
        click(args.display, centers[0])
        opener.wait_for(before + 1)
        for step in (1, 2, 3, 4, 5):
            xdo(args.display, "key", "Tab")
            time.sleep(0.3)
            xdo(args.display, "key", "space")
            opened = opener.wait_for(before + 1 + step)
            got = opened[-1] if len(opened) == before + 1 + step else None
            check(f"[{tag}] Tab+Space reaches {solutions()[step]['name']}", got == expected[step], repr(got))
        xdo(args.display, "key", "Tab")
        time.sleep(0.3)
        xdo(args.display, "key", "space")
        opened = opener.wait_for(before + 7)
        check(f"[{tag}] Tab+Space reaches the more link", opened[-1:] == [MORE], repr(opened[-1:]))
        # tooltip: hover a button, the tagline appears in a tooltip window or the screenshot
        xdo(args.display, "mousemove", str(centers[2][0]), str(centers[2][1] - 3))
        time.sleep(0.4)
        xdo(args.display, "mousemove", str(centers[2][0]), str(centers[2][1]))
        time.sleep(2.5)
        office.screenshot(shot("02-tooltip"))
        # narrow window: artwork hidden, buttons remain
        xdo(args.display, "windowsize", wid, str(NARROW[0]), str(NARROW[1]))
        time.sleep(3)
        office.screenshot(shot("03-narrow-raw"))
        centers, art = banner_buttons(shot("03-narrow"), args.display, wid)
        check(f"[{tag}] narrow window {NARROW[0]}x{NARROW[1]}: artwork hidden, six buttons and the more link found",
              len(centers) == 7 and art == 0, f"points={len(centers)} art={art}")
        if len(centers) == 7:
            before = len(opener.opened())
            click(args.display, centers[5])
            click(args.display, centers[6])
            opened = opener.wait_for(before + 2)
            check(f"[{tag}] narrow: last button and the more link open their URLs",
                  opened[-2:] == [expected[5], MORE], repr(opened[-2:]))
        # wide again: artwork returns
        xdo(args.display, "windowsize", wid, str(width), str(height))
        time.sleep(3)
        centers, art = banner_buttons(shot("04-wide-again"), args.display, wid)
        check(f"[{tag}] widened again: artwork shown", len(centers) == 7 and art == 1, f"art={art}")
    finally:
        office.stop()


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--instdir", default=os.path.join(ROOT, "upstream/libreoffice/instdir"))
    parser.add_argument("--out", default=os.path.join(ROOT, "tests/output/start-center-banner"))
    parser.add_argument("--shots", default=os.path.join(ROOT, "tests/output/screenshots-banner"))
    parser.add_argument("--display", default=":95")
    parser.add_argument("--no-gui", action="store_true")
    args = parser.parse_args()
    args.instdir, args.out = os.path.abspath(args.instdir), os.path.abspath(args.out)
    os.makedirs(args.out, exist_ok=True)
    os.makedirs(args.shots, exist_ok=True)
    results = []

    def check(name, ok, detail=""):
        results.append({"check": name, "status": "PASS" if ok else "FAIL", "detail": detail})
        print(f"{'PASS' if ok else 'FAIL'}  {name}  {detail}")

    static_checks(args.instdir, check)
    if not args.no_gui:
        hst_gui.setup_uno(args.instdir)
        gui_run(args, "en_US.UTF-8", "en", check)
        gui_run(args, "vi_VN.UTF-8", "vi", check)
    failed = sum(r["status"] == "FAIL" for r in results)
    with open(os.path.join(args.out, "evidence.json"), "w", encoding="utf-8") as handle:
        json.dump({"failed": failed, "checks": results}, handle, indent=2, ensure_ascii=False)
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
