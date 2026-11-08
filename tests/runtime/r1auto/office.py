# SPDX-License-Identifier: AGPL-3.0-only
"""Native lifecycle adapter; reuse existing UNO methods and Windows smoke helpers."""
import os
from pathlib import Path
import platform
import subprocess
import sys
import time
from support import existing, native, wait, background
import hst_gui

smoke = existing("check-windows-smoke")


class Office(hst_gui.Office):
    def __init__(self, install, workdir, port=22122):
        self.install, self.workdir = Path(install).resolve(), str(Path(workdir).resolve())
        self.profile = Path(self.workdir) / "profile"
        self.port, self.ctx, self.proc = port, None, None
        self.display = os.environ.get("DISPLAY", ":160")
        self.system = platform.system()
        self.program = str(self.install / ("Contents/MacOS" if self.system == "Darwin" else "program"))
        self.binary = Path(self.program) / ("soffice.exe" if self.system == "Windows" else "soffice")
        self.logs = []
        # A socket listener raises macOS's "find devices on local networks" alert, which takes keyboard focus.
        self.pipe = f"r1office{port}"

    def accept(self):
        if self.system == "Darwin":
            return f"--accept=pipe,name={self.pipe};urp;"
        return f"--accept=socket,host=127.0.0.1,port={self.port};urp;"

    def _connect(self, timeout=120):
        if self.system != "Darwin":
            return super()._connect(timeout)
        import uno
        local = uno.getComponentContext()
        resolver = local.ServiceManager.createInstanceWithContext("com.sun.star.bridge.UnoUrlResolver", local)
        end = time.monotonic() + timeout
        while True:
            try:
                ctx = resolver.resolve(f"uno:pipe,name={self.pipe};urp;StarOffice.ComponentContext")
                time.sleep(3)  # let startup settle before the first calls
                return ctx
            except Exception:
                if time.monotonic() > end:
                    raise
                time.sleep(1)

    def start(self):
        import uno
        from support import claim_port
        claim_port(self.port)
        Path(self.workdir).mkdir(parents=True, exist_ok=True)
        if self.profile.exists():
            raise RuntimeError("Profile đã tồn tại; cần thư mục chạy mới")
        user = "-env:UserInstallation=" + self.profile.as_uri()
        from hst_gui_macos import DRIVER_ONLY
        env = {k: v for k, v in os.environ.items() if k not in DRIVER_ONLY}
        # VCL builds the accessibility of toolbars and top windows only with AT support on (Linux has AT-SPI);
        # the probes read the ribbon and popups through it (MiscSettings::GetEnableATToolSupport).
        env.update(LANG="vi_VN.UTF-8", SAL_ACCESSIBILITY_ENABLED="1")
        empty = Path(self.workdir) / "init.txt"
        empty.write_text("", encoding="utf-8")
        for _ in range(3):
            done = subprocess.run([str(self.binary), user, "--headless", "--norestore", "--convert-to", "pdf",
                                   "--outdir", self.workdir, str(empty)], capture_output=True, timeout=120, env=env)
            if done.returncode == 0 and (self.profile / "user/registrymodifications.xcu").exists():
                break
        else:
            raise RuntimeError("Không khởi tạo được profile")
        hst_gui.seed_profile(str(self.profile), [
            ("/org.openoffice.Office.Linguistic/General", "UILocale", "vi"),
            ("/org.hasontech.hstoffice.Welcome", "Shown", "true"),
            ("/org.hasontech.hstoffice.DefaultApps", "Ask", "false"),
            ("/org.openoffice.Office.Common/Misc", "ShowTipOfTheDay", "false"),
            ("/org.openoffice.Office.Common/History", "RecentDocsThumbnail", "true")])
        if self.system == "Windows":
            self.proc, self.ctx = smoke.start_office(self.program, self.profile.as_uri(), self.port,
                                                    str(Path(self.workdir) / "office.log"), env)
        else:
            log = open(Path(self.workdir) / "office.log", "w", encoding="utf-8")
            self.logs.append(log)
            self.proc = subprocess.Popen([str(self.binary), user, "--nologo", "--norestore", "--nodefault",
                                          self.accept()],
                                         stdout=log, stderr=log, env=env)
            self.ctx = self._connect()
        extensions = list(self.install.glob("**/hst-vietnamese-tools/python"))
        if len(extensions) != 1:
            raise RuntimeError("Không xác định được extension đã cài")
        sys.path.insert(0, str(extensions[0]))
        return self

    def titles(self):
        try:
            return [smoke.window_title(w) for w in smoke.top_windows(self.service("com.sun.star.awt.Toolkit"))]
        except Exception:
            return []

    def screenshot(self, path):
        return native("shot", path)

    def stop(self):
        if self.ctx is not None:
            background(self._terminate).join(5)
        native("cleanup", self.profile.as_uri())
        if self.proc:
            try:
                self.proc.wait(5)
            except subprocess.TimeoutExpired:
                self.proc.terminate()
                self.proc.wait(5)
        for stream in self.logs:
            stream.close()
        self.ctx = None

    def focus(self, window):
        # Windows refuses the foreground to a background process unless the last input came from it: press Alt
        # first (as windows_gui.foreground does), but never while HST is in front (Alt would focus its menu).
        if self.system == "Windows" and not native("front").lower().startswith("soffice"):
            native("key", "alt")
        window.setVisible(True)
        window.toFront()
        window.setFocus()
        time.sleep(0.5)

    def config(self, node, name):
        from pdf_viewer_uno import signing_props
        access = self.service("com.sun.star.configuration.ConfigurationProvider").createInstanceWithArguments(
            "com.sun.star.configuration.ConfigurationAccess", signing_props(nodepath=node))
        return access.getPropertyValue(name)
