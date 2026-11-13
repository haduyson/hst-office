# SPDX-License-Identifier: AGPL-3.0-only
"""A headless HST Office for portable UNO checks (Linux, Windows, macOS): fresh profile, fixed port, stop what it started.

Usage: office = Office(path_to_soffice, workdir, port); doc = office.load(url); ...; office.stop()
The interpreter must have the office's Python-UNO bridge (Windows/macOS: the office's own python; Linux: any
python3 when the program folder has uno.py).
"""
import os
import subprocess
import sys
import time


def import_uno(soffice):
    try:
        import uno  # noqa: F401
    except ImportError:
        program = os.path.dirname(os.path.abspath(soffice))
        sys.path.insert(0, program)
        os.environ.setdefault("URE_BOOTSTRAP", "vnd.sun.star.pathname:" + os.path.join(program, "fundamentalrc"))
    import uno
    return uno


def props(**values):
    from com.sun.star.beans import PropertyValue
    result = []
    for name, value in values.items():
        prop = PropertyValue()
        prop.Name, prop.Value = name, value
        result.append(prop)
    return tuple(result)


class Office:
    def __init__(self, soffice, workdir, port):
        self.uno = import_uno(soffice)
        profile = self.uno.systemPathToFileUrl(os.path.join(workdir, "profile"))
        self.proc = subprocess.Popen([soffice, "--headless", "--invisible", "--norestore", "--nologo", "--nodefault",
                                      "-env:UserInstallation=" + profile,
                                      f"--accept=socket,host=127.0.0.1,port={port};urp;"])
        local = self.uno.getComponentContext()
        resolver = local.ServiceManager.createInstanceWithContext("com.sun.star.bridge.UnoUrlResolver", local)
        for _ in range(240):
            try:
                self.ctx = resolver.resolve(f"uno:socket,host=127.0.0.1,port={port};urp;StarOffice.ComponentContext")
                break
            except Exception:  # noqa: BLE001 - the office is still starting
                time.sleep(0.5)
        else:
            raise SystemExit("office did not start")
        self.desktop = self.service("com.sun.star.frame.Desktop")

    def service(self, name):
        return self.ctx.ServiceManager.createInstanceWithContext(name, self.ctx)

    def url(self, path):
        return self.uno.systemPathToFileUrl(os.path.abspath(path))

    def load(self, url):
        return self.desktop.loadComponentFromURL(url, "_blank", 0, props(Hidden=True))

    def dispatch(self, doc, command):
        frame = doc.getCurrentController().getFrame()
        self.service("com.sun.star.frame.DispatchHelper").executeDispatch(frame, command, "", 0, ())

    def stop(self):
        try:
            self.desktop.terminate()
        except Exception:  # noqa: BLE001 - the bridge goes away while the office quits
            pass
        try:
            self.proc.wait(timeout=60)
        except subprocess.TimeoutExpired:
            self.proc.kill()
