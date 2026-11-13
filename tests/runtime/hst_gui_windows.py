# SPDX-License-Identifier: AGPL-3.0-only
"""hst_gui.Office for Windows: lets the hst_gui based runtime checks (written for Linux and Xvfb) run on Windows
against an installed or administratively extracted HST Office, through windows_gui.WinOffice.

Differences from Linux that matter (all handled here):
- soffice.exe returns before soffice.bin has written a new profile, and a --terminate_after_init start leaves the
  bundled-extension sync unfinished: the next start re-inserts the extensions' schemas and drops seeded values, so
  the modal welcome dialog appears and blocks Desktop/document close. The profile is therefore settled with
  soffice.bin --convert-to runs (as hst_gui_profile.settle_extensions does on Linux) before it is seeded.
- There is no display argument; `ui=False` starts the office --headless (no interactive session needed, but a
  headless office cannot open a comment for editing and shows no dialogs).
Run with the office's own python.exe. Only the office started here is stopped.
"""
import os
import subprocess

from hst_gui_profile import seed_profile
from windows_gui import WinOffice  # importable on Windows only (ctypes.WinDLL)

SEED = [("/org.hasontech.hstoffice.Welcome", "Shown", "true"), ("/org.hasontech.hstoffice.DefaultApps", "Ask", "false"),
        ("/org.openoffice.Office.Common/Misc", "ShowTipOfTheDay", "false")]


def settle_profile(program, profile, workdir, tries=4):
    """Create `profile` and finish its bundled-extension sync (the first run asks for a restart, exit 81)."""
    settle = os.path.join(workdir, "settle")
    os.makedirs(settle, exist_ok=True)
    empty = os.path.join(settle, "empty.txt")
    open(empty, "w").close()
    url = "-env:UserInstallation=file:///" + profile.replace("\\", "/")
    marker = os.path.join(profile, "user", "extensions", "bundled", "lastsynchronized")
    for _ in range(tries):
        done = subprocess.run([os.path.join(program, "soffice.bin"), "--headless", "--norestore", url, "--convert-to", "pdf",
                               "--outdir", settle, empty], timeout=300, capture_output=True, check=False)
        if done.returncode == 0 and os.path.exists(marker):
            return True
    return False


class _Office(WinOffice):
    """windows_gui.WinOffice, optionally --headless."""

    def __init__(self, *args, headless=False, **kwargs):
        super().__init__(*args, **kwargs)
        self.headless = headless

    def start(self, fresh=False):
        self.starts += 1
        cmd = [os.path.join(self.program, "soffice.exe"), "--norestore", "--nologo", "--nodefault",
               "-env:UserInstallation=" + self.url, "--accept=socket,host=127.0.0.1,port=%d;urp;" % self.port]
        os.makedirs(self.log_dir, exist_ok=True)
        log = os.path.join(self.log_dir, "soffice-%d" % self.starts)
        self.proc = subprocess.Popen(cmd + (["--headless"] if self.headless else []), stdout=open(log + ".out", "w"),
                                     stderr=open(log + ".err", "w"))
        self.ctx = self._connect()
        return self


class Office:
    """Same constructor and methods as hst_gui.Office (display is ignored); `ui` comes from HST_WINDOWS_UI=1."""

    def __init__(self, instdir, workdir, port, display=None, config=(), env=None, ui=None, **_ignored):
        self.instdir, self.workdir, self.port = os.path.abspath(instdir), os.path.abspath(workdir), port
        self.profile = os.path.join(self.workdir, "profile")
        self.config = SEED + list(config)
        self.ui = os.environ.get("HST_WINDOWS_UI") == "1" if ui is None else ui
        self.extra_env = dict(env or {})
        self.office = _Office(self.instdir, self.profile, port, os.path.join(self.workdir, "logs"), headless=not self.ui)
        self.ctx = None

    def start(self, fresh=True):
        if fresh:
            import shutil
            shutil.rmtree(self.profile, ignore_errors=True)
            os.makedirs(self.profile, exist_ok=True)
            settle_profile(os.path.join(self.instdir, "program"), self.profile, self.workdir)
            seed_profile(self.profile, self.config)
        os.environ.update(self.extra_env)  # inherited by soffice
        self.ctx = self.office.start().ctx
        return self

    @property
    def smgr(self):
        return self.ctx.ServiceManager

    def service(self, name):
        return self.office.service(name)

    def desktop(self):
        return self.office.desktop

    def load(self, url, target="_blank", hidden=False):
        from com.sun.star.beans import PropertyValue
        prop = PropertyValue()
        prop.Name, prop.Value = "Hidden", hidden
        return self.desktop().loadComponentFromURL(url, target, 0, (prop,))

    def dispatch(self, frame, command, args=()):
        return self.service("com.sun.star.frame.DispatchHelper").executeDispatch(frame, command, "", 0, tuple(args))

    def set_config(self, node, name, value):
        from com.sun.star.beans import PropertyValue
        arg = PropertyValue()
        arg.Name, arg.Value = "nodepath", node
        access = self.service("com.sun.star.configuration.ConfigurationProvider").createInstanceWithArguments(
            "com.sun.star.configuration.ConfigurationUpdateAccess", (arg,))
        access.setPropertyValue(name, value)
        access.commitChanges()

    def stop(self):
        self.office.stop()
        self.ctx = None


def install():
    """Make hst_gui use this Office (and skip its Linux-only UNO path setup: python.exe already imports uno)."""
    import hst_gui
    hst_gui.Office, hst_gui.setup_uno = Office, lambda instdir: None
