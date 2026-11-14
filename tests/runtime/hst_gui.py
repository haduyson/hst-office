# SPDX-License-Identifier: AGPL-3.0-only
"""Shared helper for GUI runtime checks: one HST Office instance on an existing X display.

Starts soffice (as the unprivileged build user when run as root, never as root) with a fresh
profile, a private vi_VN.UTF-8 locale (localedef + LOCPATH, so .ui labels are translated even
on hosts without a Vietnamese system locale) and a UNO socket on a deterministic port, and
offers small helpers: connect, load documents, list top-level X windows, take screenshots.

The display must already run (tests use Xvfb :97); this module never starts or kills it.
"""
import os
import shutil
import socket
import subprocess
import threading
import time

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
# helpers kept importable from here: the checks use hst_gui.toplevels, hst_gui.screenshot, ...
from hst_gui_profile import BUILD_USER, _as_user_prefix, ensure_locale, seed_profile, settle_extensions  # noqa: E402,F401
from hst_gui_own_office import ForeignOfficeError, ensure_own_office  # noqa: E402,F401
from hst_gui_x11 import (WindowMixin, classic_menubar_visible, mapped_toplevels, ribbon_accent,  # noqa: E402,F401
                         screenshot, send_close_request, tab_accent_colour, toplevels, window_pid)


class Office(WindowMixin):
    """One soffice process with its own profile under `workdir`."""

    def __init__(self, instdir, workdir, port, display=":97", lang="vi_VN.UTF-8", extra_args=(), config=(), nodefault=True,
                 welcome=False, env=None, restore=False):
        self.program = os.path.join(os.path.abspath(instdir), "program")
        self.workdir = os.path.abspath(workdir)
        self.port = port
        self.display = display
        self.lang = lang
        self.extra_args = list(extra_args) + (["--nodefault"] if nodefault else [])
        # (node path, property, xml value) written into the fresh profile before the GUI start.
        # The HST welcome dialog is modal and would block UNO calls: mark it as shown.
        # The default-apps question is modal too: answered in every test profile unless a check asks for it.
        self.config = [("/org.hasontech.hstoffice.Welcome", "Shown", "true"),
                       ("/org.hasontech.hstoffice.DefaultApps", "Ask", "false"),
                       ("/org.openoffice.Office.Common/Misc", "ShowTipOfTheDay", "false")] + list(config)
        self.welcome = welcome  # True: leave the welcome dialog up (the caller closes it)
        self.extra_env = dict(env or {})
        self.restore = restore  # True: no --norestore (AutoRecovery/session restore active)
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
        args = [f"-env:UserInstallation=file://{profile}"] + ([] if self.restore else ["--norestore"]) + ["--nologo",
                f"--accept=socket,host=127.0.0.1,port={self.port};urp;"] + self.extra_args
        if fresh:
            # A fresh profile makes soffice restart itself once (exit 81); initialise it first.
            for _ in range(3):
                warm = subprocess.run(_as_user_prefix() + [os.path.join(self.program, "soffice.bin"), "--headless",
                                      "--norestore", "--terminate_after_init", args[0]], env=env, timeout=180, check=False)
                if warm.returncode == 0:
                    break
            settle_extensions(self.program, self.workdir, profile, env, args[0])
            seed_profile(profile, self.config)
        # extra variables go to soffice only (runuser resets PATH; our own lookups need it)
        extra = ["env"] + [f"{k}={v}" for k, v in self.extra_env.items()] if self.extra_env else []
        self.proc = subprocess.Popen(_as_user_prefix() + extra + [os.path.join(self.program, "soffice")] + args, env=env)
        self._stop_watch = threading.Event()
        if not self.welcome:
            threading.Thread(target=self._dismiss_welcome, daemon=True).start()
        self.ctx = self._connect_own()
        return self

    def _connect_own(self):
        try:
            return self._connect()
        except ForeignOfficeError:
            self.stop()  # without a bridge stop() ends only our own process, never the other office
            raise

    @property
    def pid(self):
        """pid of this instance's soffice.bin (windows carry it in _NET_WM_PID). Not cached:
        soffice.bin may restart itself (new pid) while a fresh profile settles."""
        profile = os.path.join(self.workdir, "profile")
        out = subprocess.run(["pgrep", "-f", f"soffice.bin.*UserInstallation=file://{profile}"],
                             capture_output=True, text=True).stdout.split()
        return int(out[0]) if out else None

    def _connect(self, timeout=120):
        import uno  # noqa: F401  (needs the instdir program dir on sys.path, see setup_uno)
        local = uno.getComponentContext()
        deadline = time.time() + timeout
        while True:
            try:
                resolver = local.ServiceManager.createInstanceWithContext("com.sun.star.bridge.UnoUrlResolver", local)
                ctx = resolver.resolve(f"uno:socket,host=127.0.0.1,port={self.port};urp;StarOffice.ComponentContext")
            except Exception:
                if time.time() > deadline:
                    raise
                time.sleep(1)
                continue
            ensure_own_office(ctx, self.workdir, self.port)  # never drive a parallel run's office
            time.sleep(3)  # let startup settle before the first calls
            return ctx

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

    def _terminate(self):
        try:
            desktop = self.desktop()
            # Like the office's own Quit (desktop/source/app/app.cxx Desktop::QueryExit): on macOS the Dock menu
            # (quick starter) vetoes a plain terminate(), the office stays up and is then killed, which its next
            # start reports as a crash ("Lần trước HST Office bị đóng đột ngột", r1-auto macOS run 42929394182 M3).
            desktop.setPropertyValue("SuspendQuickstartVeto", True)
            desktop.terminate()
        except Exception:  # noqa: BLE001 - the bridge goes away while the office quits
            pass

    def stop(self):
        if getattr(self, "_stop_watch", None):
            self._stop_watch.set()
        if self.ctx is not None:
            # terminate() never returns while a modal dialog is up (e.g. the save question of a document a
            # failed check left modified): wait a bounded time, then the process is ended below.
            closer = threading.Thread(target=self._terminate, daemon=True)
            closer.start()
            closer.join(60)
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


def free_port():
    """A TCP port on 127.0.0.1 that is free right now, for checks that must not clash with other sessions."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


def setup_uno(instdir):
    """Make the build's Python-UNO bridge importable in this process."""
    import sys
    program = os.path.join(os.path.abspath(instdir), "program")
    if os.path.exists(os.path.join(program, "uno.py")) and program not in sys.path:
        sys.path.insert(0, program)
        os.environ["URE_BOOTSTRAP"] = "vnd.sun.star.pathname:" + os.path.join(program, "fundamentalrc")
