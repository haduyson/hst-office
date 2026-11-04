# SPDX-License-Identifier: AGPL-3.0-only
"""Check the Start Center banner: one real, separately clickable button per HASON TECH solution.

Usage: python3 tests/runtime/check-start-center-banner.py [--instdir upstream/libreoffice/instdir]
           [--out tests/output/start-center-banner] [--shots tests/output/screenshots-banner]
           [--display :95] [--no-gui]

Static part: the C++ table in patches/libreoffice/hst-start-center-banner.patch mirrors
data/hst/solutions.json (name, tagline, URL, same order), the installed startcenter.ui has the six
buttons and no leftover donation widgets, and the installed program carries the texts.
GUI part (unless --no-gui, needs a running X display; the test never starts or stops it; as root it
re-executes itself as the build user under dbus-run-session for AT-SPI): Start Center under an en-US
and a vi UI with a fake xdg-open that logs the opened URL. Widgets are located through AT-SPI: every
solution button has accessible name = name and description = tagline, its tagline is shown centred
below it, no banner widget overlaps another or leaves the window. Every button is clicked and must
open url + "?utm_source=hst-office&utm_medium=start-center&utm_campaign=hst-office-1-0"; Tab moves
the focus through the six buttons; in a narrow window the artwork is hidden and the buttons, taglines
and the text link remain. Screenshots are kept. Exit 1 when a check fails.
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
MORE_LABEL = "Xem thêm các giải pháp khác →"
PATCH = os.path.join(ROOT, "patches/libreoffice/hst-start-center-banner.patch")
NARROW = (1000, 700)


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
    for index, (name, tagline, _url) in enumerate(expected):
        check(f"startcenter.ui has btnSolution{index} and its tagline label lbSolution{index}",
              f'id="btnSolution{index}"' in ui and f'id="lbSolution{index}"' in ui)
        check(f"startcenter.ui tagline {index} equals data/hst/solutions.json", f">{tagline}<" in ui)
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
    # "Create" list: product name + document type, em dash with spaces (type follows the UI language)
    en = ("HST _Writer — Document", "HST _Sheets — Spreadsheet", "HST S_lides — Presentation")
    vi = ("HST _Writer — Văn bản", "HST _Sheets — Bảng tính", "HST S_lides — Trình chiếu")
    check("startcenter.ui: en-US create labels are 'HST <app> — <type>'", all(f">{text}<" in ui for text in en))
    mo = subprocess.run(["msgunfmt", os.path.join(instdir, "program/resource/vi/LC_MESSAGES/sfx.mo")],
                        capture_output=True, text=True).stdout
    check("vi sfx.mo: create labels are 'HST <app> — Văn bản / Bảng tính / Trình chiếu'",
          all(f'msgid "{e}"\nmsgstr "{v}"' in mo for e, v in zip(en, vi)))
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


def office_app():
    import pyatspi
    desktop = pyatspi.Registry.getDesktop(0)
    for index in range(desktop.childCount):
        app = desktop.getChildAtIndex(index)
        if "office" in (app.name or "").lower():
            return app
    return None


def walk(node, out):
    try:
        out.append(node)
        for index in range(node.childCount):
            walk(node.getChildAtIndex(index), out)
    except Exception:  # noqa: BLE001 - a widget may vanish while walking
        pass
    return out


def banner(display):
    """{"buttons": [(name, description, box)] in solution order + the more link, "labels": [(text, box)]} of the
    banner as AT-SPI shows it (box = x, y, w, h in screen coordinates; showing widgets only)."""
    import pyatspi
    names = [s["name"] for s in solutions()] + [MORE_LABEL]
    taglines = [s["tagline"] for s in solutions()]
    found = {"buttons": {}, "labels": {}}
    app = office_app()
    for node in walk(app, []) if app is not None else []:
        try:
            if not node.getState().contains(pyatspi.STATE_SHOWING):
                continue
            role, name = node.getRoleName(), node.name
            ext = node.queryComponent().getExtents(pyatspi.DESKTOP_COORDS)
            box = (ext.x, ext.y, ext.width, ext.height)
        except Exception:  # noqa: BLE001
            continue
        if role == "push button" and name in names:
            found["buttons"][name] = (name, node.description, box)
        elif role == "label" and name in taglines:
            found["labels"][name] = (name, box)
    return {"buttons": [found["buttons"].get(n) for n in names], "labels": [found["labels"].get(t) for t in taglines]}


def center(box):
    return box[0] + box[2] // 2, box[1] + box[3] // 2


def overlaps(a, b):
    return a[0] < b[0] + b[2] and b[0] < a[0] + a[2] and a[1] < b[1] + b[3] and b[1] < a[1] + a[3]


def layout_checks(tag, what, found, window, check):
    """Every solution shows its name (button: accessible name = name, description = tagline) and its tagline
    below it; nothing overlaps and nothing lies outside the window. Returns True when everything was found."""
    sols = solutions()
    ok_found = all(found["buttons"]) and all(found["labels"])
    check(f"[{tag}] {what}: six buttons, the more link and six visible taglines found", ok_found,
          f"buttons={[b and b[0] for b in found['buttons']]} labels={sum(1 for l in found['labels'] if l)}")
    if not ok_found:
        return False
    check(f"[{tag}] {what}: accessible name = solution name, accessible description = tagline",
          all(b[0] == s["name"] and b[1] == s["tagline"] for b, s in zip(found["buttons"], sols)),
          repr([(b[0], b[1]) for b in found["buttons"][:6]])[:300])
    boxes = [b[2] for b in found["buttons"]] + [l[1] for l in found["labels"]]
    x0, y0, width, height = window
    inside = all(b[2] > 0 and b[3] > 0 and b[0] >= x0 and b[1] >= y0 and b[0] + b[2] <= x0 + width
                 and b[1] + b[3] <= y0 + height for b in boxes)
    check(f"[{tag}] {what}: banner widgets lie inside the window (not clipped)", inside, repr(boxes)[:300])
    clash = [(i, j) for i in range(len(boxes)) for j in range(i + 1, len(boxes)) if overlaps(boxes[i], boxes[j])]
    check(f"[{tag}] {what}: no two banner widgets overlap", not clash, repr(clash))
    below = all(l[1][1] >= b[2][1] + b[2][3] and abs(center(l[1])[0] - center(b[2])[0]) <= 2
                for b, l in zip(found["buttons"], found["labels"]))
    check(f"[{tag}] {what}: each tagline sits centred below its button", below)
    return True


def art_shown(found, window):
    """The artwork sits left of the button grid: the grid starts far right of the left pane when it is shown."""
    left = min(b[2][0] for b in found["buttons"][:6])
    return left - window[0] > 600


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


def click(display, point):
    xdo(display, "mousemove", str(point[0]), str(point[1]), "click", "1")


def gui_run(args, lang, tag, check):
    expected = [s["url"] + "?" + UTM for s in solutions()]
    workdir = os.path.join(args.out, f"gui-{tag}")
    opener = Opener(os.path.join(workdir, "fakebin"))
    subprocess.run(["xprop", "-display", args.display, "-root", "-remove", "AT_SPI_BUS"], check=False)
    office = hst_gui.Office(args.instdir, workdir, 21996 if tag == "en" else 21997, display=args.display, lang=lang,
                            nodefault=False, env={"PATH": opener.directory + ":" + os.environ["PATH"]})
    office.start()
    try:
        time.sleep(8)
        wid = start_center_window(args.display, office.pid)
        window = geometry(args.display, wid)
        office.raise_windows()
        shot = lambda name: os.path.join(args.shots, f"{tag}-{name}.png")  # noqa: E731
        hst_gui.screenshot(shot("01-start-center"), args.display)
        found = banner(args.display)
        if not layout_checks(tag, f"default window {window[2]}x{window[3]}", found, window, check):
            return
        check(f"[{tag}] default window {window[2]}x{window[3]}: artwork shown", art_shown(found, window))
        centers = [center(b[2]) for b in found["buttons"]]
        for index, point in enumerate(centers[:6]):
            click(args.display, point)
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
        # tooltip: hover a button, the tagline appears in a tooltip
        xdo(args.display, "mousemove", str(centers[2][0]), str(centers[2][1] - 3))
        time.sleep(0.4)
        xdo(args.display, "mousemove", str(centers[2][0]), str(centers[2][1]))
        time.sleep(2.5)
        office.screenshot(shot("02-tooltip"))
        # narrow window: artwork hidden, buttons and taglines remain
        xdo(args.display, "windowsize", wid, str(NARROW[0]), str(NARROW[1]))
        time.sleep(3)
        office.screenshot(shot("03-narrow"))
        narrow = geometry(args.display, wid)
        found = banner(args.display)
        if layout_checks(tag, f"narrow window {narrow[2]}x{narrow[3]}", found, narrow, check):
            check(f"[{tag}] narrow window: artwork hidden", not art_shown(found, narrow))
            before = len(opener.opened())
            click(args.display, center(found["buttons"][5][2]))
            click(args.display, center(found["buttons"][6][2]))
            opened = opener.wait_for(before + 2)
            check(f"[{tag}] narrow: last button and the more link open their URLs",
                  opened[-2:] == [expected[5], MORE], repr(opened[-2:]))
        # wide again: artwork returns
        xdo(args.display, "windowsize", wid, str(window[2]), str(window[3]))
        time.sleep(3)
        hst_gui.screenshot(shot("04-wide-again"), args.display)
        found = banner(args.display)
        check(f"[{tag}] widened again: artwork shown", all(found["buttons"]) and art_shown(found, window))
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
    if os.geteuid() == 0 and not args.no_gui:
        # AT-SPI needs a session bus shared with the office: run as the build user under dbus-run-session
        for directory in (args.out, args.shots):
            os.makedirs(directory, exist_ok=True)
            subprocess.run(["chown", "-R", hst_gui.BUILD_USER, directory], check=False)
        os.execvp("runuser", ["runuser", "-u", hst_gui.BUILD_USER, "--", "dbus-run-session", "--", sys.executable] + sys.argv)
    args.instdir, args.out = os.path.abspath(args.instdir), os.path.abspath(args.out)
    os.makedirs(args.out, exist_ok=True)
    os.makedirs(args.shots, exist_ok=True)
    results = []

    def check(name, ok, detail=""):
        results.append({"check": name, "status": "PASS" if ok else "FAIL", "detail": detail})
        print(f"{'PASS' if ok else 'FAIL'}  {name}  {detail}")

    static_checks(args.instdir, check)
    if not args.no_gui:
        os.environ.update(NO_AT_BRIDGE="0", GTK_MODULES="gail:atk-bridge")
        hst_gui.setup_uno(args.instdir)
        gui_run(args, "en_US.UTF-8", "en", check)
        gui_run(args, "vi_VN.UTF-8", "vi", check)
    failed = sum(r["status"] == "FAIL" for r in results)
    with open(os.path.join(args.out, "evidence.json"), "w", encoding="utf-8") as handle:
        json.dump({"failed": failed, "checks": results}, handle, indent=2, ensure_ascii=False)
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
