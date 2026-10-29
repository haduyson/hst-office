# SPDX-License-Identifier: AGPL-3.0-only
"""Isolated LibreOffice session for extension runtime checks: own profile, unopkg install, socket UNO, clean teardown."""
import glob
import os
import shutil
import signal
import subprocess
import time

import uno
from com.sun.star.beans import PropertyValue

NAME = "hst-vietnamese-tools"
CLEAN_ENV_DROP = ("URE_BOOTSTRAP", "UNO_PATH", "PYTHONHOME", "PYTHONPATH")


def clean_env(extra=None):
    env = {k: v for k, v in os.environ.items() if k not in CLEAN_ENV_DROP}
    env.update(extra or {})
    return env


def props(**kwargs):
    out = []
    for name, value in kwargs.items():
        p = PropertyValue()
        p.Name, p.Value = name, value
        out.append(p)
    return tuple(out)


class Session:
    def __init__(self, soffice, extension, workdir, port=2105, display=None, mode="user"):
        self.soffice, self.extension, self.workdir, self.port, self.mode = soffice, extension, workdir, port, mode
        self.unprivileged = mode == "user" and os.geteuid() == 0  # unopkg refuses to add a user extension as root
        if self.unprivileged:
            self.workdir = workdir = "/var/tmp/hst-ext-check-%d" % port  # the scratch tree is root-only; nobody must traverse it
        self.profile = os.path.join(workdir, "profile")
        self.profile_url = "file://" + self.profile
        self.display, self.proc, self.ctx, self.desktop = display, None, None, None

    def _env(self):
        extra = {"DISPLAY": self.display} if self.display else {}
        if self.unprivileged:
            extra.update(HOME=self.workdir, XDG_CACHE_HOME=os.path.join(self.workdir, "cache"), XDG_CONFIG_HOME=os.path.join(self.workdir, "config"))
        return clean_env(extra)

    def unopkg(self, *args):
        cmd = [os.path.join(os.path.dirname(self.soffice), "unopkg"), *args, "-env:UserInstallation=" + self.profile_url]
        if self.unprivileged:
            cmd = ["setpriv", "--reuid=65534", "--regid=65534", "--clear-groups", *cmd]
        done = subprocess.run(cmd, env=self._env(), capture_output=True, text=True, timeout=300)
        return done.returncode, done.stdout + done.stderr

    def _bundled_dir(self, name):
        return os.path.join(os.path.dirname(os.path.dirname(self.soffice)), "share", "extensions", name)

    def _unpack_bundled(self, oxt, name):
        """Bundled extensions are unpacked directories in <install>/share/extensions (unopkg has no --bundled option)."""
        import zipfile
        target_dir = self._bundled_dir(name)
        shutil.rmtree(target_dir, ignore_errors=True)
        zipfile.ZipFile(oxt).extractall(target_dir)

    def install(self):
        shutil.rmtree(self.workdir, ignore_errors=True)
        os.makedirs(self.workdir)
        if self.mode == "bundled":
            self._unpack_bundled(self.extension, NAME)
            return True, "unpacked to " + self._bundled_dir(NAME), "(bundled; discovered by the office on first start)"
        oxt = self.extension
        if self.unprivileged:
            os.chmod(self.workdir, 0o777)
            oxt = os.path.join(self.workdir, os.path.basename(self.extension))
            shutil.copy(self.extension, oxt)
            os.chmod(oxt, 0o644)
        code, out = self.unopkg("add", "--suppress-license", oxt)
        return code == 0, out.strip(), self.unopkg("list")[1]

    def installed_python_dir(self):
        base = os.path.dirname(os.path.dirname(self.soffice))
        patterns = [os.path.join(self.profile, "user", "uno_packages", "cache", "uno_packages", "*", NAME + ".oxt", "python"),
                    os.path.join(base, "share", "extensions", NAME, "python")]
        hits = [h for p in patterns for h in glob.glob(p)]
        return hits[0] if hits else None

    def _log(self):
        """Office stderr goes to $HST_LO_LOG when set (debugging), otherwise it is discarded."""
        path = os.environ.get("HST_LO_LOG")
        return open(path, "w") if path else subprocess.DEVNULL

    def start(self):
        args = [self.soffice, "-env:UserInstallation=" + self.profile_url, "--norestore", "--nologo", "--nodefault",
                "--accept=socket,host=127.0.0.1,port=%d;urp;" % self.port]
        if not self.display:
            args.insert(1, "--headless")
        self.proc = subprocess.Popen(args, env=self._env(), stdout=subprocess.DEVNULL, stderr=self._log(), start_new_session=True)
        local = uno.getComponentContext()
        resolver = local.ServiceManager.createInstanceWithContext("com.sun.star.bridge.UnoUrlResolver", local)
        last = None
        for _ in range(180):
            try:
                self.ctx = resolver.resolve("uno:socket,host=127.0.0.1,port=%d;urp;StarOffice.ComponentContext" % self.port)
                self.desktop = self.ctx.ServiceManager.createInstanceWithContext("com.sun.star.frame.Desktop", self.ctx)
                return
            except Exception as exc:  # noqa: BLE001 - retry until the office accepts connections
                last = exc
                time.sleep(0.5)
        self.stop()
        raise RuntimeError("cannot connect to soffice: %r" % last)

    def new_doc(self, kind):
        return self.desktop.loadComponentFromURL("private:factory/" + kind, "_blank", 0, props(Hidden=True))

    def open_doc(self, path):
        return self.desktop.loadComponentFromURL(uno.systemPathToFileUrl(path), "_blank", 0, props(Hidden=True))

    def deployed_identifiers(self):
        """Identifiers of deployed extensions as the running office sees them (all repositories)."""
        manager = self.ctx.getValueByName("/singletons/com.sun.star.deployment.ExtensionManager")
        found = []
        for repo in ("user", "shared", "bundled"):
            found += [(repo, e.getIdentifier().Value) for e in manager.getDeployedExtensions(repo, None, None)]
        return found

    def cleanup(self):
        if self.unprivileged:
            shutil.rmtree(self.workdir, ignore_errors=True)

    def uninstall_bundled(self):
        if self.mode == "bundled":
            for name in (NAME, "hst-test-probe"):
                shutil.rmtree(self._bundled_dir(name), ignore_errors=True)
            return not os.path.exists(self._bundled_dir(NAME))
        return True

    def build_probe_oxt(self, directory):
        """Zip the test-only probe component into an .oxt (kept out of the product package)."""
        import zipfile
        here = os.path.dirname(os.path.abspath(__file__))
        path = os.path.join(directory, "hst-test-probe.oxt")
        manifest = ('<?xml version="1.0" encoding="UTF-8"?><manifest:manifest xmlns:manifest="http://openoffice.org/2001/manifest">'
                    '<manifest:file-entry manifest:full-path="python/hst_probe_component.py" '
                    'manifest:media-type="application/vnd.sun.star.uno-component;type=Python"/></manifest:manifest>')
        description = ('<?xml version="1.0" encoding="UTF-8"?><description xmlns="http://openoffice.org/extensions/description/2006">'
                       '<identifier value="org.hst.test.probe"/><version value="0.0.1"/></description>')
        with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as z:
            z.writestr("META-INF/manifest.xml", manifest)
            z.writestr("description.xml", description)
            for name in ("hst_probe_component.py", "hst_probe_macro.py"):
                z.write(os.path.join(here, name), "python/" + name)
        return path

    def install_probe(self):
        oxt = self.build_probe_oxt(self.workdir)
        if self.mode == "bundled":
            self._unpack_bundled(oxt, "hst-test-probe")
            return True, "unpacked"
        if self.unprivileged:
            os.chmod(oxt, 0o644)
        code, out = self.unopkg("add", "--suppress-license", oxt)
        return code == 0, out.strip()

    def macro(self, name, *args):
        """Run hst_probe_macro.<name>(*args) inside the office process; returns its (JSON) string result."""
        probe = self.ctx.ServiceManager.createInstanceWithContext("org.hst.test.Probe", self.ctx)
        from com.sun.star.beans import NamedValue
        return probe.execute((NamedValue("name", name), NamedValue("args", tuple(args))))

    def version(self):
        provider = self.ctx.ServiceManager.createInstanceWithContext("com.sun.star.configuration.ConfigurationProvider", self.ctx)
        node = provider.createInstanceWithArguments("com.sun.star.configuration.ConfigurationAccess", props(nodepath="/org.openoffice.Setup/Product"))
        return "%s %s" % (node.getByName("ooName"), node.getByName("ooSetupVersion"))

    def stop(self):
        if self.proc is None:
            return
        try:
            self.desktop.terminate()
        except Exception:  # noqa: BLE001 - fall back to signals below
            pass
        try:
            self.proc.wait(20)
        except subprocess.TimeoutExpired:
            pass
        for sig in (signal.SIGTERM, signal.SIGKILL):
            try:
                os.killpg(self.proc.pid, sig)
            except ProcessLookupError:
                break
            time.sleep(1)
        self.proc = None
