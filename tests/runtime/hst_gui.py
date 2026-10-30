# SPDX-License-Identifier: AGPL-3.0-only
"""Shared helper for GUI runtime checks: one HST Office instance on an existing X display.

Starts soffice (as the unprivileged build user when run as root, never as root) with a fresh
profile, a private vi_VN.UTF-8 locale (localedef + LOCPATH, so .ui labels are translated even
on hosts without a Vietnamese system locale) and a UNO socket on a deterministic port, and
offers small helpers: connect, load documents, list top-level X windows, take screenshots.

The display must already run (tests use Xvfb :97); this module never starts or kills it.
"""
import os
import re
import shutil
import subprocess
import threading
import time

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
BUILD_USER = os.environ.get("HST_BUILD_USER", "hstbuild")


def _as_user_prefix():
    return ["runuser", "-u", BUILD_USER, "--"] if os.geteuid() == 0 else []


def ensure_locale(base, locale="vi_VN"):
    """Compile <locale>.UTF-8 into base/locpath once; return the LOCPATH directory."""
    locpath = os.path.join(base, "locpath")
    target = os.path.join(locpath, f"{locale}.UTF-8")
    if not os.path.isdir(target):
        os.makedirs(locpath, exist_ok=True)
        subprocess.run(["localedef", "-i", locale, "-f", "UTF-8", target], check=False,
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    return locpath


class Office:
    """One soffice process with its own profile under `workdir`."""

    def __init__(self, instdir, workdir, port, display=":97", lang="vi_VN.UTF-8", extra_args=(), config=(), nodefault=True,
                 welcome=False, env=None):
        self.program = os.path.join(os.path.abspath(instdir), "program")
        self.workdir = os.path.abspath(workdir)
        self.port = port
        self.display = display
        self.lang = lang
        self.extra_args = list(extra_args) + (["--nodefault"] if nodefault else [])
        # (node path, property, xml value) written into the fresh profile before the GUI start.
        # The HST welcome dialog is modal and would block UNO calls: mark it as shown.
        self.config = [("/org.hasontech.hstoffice.Welcome", "Shown", "true"),
                       ("/org.openoffice.Office.Common/Misc", "ShowTipOfTheDay", "false")] + list(config)
        self.welcome = welcome  # True: leave the welcome dialog up (the caller closes it)
        self.extra_env = dict(env or {})
        self.proc = None
        self.ctx = None

    def _env(self):
        env = {k: v for k, v in os.environ.items() if k not in ("URE_BOOTSTRAP", "SAL_USE_VCLPLUGIN")}
        env.update(DISPLAY=self.display, LANG=self.lang, LC_ALL=self.lang, HOME=os.path.join(self.workdir, "home"))
        if self.lang.startswith("vi_"):
            env["LOCPATH"] = ensure_locale(self.workdir)
        env["SAL_USE_VCLPLUGIN"] = os.environ.get("HST_VCLPLUGIN", "gtk3")
        return env

    def start(self, fresh=True):
        profile = os.path.join(self.workdir, "profile")
        if fresh:
            shutil.rmtree(profile, ignore_errors=True)
        os.makedirs(os.path.join(self.workdir, "home"), exist_ok=True)
        os.makedirs(profile, exist_ok=True)
        env = self._env()
        if os.geteuid() == 0:
            subprocess.run(["chown", "-R", BUILD_USER, self.workdir], check=True)
        args = [f"-env:UserInstallation=file://{profile}", "--norestore", "--nologo",
                f"--accept=socket,host=127.0.0.1,port={self.port};urp;"] + self.extra_args
        if fresh:
            # A fresh profile makes soffice restart itself once (exit 81); initialise it first.
            for _ in range(3):
                warm = subprocess.run(_as_user_prefix() + [os.path.join(self.program, "soffice.bin"), "--headless",
                                      "--norestore", "--terminate_after_init", args[0]], env=env, timeout=180, check=False)
                if warm.returncode == 0:
                    break
            self._seed_profile(profile)
        # extra variables go to soffice only (runuser resets PATH; our own lookups need it)
        extra = ["env"] + [f"{k}={v}" for k, v in self.extra_env.items()] if self.extra_env else []
        self.proc = subprocess.Popen(_as_user_prefix() + extra + [os.path.join(self.program, "soffice")] + args, env=env)
        self._stop_watch = threading.Event()
        if not self.welcome:
            threading.Thread(target=self._dismiss_welcome, daemon=True).start()
        self.ctx = self._connect()
        return self

    @property
    def pid(self):
        """pid of this instance's soffice.bin (windows carry it in _NET_WM_PID). Not cached:
        soffice.bin may restart itself (new pid) while a fresh profile settles."""
        profile = os.path.join(self.workdir, "profile")
        out = subprocess.run(["pgrep", "-f", f"soffice.bin.*UserInstallation=file://{profile}"],
                             capture_output=True, text=True).stdout.split()
        return int(out[0]) if out else None

    def _dismiss_welcome(self):
        """The modal HST welcome dialog (first visible window of a fresh profile) blocks UNO
        calls until closed; click its close button whenever it appears."""
        pattern = re.compile(r"Chào mừng|Welcome to")
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

    def _seed_profile(self, profile):
        path = os.path.join(profile, "user", "registrymodifications.xcu")
        items = "".join(f'<item oor:path="{node}"><prop oor:name="{name}" oor:op="fuse"><value>{value}</value></prop></item>\n'
                        for node, name, value in self.config)
        with open(path, encoding="utf-8") as handle:
            text = handle.read()
        with open(path, "w", encoding="utf-8") as handle:
            handle.write(text.replace("</oor:items>", items + "</oor:items>"))

    def _connect(self, timeout=120):
        import uno  # noqa: F401  (needs the instdir program dir on sys.path, see setup_uno)
        local = uno.getComponentContext()
        deadline = time.time() + timeout
        while True:
            try:
                resolver = local.ServiceManager.createInstanceWithContext("com.sun.star.bridge.UnoUrlResolver", local)
                ctx = resolver.resolve(f"uno:socket,host=127.0.0.1,port={self.port};urp;StarOffice.ComponentContext")
                time.sleep(3)  # let startup settle before the first calls
                return ctx
            except Exception:
                if time.time() > deadline:
                    raise
                time.sleep(1)

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
            if re.search(r"Chào mừng|Welcome to", name):
                self.click_close(wid)
                return True
        return False

    def raise_windows(self):
        """Raise this instance's mapped windows (another instance may share the display)."""
        env = dict(os.environ, DISPLAY=self.display)
        # document/Start Center windows first, dialogs last (on top)
        windows = sorted(toplevels(self.display, self.pid), key=lambda w: w[1] == "HST Office" or " — HST Office" in w[1])
        for wid, _name in reversed(windows):
            subprocess.run(["xdotool", "windowraise", wid], env=env, check=False, timeout=10)
        time.sleep(0.5)

    def screenshot(self, path):
        self.raise_windows()
        return screenshot(path, self.display)

    @property
    def smgr(self):
        return self.ctx.ServiceManager

    def service(self, name):
        return self.smgr.createInstanceWithContext(name, self.ctx)

    def desktop(self):
        return self.service("com.sun.star.frame.Desktop")

    def load(self, url, target="_blank", hidden=False):
        from com.sun.star.beans import PropertyValue
        prop = PropertyValue()
        prop.Name, prop.Value = "Hidden", hidden
        return self.desktop().loadComponentFromURL(url, target, 0, (prop,))

    def dispatch(self, frame, command, args=()):
        helper = self.service("com.sun.star.frame.DispatchHelper")
        return helper.executeDispatch(frame, command, "", 0, tuple(args))

    def set_config(self, node, name, value):
        from com.sun.star.beans import PropertyValue
        provider = self.service("com.sun.star.configuration.ConfigurationProvider")
        arg = PropertyValue()
        arg.Name, arg.Value = "nodepath", node
        access = provider.createInstanceWithArguments("com.sun.star.configuration.ConfigurationUpdateAccess", (arg,))
        access.setPropertyValue(name, value)
        access.commitChanges()

    def stop(self):
        if getattr(self, "_stop_watch", None):
            self._stop_watch.set()
        try:
            if self.ctx is not None:
                self.desktop().terminate()
        except Exception:
            pass
        if self.proc is not None:
            try:
                self.proc.wait(timeout=30)
            except subprocess.TimeoutExpired:
                self.proc.terminate()
                try:
                    self.proc.wait(timeout=15)
                except subprocess.TimeoutExpired:
                    self.proc.kill()
        # soffice (oosplash) may leave soffice.bin behind when killed: stop only ours (same profile).
        subprocess.run(["pkill", "-f", f"UserInstallation=file://{os.path.join(self.workdir, 'profile')}"], check=False)


def setup_uno(instdir):
    """Make the build's Python-UNO bridge importable in this process."""
    import sys
    program = os.path.join(os.path.abspath(instdir), "program")
    if os.path.exists(os.path.join(program, "uno.py")) and program not in sys.path:
        sys.path.insert(0, program)
        os.environ["URE_BOOTSTRAP"] = "vnd.sun.star.pathname:" + os.path.join(program, "fundamentalrc")


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
