# SPDX-License-Identifier: AGPL-3.0-only
"""X11 side of the GUI runtime checks (hst_gui.py): top-level windows, screenshots, closing dialogs.

WindowMixin holds the Office methods that act on this instance's windows."""
import os
import re
import subprocess
import time


class WindowMixin:
    """Methods of hst_gui.Office that act on its X windows (needs display, pid, workdir, _stop_watch)."""

    def _dismiss_welcome(self):
        """The modal HST welcome dialog (first visible window of a fresh profile) blocks UNO
        calls until closed; click its close button whenever it appears."""
        pattern = re.compile(r"Chào mừng|chào đón bạn|Welcome to")
        while not self._stop_watch.wait(1.0):
            if self.pid is None:
                continue
            try:
                for wid, name in toplevels(self.display, self.pid):
                    if pattern.search(name):
                        self.click_close(wid)
            except Exception as error:  # noqa: BLE001 - keep watching
                with open(os.path.join(self.workdir, "watch.log"), "a", encoding="utf-8") as log:
                    log.write(f"{time.time():.0f} {error!r}\n")

    def click_close(self, wid):
        """Raise our dialog (another instance may share the display) and click its close
        button, bottom right ("Đóng"/"Close"); pointer clicks need no keyboard focus."""
        env = dict(os.environ, DISPLAY=self.display)
        info = subprocess.run(["xwininfo", "-display", self.display, "-id", wid], capture_output=True, text=True).stdout
        width = int(re.search(r"Width: (\d+)", info).group(1))
        height = int(re.search(r"Height: (\d+)", info).group(1))
        subprocess.run(["xdotool", "windowraise", wid], env=env, check=False, timeout=10)
        time.sleep(0.3)
        subprocess.run(["xdotool", "mousemove", "--window", wid, str(width - 70), str(height - 34), "click", "1"],
                       env=env, check=False, timeout=10)

    def close_welcome(self):
        for wid, name in toplevels(self.display, self.pid):
            if re.search(r"Chào mừng|chào đón bạn|Welcome to", name):
                self.click_close(wid)
                return True
        return False

    def raise_windows(self):
        """Raise this instance's mapped windows (another instance may share the display)."""
        env = dict(os.environ, DISPLAY=self.display)
        # document/Start Center windows first, dialogs last (on top)
        windows = sorted(toplevels(self.display, self.pid), key=lambda w: w[1] == "HST Office" or " — HST " in w[1])
        for wid, _name in reversed(windows):
            subprocess.run(["xdotool", "windowraise", wid], env=env, check=False, timeout=10)
        time.sleep(0.5)

    def screenshot(self, path):
        self.raise_windows()
        return screenshot(path, self.display)


def screenshot(path, display=":97"):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    subprocess.run(["import", "-display", display, "-window", "root", path], check=True)
    return path


def window_pid(wid, display=":97"):
    out = subprocess.run(["xprop", "-display", display, "-id", wid, "_NET_WM_PID"], capture_output=True, text=True).stdout
    match = re.search(r"= (\d+)", out)
    return int(match.group(1)) if match else None


def toplevels(display=":97", pid=None, mapped=True):
    """[(window id, name)] of top-level windows, optionally only mapped ones of process pid.

    Several soffice instances may share the test display: tests pass their own pid."""
    out = subprocess.run(["xwininfo", "-display", display, "-root", "-children"], capture_output=True, text=True).stdout
    result = []
    for line in out.splitlines():
        match = re.match(r'\s*(0x[0-9a-f]+) "([^"]*)"', line)
        if not match:
            continue
        wid, name = match.groups()
        if mapped:
            info = subprocess.run(["xwininfo", "-display", display, "-id", wid], capture_output=True, text=True).stdout
            if "Map State: IsViewable" not in info:
                continue
        if pid is not None and window_pid(wid, display) != pid:
            continue
        result.append((wid, name))
    return result


def mapped_toplevels(display=":97", name_filter=None, pid=None):
    """Names of the mapped (viewable) top-level windows, i.e. what a taskbar would list."""
    return [name for _wid, name in toplevels(display, pid) if name_filter is None or name_filter(name)]


