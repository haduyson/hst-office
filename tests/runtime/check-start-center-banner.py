# SPDX-License-Identifier: AGPL-3.0-only
"""Check the HASON TECH block of the Start Center: its heading, one real, separately clickable button per solution and
the "Xem thêm" link, in the left column of the Start Center window (HstStartCenterWindow). The Start Center shows no
HASON TECH banner (the owner took it out; the ribbon and the File panel keep theirs).

Usage: python3 tests/runtime/check-start-center-banner.py [--instdir upstream/libreoffice/instdir]
           [--out tests/output/start-center-banner] [--shots tests/output/screenshots-banner]
           [--display :95] [--no-gui]

Static part: the solution table of patches/libreoffice/hst-start-center-redesign.patch mirrors
data/hst/solutions.json (name, tagline, URL, same order); the installed hststartcenter.ui has the block's widgets
(heading, six buttons, the more link); the installed program carries the texts; the vi sfx catalogue
translates the heading and the "Tài liệu chưa lưu" menu item.
GUI part (unless --no-gui; needs a running X display, which the test never starts or stops; as root it re-executes
itself as the build user under dbus-run-session for AT-SPI): the Start Center under an English and a Vietnamese UI
(the profile's UILocale; the heading follows it, the solutions and the link are Vietnamese in both), with a fake
xdg-open that logs the opened URL. Through AT-SPI: the heading shows and no banner does; every solution button has
accessible name = name and description = tagline (also its tooltip); the block lies in the left column, inside the
window, below the heading, without overlaps. Every button is clicked and must open
url + "?utm_source=hst-office&utm_medium=start-center&utm_campaign=hst-office-1-0", "Xem thêm" opens hasontech.vn;
Tab moves the focus through the six buttons and the link. A window narrower than 860 px folds the block away; widened
again, it is back. Screenshots are kept. Exit 1 when a check fails.
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
HEADING = {"en": "HASON TECH digital transformation solutions", "vi": "Các giải pháp chuyển đổi số của HASON TECH"}
UNSAVED = ("Unsaved Documents", "Tài liệu chưa lưu")
PATCH = os.path.join(ROOT, "patches/libreoffice/hst-start-center-redesign.patch")
UI = "share/config/soffice.cfg/sfx/ui/hststartcenter.ui"
# the UI language is the profile's UILocale (Vietnamese when none is stored), not the locale of the process
UI_LOCALE = {"en": "en-US", "vi": "vi"}
NARROW = (820, 700)  # below the 860 px at which the left column folds to its menu glyphs
LEFT_SHARE = 0.4  # the left column is narrower than this share of a default-sized window


def solutions():
    with open(os.path.join(ROOT, "data/hst/solutions.json"), encoding="utf-8") as handle:
        return json.load(handle)["solutions"]


def decode(literal):
    """C++ u"..." body with \\uXXXX escapes -> text."""
    return re.sub(r"\\u([0-9A-Fa-f]{4})", lambda m: chr(int(m.group(1), 16)), literal)


def patch_table(text):
    """[(name, tagline, url)] of the solution table (aSolutions) in the patch text."""
    rows = re.findall(r'^\+\s*\{ u"([^"]*)"_ustr,\n\+\s*u"([^"]*)"_ustr,\n\+\s*u"([^"]*)"_ustr \},', text, re.M)
    return [tuple(decode(part) for part in row) for row in rows]


def static_checks(instdir, check):
    expected = [(s["name"], s["tagline"], s["url"]) for s in solutions()]
    with open(PATCH, encoding="utf-8") as handle:
        table = patch_table(handle.read())
    check("patch table mirrors data/hst/solutions.json (name, tagline, url, order)", table == expected,
          repr(table)[:200])
    ui_path = os.path.join(instdir, UI)
    ui = open(ui_path, encoding="utf-8").read() if os.path.isfile(ui_path) else ""
    check("hststartcenter.ui is installed", bool(ui), ui_path)
    for widget in ["solutions", "solutionstitle", "btnMoreSolutions", "nav_unsaved"] + [
            f"btnSolution{index}" for index in range(len(expected))]:
        check(f"hststartcenter.ui has {widget}", f'id="{widget}"' in ui)
    libs = [path for path in glob.glob(os.path.join(instdir, "program/lib*.so")) if os.path.getsize(path) > 1000]
    blobs = [open(path, "rb").read() for path in libs]
    for name, tagline, url in expected:
        for what, text in (("name", name), ("tagline", tagline), ("url", url)):
            check(f"program carries solution {what}: {text[:40]}",
                  any(text.encode("utf-16-le") in blob for blob in blobs))
    check("program carries the start-center UTM tail", any(UTM.encode("utf-16-le") in blob for blob in blobs))
    check("program carries the more-solutions link text",
          any(MORE_LABEL.encode("utf-16-le") in blob for blob in blobs))
    mo = subprocess.run(["msgunfmt", os.path.join(instdir, "program/resource/vi/LC_MESSAGES/sfx.mo")],
                        capture_output=True, text=True, check=False).stdout
    check("vi sfx.mo translates the block's heading", f'msgid "{HEADING["en"]}"\nmsgstr "{HEADING["vi"]}"' in mo)
    check("vi sfx.mo translates the Tài liệu chưa lưu menu item", 'msgid "%s"\nmsgstr "%s"' % UNSAVED in mo)


# ---- GUI helpers -------------------------------------------------------------------------------

def xdo(display, *args):
    subprocess.run(["xdotool", *args], env=dict(os.environ, DISPLAY=display), check=False, timeout=15)


def geometry(display, wid):
    info = subprocess.run(["xwininfo", "-display", display, "-id", wid], capture_output=True, text=True,
                          check=False).stdout
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


def shown_widgets():
    """[(role, name, description, box)] of the showing widgets (box = x, y, w, h in screen coordinates)."""
    import pyatspi
    app = office_app()
    out = []
    for node in walk(app, []) if app is not None else []:
        try:
            if not node.getState().contains(pyatspi.STATE_SHOWING):
                continue
            ext = node.queryComponent().getExtents(pyatspi.DESKTOP_COORDS)
            out.append((node.getRoleName(), node.name or "", node.description or "",
                        (ext.x, ext.y, ext.width, ext.height)))
        except Exception:  # noqa: BLE001
            continue
    return out


def block(widgets, tag):
    """The HASON TECH block as AT-SPI shows it: {"buttons": [(name, description, box) or None] in solution order and
    then the more link, "heading": box or None, "banner": box of a banner (there must be none) or None}."""
    names = [s["name"] for s in solutions()] + [MORE_LABEL]
    buttons = {name: (name, desc, box) for role, name, desc, box in widgets if role == "push button" and name in names}
    heading = next((box for role, name, _d, box in widgets if role == "label" and name == HEADING[tag]), None)
    # the rotating banner is named after the solution it shows: "<name> — <tagline>"
    shown = tuple(f"{s['name']} — " for s in solutions())
    banner = next((box for role, name, _d, box in widgets if role == "drawing area" and name.startswith(shown)), None)
    return {"buttons": [buttons.get(n) for n in names], "heading": heading, "banner": banner}


def center(box):
    return box[0] + box[2] // 2, box[1] + box[3] // 2


def overlaps(a, b):
    return a[0] < b[0] + b[2] and b[0] < a[0] + a[2] and a[1] < b[1] + b[3] and b[1] < a[1] + a[3]


def inside(box, window):
    x0, y0, width, height = window
    return (box[2] > 0 and box[3] > 0 and box[0] >= x0 and box[1] >= y0 and box[0] + box[2] <= x0 + width
            and box[1] + box[3] <= y0 + height)


def layout_checks(tag, found, window, check):
    """The heading, six buttons and the more link show (and no banner), named and described, in the left column, inside
    the window, below the heading, without overlaps. Returns True when everything was found."""
    sols = solutions()
    check(f"[{tag}] the Start Center shows no HASON TECH banner", found["banner"] is None, repr(found["banner"]))
    ok_found = all(found["buttons"]) and found["heading"] is not None
    check(f"[{tag}] heading, six solution buttons and the more link show", ok_found,
          f"heading={found['heading']} buttons={[b and b[0] for b in found['buttons']]}")
    if not ok_found:
        return False
    check(f"[{tag}] accessible name = solution name, accessible description = tagline",
          all(b[0] == s["name"] and b[1] == s["tagline"] for b, s in zip(found["buttons"], sols)),
          repr([(b[0], b[1]) for b in found["buttons"][:6]])[:300])
    boxes = [found["heading"]] + [b[2] for b in found["buttons"]]
    check(f"[{tag}] the block lies inside the window (not clipped)", all(inside(b, window) for b in boxes),
          repr(boxes)[:300])
    left_edge = window[0] + window[2] * LEFT_SHARE
    check(f"[{tag}] the block lies in the left column", all(b[0] + b[2] <= left_edge for b in boxes),
          repr(boxes)[:300])
    clash = [(i, j) for i in range(len(boxes)) for j in range(i + 1, len(boxes)) if overlaps(boxes[i], boxes[j])]
    check(f"[{tag}] no two widgets of the block overlap", not clash, repr(clash))
    top = found["heading"][1] + found["heading"][3]
    check(f"[{tag}] the buttons sit below the heading", all(b[1] >= top for b in boxes[1:]))
    return True


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
        with open(self.log, encoding="utf-8") as handle:
            return [line.strip() for line in handle if line.strip()]

    def wait_for(self, count, timeout=15):
        deadline = time.time() + timeout
        while time.time() < deadline and len(self.opened()) < count:
            time.sleep(0.3)
        return self.opened()


def click(display, point):
    xdo(display, "mousemove", str(point[0]), str(point[1]), "click", "1")


def gui_run(args, lang, tag, check):
    expected = [s["url"] + "?" + UTM for s in solutions()] + [MORE]
    targets = [s["name"] for s in solutions()] + ["Xem thêm"]
    workdir = os.path.join(args.out, f"gui-{tag}")
    opener = Opener(os.path.join(workdir, "fakebin"))
    subprocess.run(["xprop", "-display", args.display, "-root", "-remove", "AT_SPI_BUS"], check=False)
    office = hst_gui.Office(args.instdir, workdir, 21996 if tag == "en" else 21997, display=args.display, lang=lang,
                            nodefault=False, env={"PATH": opener.directory + ":" + os.environ["PATH"]},
                            config=[("/org.openoffice.Office.Linguistic/General", "UILocale", UI_LOCALE[tag])])
    office.start()
    try:
        time.sleep(8)
        wid = start_center_window(args.display, office.pid)
        window = geometry(args.display, wid)
        office.raise_windows()
        shot = lambda name: os.path.join(args.shots, f"{tag}-{name}.png")  # noqa: E731
        hst_gui.screenshot(shot("01-start-center"), args.display)
        widgets = shown_widgets()
        check(f"[{tag}] the Start Center is the new window (its Tài liệu chưa lưu menu item shows)",
              any(role == "push button" and name in UNSAVED for role, name, _d, _b in widgets))
        found = block(widgets, tag)
        if not layout_checks(tag, found, window, check):
            left = [(role, name) for role, name, _d, box in widgets
                    if name and box[0] < window[0] + window[2] * LEFT_SHARE and role not in ("push button",)]
            check(f"[{tag}] (detail) named widgets of the left column", False, left[:60])
            return
        centers = [center(b[2]) for b in found["buttons"]]
        for index, point in enumerate(centers):
            click(args.display, point)
            opened = opener.wait_for(index + 1)
            got = opened[index] if len(opened) > index else None
            check(f"[{tag}] click {targets[index]} opens its URL with UTM", got == expected[index], repr(got))
        # keyboard: a click focuses the first button; Tab then Space activates the next ones, then the more link
        before = len(opener.opened())
        click(args.display, centers[0])
        opener.wait_for(before + 1)
        for step in range(1, len(centers)):
            xdo(args.display, "key", "Tab")
            time.sleep(0.3)
            xdo(args.display, "key", "space")
            opened = opener.wait_for(before + 1 + step)
            got = opened[-1] if len(opened) == before + 1 + step else None
            check(f"[{tag}] Tab+Space reaches {targets[step]}", got == expected[step], repr(got))
        # tooltip: hover a button, its tagline appears
        xdo(args.display, "mousemove", str(centers[2][0]), str(centers[2][1] - 3))
        time.sleep(0.4)
        xdo(args.display, "mousemove", str(centers[2][0]), str(centers[2][1]))
        time.sleep(2.5)
        office.screenshot(shot("02-tooltip"))
        # narrow window: the left column folds to its menu glyphs, the block goes away
        xdo(args.display, "windowsize", wid, str(NARROW[0]), str(NARROW[1]))
        time.sleep(3)
        office.screenshot(shot("03-narrow"))
        narrow = geometry(args.display, wid)
        folded = block(shown_widgets(), tag)
        check(f"[{tag}] narrow window {narrow[2]}x{narrow[3]}: the block is folded away",
              narrow[2] < 860 and not any(folded["buttons"]) and folded["heading"] is None,
              [b and b[0] for b in folded["buttons"]])
        # wide again: the block is back
        xdo(args.display, "windowsize", wid, str(window[2]), str(window[3]))
        time.sleep(3)
        hst_gui.screenshot(shot("04-wide-again"), args.display)
        back = block(shown_widgets(), tag)
        check(f"[{tag}] widened again: the block is back", all(back["buttons"]) and back["heading"] is not None)
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
        os.execvp("runuser", ["runuser", "-u", hst_gui.BUILD_USER, "--", "dbus-run-session", "--", sys.executable]
                  + sys.argv)
    args.instdir, args.out = os.path.abspath(args.instdir), os.path.abspath(args.out)
    os.makedirs(args.out, exist_ok=True)
    os.makedirs(args.shots, exist_ok=True)
    results = []

    def check(name, ok, detail=""):
        results.append({"check": name, "status": "PASS" if ok else "FAIL", "detail": str(detail)})
        print(f"{'PASS' if ok else 'FAIL'}  {name}  {detail}", flush=True)

    static_checks(args.instdir, check)
    if not args.no_gui:
        os.environ.update(NO_AT_BRIDGE="0", GTK_MODULES="gail:atk-bridge")
        hst_gui.setup_uno(args.instdir)
        for lang, tag in (("en_US.UTF-8", "en"), ("vi_VN.UTF-8", "vi")):
            try:
                gui_run(args, lang, tag, check)
            except Exception as error:  # noqa: BLE001 - the other language still runs
                check(f"[{tag}] run", False, repr(error))
    failed = sum(r["status"] == "FAIL" for r in results)
    with open(os.path.join(args.out, "evidence.json"), "w", encoding="utf-8") as handle:
        json.dump({"failed": failed, "checks": results}, handle, indent=2, ensure_ascii=False)
    print(f"{len(results) - failed} pass, {failed} fail")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
