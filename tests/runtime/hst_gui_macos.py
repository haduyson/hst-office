# SPDX-License-Identifier: AGPL-3.0-only
"""macOS counterpart of hst_gui.Office: one HST Office.app instance driven over UNO.

Runs inside the app's bundled Python (it provides `uno`). Each instance has its own profile and
HOME under `workdir`; extra environment variables go to soffice only. The optional .oxt is
installed into the fresh profile with the app's own unopkg, as the current (normal) user, so the
signed bundle itself is never modified. Screenshots use `screencapture` (whole screen).
"""
import os
from pathlib import Path
import shutil
import subprocess
import time

# Driver-only variables that must not leak into soffice's embedded Python.
DRIVER_ONLY = ("PYTHONPATH", "PYTHONHOME", "URE_BOOTSTRAP", "PYTHONNOUSERSITE")


class Office:
    def __init__(self, app, workdir, port, env=None, config=(), oxt=None):
        self.app = Path(app)
        self.program = str(self.app / "Contents/MacOS")
        self.workdir = str(Path(workdir).resolve())
        self.port = port
        self.extra_env = dict(env or {})
        self.config = [("/org.hasontech.hstoffice.Welcome", "Shown", "true"),
                       ("/org.openoffice.Office.Common/Misc", "ShowTipOfTheDay", "false")] + list(config)
        self.oxt = oxt
        self.extra_args = []
        self.proc = None
        self.ctx = None
        self.logs = Path(self.workdir) / "logs"

    @property
    def home(self):
        return Path(self.workdir) / "home"

    @property
    def profile(self):
        return Path(self.workdir) / "profile"

    def _env(self):
        env = {k: v for k, v in os.environ.items() if k not in DRIVER_ONLY}
        env.update(HOME=str(self.home), LANG="vi_VN.UTF-8", LC_ALL="vi_VN.UTF-8")
        env.update(self.extra_env)
        return env

    def _run(self, name, args, timeout=300):
        self.logs.mkdir(parents=True, exist_ok=True)
        with open(self.logs / (name + ".log"), "a", encoding="utf-8") as log:
            log.write("$ " + " ".join(args) + "\n")
            log.flush()
            return subprocess.run(args, env=self._env(), stdout=log, stderr=subprocess.STDOUT,
                                  stdin=subprocess.DEVNULL, timeout=timeout, check=False).returncode

    def _install_arg(self):
        return "-env:UserInstallation=" + self.profile.as_uri()

    def prepare(self):
        """Fresh profile: settle the first-start restart (exit 81), unopkg add, seed settings."""
        shutil.rmtree(self.profile, ignore_errors=True)
        self.home.mkdir(parents=True, exist_ok=True)
        for _ in range(3):
            if self._run("init", [self.program + "/soffice", "--headless", "--norestore",
                                  "--terminate_after_init", self._install_arg()]) == 0:
                break
        if self.oxt:
            unopkg = self.program + "/unopkg"
            code = self._run("unopkg", [unopkg, "add", "--suppress-license", "--force", self._install_arg(), str(self.oxt)])
            assert code == 0, "unopkg add failed (%d), see %s" % (code, self.logs / "unopkg.log")
            self._run("unopkg", [unopkg, "list", self._install_arg()])
        xcu = self.profile / "user/registrymodifications.xcu"
        items = "".join('<item oor:path="%s"><prop oor:name="%s" oor:op="fuse"><value>%s</value></prop></item>\n'
                        % item for item in self.config)
        xcu.write_text(xcu.read_text(encoding="utf-8").replace("</oor:items>", items + "</oor:items>"), encoding="utf-8")

    def start(self, fresh=True):
        if fresh:
            self.prepare()
        self.logs.mkdir(parents=True, exist_ok=True)
        log = open(self.logs / "soffice.log", "a", encoding="utf-8")
        args = [self.program + "/soffice", self._install_arg(), "--norestore", "--nologo", "--nodefault",
                "--accept=socket,host=127.0.0.1,port=%d;urp;" % self.port] + self.extra_args
        self.proc = subprocess.Popen(args, env=self._env(), stdout=log, stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL)
        log.close()
        self.ctx = self._connect()
        self.front()
        return self

    def _connect(self, timeout=180):
        import uno
        local = uno.getComponentContext()
        resolver = local.ServiceManager.createInstanceWithContext("com.sun.star.bridge.UnoUrlResolver", local)
        deadline = time.time() + timeout
        while True:
            try:
                ctx = resolver.resolve("uno:socket,host=127.0.0.1,port=%d;urp;StarOffice.ComponentContext" % self.port)
                time.sleep(3)
                return ctx
            except Exception:  # noqa: BLE001 - not listening yet
                if time.time() > deadline or self.proc.poll() is not None:
                    raise
                time.sleep(1)

    def front(self):
        """A shell-started app is not frontmost; bring it forward for meaningful screenshots."""
        script = ('tell application "System Events" to set frontmost of (first process whose unix id is %d) to true'
                  % self.proc.pid)
        subprocess.run(["perl", "-e", "alarm 20; exec @ARGV", "osascript", "-e", script],
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False)

    def screenshot(self, path):
        os.makedirs(os.path.dirname(path), exist_ok=True)
        self.front()
        subprocess.run(["screencapture", "-x", path], check=False, timeout=30)
        return path

    @property
    def smgr(self):
        return self.ctx.ServiceManager

    def service(self, name):
        return self.smgr.createInstanceWithContext(name, self.ctx)

    def desktop(self):
        return self.service("com.sun.star.frame.Desktop")

    def load(self, url, target="_blank", hidden=False):
        from com.sun.star.beans import PropertyValue
        return self.desktop().loadComponentFromURL(url, target, 0, (PropertyValue(Name="Hidden", Value=hidden),))

    def dispatch(self, frame, command, args=()):
        helper = self.service("com.sun.star.frame.DispatchHelper")
        return helper.executeDispatch(frame, command, "", 0, tuple(args))

    def config_value(self, node, name):
        from com.sun.star.beans import PropertyValue
        provider = self.service("com.sun.star.configuration.ConfigurationProvider")
        access = provider.createInstanceWithArguments("com.sun.star.configuration.ConfigurationAccess",
                                                      (PropertyValue(Name="nodepath", Value=node),))
        return access.getPropertyValue(name)

    def stop(self):
        try:
            if self.ctx is not None:
                self.desktop().terminate()
        except Exception:  # noqa: BLE001 - the bridge drops while terminating
            pass
        self.ctx = None
        if self.proc is not None:
            try:
                self.proc.wait(timeout=60)
            except subprocess.TimeoutExpired:
                self.proc.terminate()
                try:
                    self.proc.wait(timeout=15)
                except subprocess.TimeoutExpired:
                    self.proc.kill()
                    self.proc.wait(timeout=15)
            self.proc = None
