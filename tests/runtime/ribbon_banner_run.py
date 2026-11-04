# SPDX-License-Identifier: AGPL-3.0-only
"""check-ribbon-banner.py: one office instance showing one app at a given GDK scale."""
import os
import re
import shutil
import subprocess
import time

from check_ribbon_banner_extra import Opener
import hst_gui
import ribbon_banner_probe as probe

NAMES = {"writer": "HST Writer", "calc": "HST Sheets", "impress": "HST Slides"}
PORTS = iter(range(22940, 22990))


def xdo(display, *args):
    subprocess.run(["xdotool", *args], env=dict(os.environ, DISPLAY=display), check=False, timeout=15)


def geometry(display, wid):
    info = subprocess.run(["xwininfo", "-display", display, "-id", wid], capture_output=True, text=True).stdout
    keys = ("Absolute upper-left X:", "Absolute upper-left Y:", "Width:", "Height:")
    return [int(line.split(":")[1]) for key in keys for line in info.splitlines() if line.strip().startswith(key)]


class Run:
    """One office instance showing one app at a given GDK scale."""

    def __init__(self, args, instdir, app, display, scale, tag, env=(), config=()):
        self.args, self.app, self.display, self.scale, self.tag = args, app, display, scale, tag
        self.work = os.path.join(args.out, tag)
        self.opener = Opener(os.path.join(self.work, "fakebin"))
        extra = {"PATH": self.opener.directory + ":" + os.environ["PATH"], **dict(env)}
        if scale != 1:
            extra["GDK_SCALE"] = str(scale)
        subprocess.run(["xprop", "-display", display, "-root", "-remove", "AT_SPI_BUS"], check=False)
        self.office = hst_gui.Office(instdir, self.work, next(PORTS), display=display,
                                     extra_args=[f"--{app}"], nodefault=False, env=extra,
                                     config=[("/org.openoffice.Office.Impress/Misc/NewDoc", "AutoPilot", "false"), *config])

    def __enter__(self):
        self.office.start()
        time.sleep(8)
        self._close_welcome()
        self.wid = [w for w, n in hst_gui.toplevels(self.display, self.office.pid) if NAMES[self.app] in n][0]
        xdo(self.display, "windowmove", self.wid, "0", "0")
        self.size(1485, 900)
        return self

    def _close_welcome(self):
        """The welcome dialog is taller than the screen under GDK_SCALE: move it, then click its close button."""
        for _ in range(6):
            for wid, name in hst_gui.toplevels(self.display, self.office.pid):
                if re.search(r"Chào mừng|chào đón bạn|Welcome to", name):
                    xdo(self.display, "windowraise", wid)
                    xdo(self.display, "windowmove", wid, "0", "0")
                    time.sleep(0.5)
                    size = geometry(self.display, wid)
                    if len(size) < 4:  # hst_gui's watcher closed it meanwhile
                        continue
                    xdo(self.display, "mousemove", "--window", wid, str(size[2] - 70 * self.scale),
                        str(size[3] - 34 * self.scale), "click", "1")
            time.sleep(1.5)

    def __exit__(self, *exc):
        self.office.stop()

    def size(self, width, height):
        xdo(self.display, "windowsize", self.wid, str(width * self.scale), str(height * self.scale))
        time.sleep(4)
        self.frame = geometry(self.display, self.wid)

    def shot(self, name, copy_to=None):
        path = os.path.join(self.work, f"{name}.png")
        self.office.screenshot(path)
        if copy_to:
            os.makedirs(copy_to, exist_ok=True)
            shutil.copy(path, os.path.join(copy_to, f"{self.tag}-{name}.png"))
        return path

    def ribbon_height(self):
        top, tabs = probe.doc_tabs_top(self.display)
        return None if tabs is None else tabs - top

    def banner(self):
        """The banner node, or None when it is hidden."""
        nodes = probe.banner_nodes()
        return nodes[0] if nodes else None

    def factor(self):
        """Screenshot pixels per AT-SPI unit (gtk reports logical pixels under GDK_SCALE)."""
        return self.scale

    def hover(self, box):
        # bottom edge: the tooltip opens below the pointer, outside the artwork
        xdo(self.display, "mousemove", str(box[0] + box[2] // 3), str(box[1] + box[3] - 4 * self.scale))

    def click(self, box):
        self.hover(box)
        xdo(self.display, "click", "1")

    def leave(self):
        """Focus and pointer back to the document area (rotation resumes)."""
        x, y = self.frame[0] + self.frame[2] // 3, self.frame[1] + self.frame[3] * 2 // 3
        xdo(self.display, "mousemove", str(x), str(y), "click", "1")
        time.sleep(0.5)
