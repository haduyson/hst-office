# SPDX-License-Identifier: AGPL-3.0-only
"""Office plumbing of tests/runtime/check-update-policy.py (also used by check-python-no-bytecode.py): start and stop
a headless office with a fresh profile and a UNO socket, read a configuration node, query a command's state."""
import importlib.util
import os
import shutil
import subprocess
import sys
import time

CORE = "/org.openoffice.Office.HSTUpdate"
READONLY = 16
BUILD_USER = os.environ.get("HST_BUILD_USER", "hstbuild")


def load_file(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def load_extension_module(extension, name):
    """hst_office.<name> of the extension directory `extension`, imported as a package module: the modules use
    relative imports (from . import diag_log), which a module loaded by file path cannot resolve. The installed
    extension is read-only for this probe: no bytecode cache is written next to it."""
    import importlib
    python = os.path.join(extension, "python")
    loaded = sys.modules.get("hst_office")
    if loaded is not None and os.path.dirname(os.path.dirname(os.path.abspath(loaded.__file__))) != python:
        raise RuntimeError("hst_office is already imported from %s" % loaded.__file__)
    keep = sys.dont_write_bytecode
    sys.dont_write_bytecode = True
    sys.path.insert(0, python)
    try:
        return importlib.import_module("hst_office." + name)
    finally:
        sys.path.remove(python)
        sys.dont_write_bytecode = keep




def extension_dir(soffice):
    """The bundled HST extension next to `soffice` (Linux/Windows program/, macOS Contents/MacOS/)."""
    base = os.path.dirname(os.path.dirname(os.path.abspath(soffice)))
    for path in (os.path.join(base, "share", "extensions", "hst-vietnamese-tools"),
                 os.path.join(base, "Resources", "extensions", "hst-vietnamese-tools")):
        if os.path.isdir(path):
            return path
    return None


def start_office(soffice, work, port):
    import uno
    profile = os.path.join(work, "profile")
    shutil.rmtree(profile, ignore_errors=True)
    os.makedirs(os.path.join(work, "home"), exist_ok=True)
    args = [soffice, "--headless", "--norestore", "--nologo", "--nodefault", "--nolockcheck",
            "-env:UserInstallation=" + uno.systemPathToFileUrl(profile), "--accept=socket,host=127.0.0.1,port=%d;urp;" % port]
    if sys.platform.startswith("linux") and os.geteuid() == 0:  # never run the office as root
        subprocess.run(["chown", "-R", BUILD_USER, work], check=True)
        args = ["runuser", "-u", BUILD_USER, "--", "env", "HOME=" + os.path.join(work, "home")] + args
    env = {k: v for k, v in os.environ.items() if k not in ("URE_BOOTSTRAP", "PYTHONPATH", "PYTHONDONTWRITEBYTECODE",
                                                        "PYTHONPYCACHEPREFIX")}  # this probe's, not the office's
    for _ in range(3):  # a fresh profile makes the office restart itself once: initialise it first
        if subprocess.run(args[:-1] + ["--terminate_after_init"], env=env, timeout=300, check=False,
                          stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL).returncode == 0:
            break
    proc = subprocess.Popen(args, stdout=open(os.path.join(work, "soffice.out"), "w"),
                            stderr=open(os.path.join(work, "soffice.err"), "w"), env=env)
    local = uno.getComponentContext()
    resolver = local.ServiceManager.createInstanceWithContext("com.sun.star.bridge.UnoUrlResolver", local)
    for _ in range(150):
        try:
            return proc, resolver.resolve("uno:socket,host=127.0.0.1,port=%d;urp;StarOffice.ComponentContext" % port)
        except Exception:  # noqa: BLE001 - not listening yet (a fresh profile restarts once)
            time.sleep(1)
    proc.kill()
    raise RuntimeError("UNO socket did not open in 150 s")


def stop_office(proc, ctx, work):
    try:
        ctx.ServiceManager.createInstanceWithContext("com.sun.star.frame.Desktop", ctx).terminate()
    except Exception:  # noqa: BLE001 - the bridge closes while the office quits
        pass
    try:
        proc.wait(60)
    except subprocess.TimeoutExpired:
        proc.kill()
    if sys.platform.startswith("linux"):  # only this run's office: matched by its own profile path
        subprocess.run(["pkill", "-f", "UserInstallation=file://" + os.path.join(work, "profile")], check=False)


def core_node(ctx, path=CORE):
    import uno
    arg = uno.createUnoStruct("com.sun.star.beans.PropertyValue")
    arg.Name, arg.Value = "nodepath", path
    provider = ctx.ServiceManager.createInstanceWithContext("com.sun.star.configuration.ConfigurationProvider", ctx)
    return provider.createInstanceWithArguments("com.sun.star.configuration.ConfigurationUpdateAccess", (arg,))


def command_enabled(ctx, frame, command):
    """IsEnabled that the HST protocol handler reports for `command` (what the menu and the ribbon show)."""
    import uno
    import unohelper
    from com.sun.star.frame import XStatusListener
    states = []

    class Listener(unohelper.Base, XStatusListener):
        def statusChanged(self, event):
            states.append(event.IsEnabled)

        def disposing(self, event):
            pass

    url = uno.createUnoStruct("com.sun.star.util.URL")
    url.Complete = command
    _ok, url = ctx.ServiceManager.createInstanceWithContext("com.sun.star.util.URLTransformer", ctx).parseStrict(url)
    dispatch = frame.queryDispatch(url, "", 0)
    if dispatch is None:
        return None
    dispatch.addStatusListener(Listener(), url)
    time.sleep(1)
    return states[-1] if states else None
