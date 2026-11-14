# SPDX-License-Identifier: AGPL-3.0-only
"""X11 helpers of check-privacy-links.py: a recording stand-in for the system browser, window lookup, keys and mouse
clicks (xdotool), and finding a text link on screen by its colour (ImageMagick's import + Pillow)."""
import json
import os
import re
import stat
import subprocess
import tempfile
import threading
import time

import hst_gui

ABOUT_TITLE = "^(Giới thiệu|About) HST Office$"
OPTIONS_TITLE = "^(Tùy chọn|Options)"
# No update check dialog may pop up in the middle of the clicks.
QUIET_CONFIG = [("/org.openoffice.Office.HSTUpdate", "AutoCheck", "false"),
                ("/org.hasontech.hstoffice.UpdateCheck", "AutoCheck", "false")]
# Link text colours: the HST dialogs' light-theme link colour and the GTK (Adwaita) link colour of the About dialog.
LINK_COLOURS = ((0x0B, 0x57, 0xD0), (0x1B, 0x6A, 0xCB))
TOLERANCE = 28
SHIM = """#!/bin/sh
# Test stand-in for the system browser: record the URL instead of opening it.
for url in "$@"; do printf '%%s\\n' "$url" >> '%s'; done
"""


class Browser:
    def __init__(self, folder, home):
        self.log = os.path.join(folder, "urls.txt")
        self.shim = os.path.join(folder, "xdg-open")
        # runuser gives soffice the build user's own HOME: point GIO at the test handler explicitly
        self.env = {"PATH": folder + ":/usr/local/bin:/usr/bin:/bin", "BROWSER": self.shim,
                    "XDG_CONFIG_HOME": os.path.join(home, ".config"),
                    "XDG_DATA_HOME": os.path.join(home, ".local", "share")}

    def urls(self):
        try:
            with open(self.log, encoding="utf-8") as handle:
                return [line.strip() for line in handle if line.strip()]
        except FileNotFoundError:
            return []


def install_browser(workdir):
    """xdg-open on PATH and the https/http handler of GIO (XDG directories under workdir/home) both record."""
    folder, home = os.path.join(workdir, "browser"), os.path.join(workdir, "home")
    os.makedirs(folder, exist_ok=True)
    browser = Browser(folder, home)
    if os.path.exists(browser.log):
        os.remove(browser.log)
    with open(browser.shim, "w", encoding="utf-8") as handle:
        handle.write(SHIM % browser.log)
    os.chmod(browser.shim, stat.S_IRWXU | stat.S_IRGRP | stat.S_IXGRP | stat.S_IROTH | stat.S_IXOTH)
    for sub in (".local/share/applications", ".config"):
        os.makedirs(os.path.join(home, sub), exist_ok=True)
    with open(os.path.join(home, ".local/share/applications/hst-test-browser.desktop"), "w", encoding="utf-8") as f:
        f.write("[Desktop Entry]\nType=Application\nName=HST test browser\nExec=%s %%u\n"
                "MimeType=x-scheme-handler/http;x-scheme-handler/https;\n" % browser.shim)
    with open(os.path.join(home, ".config/mimeapps.list"), "w", encoding="utf-8") as f:
        f.write("[Default Applications]\nx-scheme-handler/http=hst-test-browser.desktop\n"
                "x-scheme-handler/https=hst-test-browser.desktop\n")
    return browser


def wait(predicate, timeout=30.0):
    deadline = time.time() + timeout
    while time.time() < deadline:
        value = predicate()
        if value:
            return value
        time.sleep(0.5)
    return None


def wait_window(office, pattern, timeout=25):
    """Newest mapped top-level window of this office whose title matches `pattern`."""
    def find():
        found = [w for w in hst_gui.toplevels(office.display, office.pid) if re.search(pattern, w[1])]
        return found[-1][0] if found else None
    return wait(find, timeout)