def send_close_request(wid, display=":97"):
    """Ask a top-level window to close as its title-bar X would (WM_DELETE_WINDOW client
    message); the test display has no window manager to do it."""
    import ctypes
    import ctypes.util
    xlib = ctypes.cdll.LoadLibrary(ctypes.util.find_library("X11"))
    xlib.XOpenDisplay.restype = ctypes.c_void_p
    xlib.XOpenDisplay.argtypes = [ctypes.c_char_p]
    xlib.XInternAtom.restype = ctypes.c_ulong
    xlib.XInternAtom.argtypes = [ctypes.c_void_p, ctypes.c_char_p, ctypes.c_int]
    xlib.XSendEvent.argtypes = [ctypes.c_void_p, ctypes.c_ulong, ctypes.c_int, ctypes.c_long, ctypes.c_void_p]
    xlib.XFlush.argtypes = [ctypes.c_void_p]
    xlib.XCloseDisplay.argtypes = [ctypes.c_void_p]

    class ClientMessage(ctypes.Structure):
        _fields_ = [("type", ctypes.c_int), ("serial", ctypes.c_ulong), ("send_event", ctypes.c_int),
                    ("display", ctypes.c_void_p), ("window", ctypes.c_ulong), ("message_type", ctypes.c_ulong),
                    ("format", ctypes.c_int), ("data", ctypes.c_long * 5), ("pad", ctypes.c_long * 19)]

    dpy = xlib.XOpenDisplay(display.encode())
    window = int(wid, 16) if isinstance(wid, str) else wid
    event = ClientMessage()
    event.type = 33  # ClientMessage
    event.window = window
    event.message_type = xlib.XInternAtom(dpy, b"WM_PROTOCOLS", 0)
    event.format = 32
    event.data[0] = xlib.XInternAtom(dpy, b"WM_DELETE_WINDOW", 0)
    event.data[1] = 0  # CurrentTime
    xlib.XSendEvent(dpy, window, 0, 0, ctypes.byref(event))
    xlib.XFlush(dpy)
    xlib.XCloseDisplay(dpy)


def ribbon_accent(display, wid, shot_path, first=33, last=130):
    """(y offset from the window top, colour name) of the active-tab accent line of the light Tabbed
    ribbon, or (None, None). The accent is a saturated horizontal run (module colour: Writer blue,
    Calc green, Impress orange) under the active ribbon tab. `shot_path` is a screenshot of the
    display taken while the window was on top."""
    from PIL import Image
    info = subprocess.run(["xwininfo", "-display", display, "-id", wid], capture_output=True, text=True).stdout
    left = max(int(re.search(r"Absolute upper-left X:\s+(-?\d+)", info).group(1)), 0)
    top = max(int(re.search(r"Absolute upper-left Y:\s+(-?\d+)", info).group(1)), 0)
    width = int(re.search(r"Width:\s+(\d+)", info).group(1))
    image = Image.open(shot_path).convert("RGB")
    for dy in range(first, last):
        run, best = 0, None
        for dx in range(0, min(width, image.width - left), 2):
            red, green, blue = image.getpixel((left + dx, top + dy))
            if max(red, green, blue) - min(red, green, blue) > 70:
                run += 1
                best = (red, green, blue)
                if run >= 20:  # 40 px wide
                    name = ("blue" if best[2] > best[0] and best[2] > best[1] else
                            "green" if best[1] > best[0] and best[1] > best[2] else "orange")
                    return dy, name
            else:
                run = 0
    return None, None


def tab_accent_colour(display, wid, shot_path):
    """Module colour (blue Writer, green Calc, orange Impress) of the accent line on top of the
    active document tab, below the ribbon; None when it is not found."""
    return ribbon_accent(display, wid, shot_path, first=120, last=260)[1]


def classic_menubar_visible(display, wid, shot_path):
    """True when the window `wid` shows the classic (GTK) menubar above its Tabbed ribbon.

    The light ribbon marks its active tab with a module-colour accent line about 40 px below the
    window top; a classic menubar on top pushes that line down by the menubar height (about 27 px).
    `shot_path` is a screenshot of the display taken while the window was on top."""
    offset, _colour = ribbon_accent(display, wid, shot_path)
    return offset is not None and offset > 55
