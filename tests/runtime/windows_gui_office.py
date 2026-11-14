# SPDX-License-Identifier: AGPL-3.0-only
"""One installed HST Office started with its own profile for the Windows GUI checks (the office's python.exe, so
`import uno` works). Nothing here starts or stops anything but the office it started itself: its soffice.bin
processes are the ones whose -env:UserInstallation is this office's private profile (windows_gui_processes); while
it runs, the input gate lets keys and clicks reach only their windows."""
import os
import subprocess
import threading
import time

import windows_gui_guard as guard
import windows_gui_processes as processes


class WinOffice:
    """One soffice process of an installed HST Office with its own profile directory `profile`.

    `fresh`: start from an empty profile exactly as a new user does: no warm-up start, nothing seeded, the Start Center
    shown (no --nodefault) so the start-up jobs (onFirstVisibleTask) run as they do for the user."""

    def __init__(self, install, profile, port, log_dir, nodefault=False):
        self.program = os.path.join(install, "program")
        self.profile = os.path.abspath(profile)
        self.port = port
        self.log_dir = log_dir
        self.nodefault = nodefault
        self.proc = None
        self.ctx = None
        self.starts = 0
        self.owner, self.leftover = None, []

    @property
    def url(self):
        return "file:///" + self.profile.replace("\\", "/")

    def start(self, fresh=False):
        import shutil
        if fresh:
            shutil.rmtree(self.profile, ignore_errors=True)
        os.makedirs(self.profile, exist_ok=True)
        os.makedirs(self.log_dir, exist_ok=True)
        self.starts += 1
        cmd = [os.path.join(self.program, "soffice.exe"), "--norestore", "-env:UserInstallation=" + self.url,
               "--accept=socket,host=127.0.0.1,port=%d;urp;" % self.port] + (["--nodefault"] if self.nodefault else [])
        log = os.path.join(self.log_dir, "soffice-%d" % self.starts)
        self.proc = subprocess.Popen(cmd, stdout=open(log + ".out", "w"), stderr=open(log + ".err", "w"))
        self.owner = processes.ProfileOwner(self.url)
        guard.register_owner(self.owner)
        self.ctx = self._connect()
        return self

    def _connect(self, timeout=180):
        import uno
        local = uno.getComponentContext()
        resolver = local.ServiceManager.createInstanceWithContext("com.sun.star.bridge.UnoUrlResolver", local)
        deadline = time.time() + timeout
        while True:
            try:
                ctx = resolver.resolve("uno:socket,host=127.0.0.1,port=%d;urp;StarOffice.ComponentContext" % self.port)
                ctx.ServiceManager.createInstanceWithContext("com.sun.star.frame.Desktop", ctx)
                return ctx
            except Exception:  # noqa: BLE001 - not up yet, or the first start restarting itself after the extension sync
                if time.time() > deadline:
                    raise RuntimeError("UNO socket of %s did not open in %d s" % (self.profile, timeout))
                time.sleep(1)

    def service(self, name):
        return self.ctx.ServiceManager.createInstanceWithContext(name, self.ctx)

    def expand(self, text):
        """A vnd.sun.star.expand: URL or a $MACRO text as the office expands it (a file URL for the install)."""
        text = text.replace("vnd.sun.star.expand:", "", 1) if text.startswith("vnd.sun.star.expand:") else text
        return self.ctx.getValueByName("/singletons/com.sun.star.util.theMacroExpander").expandMacros(text)

    @staticmethod
    def bin_pids():
        """Process ids of every soffice.bin (a change between two calls shows the office restarted itself)."""
        listing = subprocess.run(["tasklist", "/FI", "IMAGENAME eq soffice.bin", "/FO", "CSV", "/NH"],
                                 capture_output=True, text=True, check=False).stdout
        return sorted(int(row.split('","')[1]) for row in listing.splitlines() if row.startswith('"soffice.bin"'))

    @property
    def desktop(self):
        return self.service("com.sun.star.frame.Desktop")

    def top_windows(self):
        toolkit = self.service("com.sun.star.awt.Toolkit")
        return [toolkit.getTopWindow(i) for i in range(toolkit.getTopWindowCount())]

    def load(self, url, hidden=False, **props):
        from com.sun.star.beans import PropertyValue
        args = []
        for name, value in dict(props, Hidden=hidden).items():
            prop = PropertyValue()
            prop.Name, prop.Value = name, value
            args.append(prop)
        return self.desktop.loadComponentFromURL(url, "_blank", 0, tuple(args))

    def dispatch_async(self, frame, command, **props):
        """Dispatch `command` from a thread (a modal dialog blocks the call until it closes); returns the thread."""
        from com.sun.star.beans import PropertyValue
        args = []
        for name, value in props.items():
            prop = PropertyValue()
            prop.Name, prop.Value = name, value
            args.append(prop)
        helper = self.service("com.sun.star.frame.DispatchHelper")
        thread = threading.Thread(target=lambda: helper.executeDispatch(frame, command, "", 0, tuple(args)), daemon=True)
        thread.start()
        return thread

    def config(self, node, name):
        import uno
        arg = uno.createUnoStruct("com.sun.star.beans.PropertyValue")
        arg.Name, arg.Value = "nodepath", node
        access = self.service("com.sun.star.configuration.ConfigurationProvider").createInstanceWithArguments(
            "com.sun.star.configuration.ConfigurationAccess", (arg,))
        return access.getPropertyValue(name) if name else access

    def bin_pids_of_profile(self):
        """PIDs of this office's own soffice.bin (its profile URL in the command line), also after a restart."""
        return processes.profile_bin_pids(self.url)

    def stop(self, timeout=60):
        """Quit through Desktop.terminate (the caller closes its modal dialogs first), then end what is left of our
        own processes: the soffice.exe started here and the soffice.bin of our profile, never another soffice."""
        if self.proc is None:
            return None
        guard.unregister_owner(self.owner)
        self.owner = None
        try:
            self.desktop.terminate()
        except Exception:  # noqa: BLE001 - the bridge goes away while the office quits
            pass
        try:
            self.proc.wait(timeout)
        except subprocess.TimeoutExpired:
            self.proc.kill()
            self.proc.wait(10)
        code, self.proc, self.ctx = self.proc.returncode, None, None
        self.leftover = processes.terminate(self.url)  # a soffice.bin of a first-start restart outlives soffice.exe
        # soffice.exe returns when soffice.bin ended; wait until our profile's lock file is gone too
        lock = os.path.join(self.profile, ".lock")
        for _ in range(30):
            if not os.path.exists(lock):
                break
            time.sleep(1)
        return code