def dispatch_async(office, frame, command, args=()):
    """Modal dialogs: the dispatch returns only when the dialog closes, so it runs on its own thread."""
    def run():
        from com.sun.star.beans import PropertyValue
        props = []
        for name, value in args:
            prop = PropertyValue()
            prop.Name, prop.Value = name, value
            props.append(prop)
        office.dispatch(frame, command, props)
    thread = threading.Thread(target=run, daemon=True)
    thread.start()
    return thread


def xdo(office, *args):
    return subprocess.run(["xdotool", *args], env=dict(os.environ, DISPLAY=office.display), capture_output=True,
                          text=True, check=False, timeout=60)


def key(office, wid, *keys):
    xdo(office, "windowfocus", "--sync", wid)
    xdo(office, "key", "--delay", "120", *keys)


def mouse_click(office, wid, x, y):
    xdo(office, "windowraise", wid)
    xdo(office, "mousemove", "--window", wid, str(x), str(y), "click", "1")
    time.sleep(0.8)


def shot(office, wid, path):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    xdo(office, "windowraise", wid)
    time.sleep(0.4)
    subprocess.run(["import", "-display", office.display, "-window", wid, path], check=False, timeout=60)


def _near(pixel):
    return any(all(abs(a - b) <= TOLERANCE for a, b in zip(pixel[:3], colour)) for colour in LINK_COLOURS)


def link_boxes(image, left=0.0, top=0.0, bottom=1.0):
    """Bounding boxes of runs of link-coloured text, one per line of text and gap-separated word group."""
    width, height = image.size
    data = image.convert("RGB").load()
    rows = {}
    for y in range(int(height * top), int(height * bottom)):
        xs = [x for x in range(int(width * left), width) if _near(data[x, y])]
        if xs:
            rows[y] = xs
    boxes, band = [], []
    for y in sorted(rows) + [None]:
        if band and (y is None or y - band[-1] > 2):
            xs = sorted(x for row in band for x in rows[row])
            start = prev = xs[0]
            for x in xs[1:] + [None]:
                if x is None or x - prev > 14:
                    boxes.append((start, band[0], prev, band[-1]))
                    start = x
                prev = x if x is not None else prev
            band = []
        if y is not None:
            band.append(y)
    return [b for b in boxes if b[2] - b[0] >= 20 and b[3] - b[1] <= 24]  # text, not icons or lines


def rightmost_link(office, wid, left_fraction=0.0, top_fraction=0.0, bottom_fraction=1.0):
    """Window-relative centre of the right-most link of the lowest row of links, or None."""
    from PIL import Image
    with tempfile.TemporaryDirectory() as folder:
        path = os.path.join(folder, "window.png")
        subprocess.run(["import", "-display", office.display, "-window", wid, path], check=False, timeout=60)
        if not os.path.exists(path):
            return None
        boxes = link_boxes(Image.open(path), left_fraction, top_fraction, bottom_fraction)
    if not boxes:
        return None
    lowest = max(b[1] for b in boxes)
    x0, y0, x1, y1 = max((b for b in boxes if b[1] >= lowest - 6), key=lambda b: b[2])
    return wid, (x0 + x1) // 2, (y0 + y1) // 2


def update_page_url(ctx):
    """The page URL as the Options dialog compares it: the extension's %origin% URL with its macros expanded."""
    expander = ctx.getValueByName("/singletons/com.sun.star.util.theMacroExpander")
    return expander.expandMacros("$BUNDLED_EXTENSIONS") + "/hst-vietnamese-tools/dialogs/Update.xdl"


def citation_titles(lang, instdir):
    code = "vi" if lang.startswith("vi") else "en"
    path = os.path.join(instdir, "share", "extensions", "hst-vietnamese-tools", "locales", "citations-%s.json" % code)
    with open(path, encoding="utf-8") as handle:
        texts = json.load(handle)
    return texts["library"]["title"], texts["entry"]["titleNew"]
