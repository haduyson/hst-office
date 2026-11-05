# SPDX-License-Identifier: AGPL-3.0-only
"""Part of check-vba.py: the headless office, results and helpers shared by the VBA checks."""
import os
import shutil
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(ROOT, "extensions/hst-vietnamese-tools/python"))
from hst_office import vba, vba_template  # noqa: E402  (the code behind "Macro VBA")

BUILD_USER = os.environ.get("HST_BUILD_USER", "hstbuild")
FIXTURES = os.path.join(ROOT, "upstream/libreoffice")
ROWS = []


def record(group, name, ok, detail="", status="ok"):
    """status ok: a failure fails the run; limited: known gap, a pass is flagged."""
    ROWS.append(dict(group=group, name=name, passed=bool(ok), status=status, detail=str(detail)[:300]))
    tag = "PASS" if ok else ("FAIL" if status == "ok" else "LIMIT")
    if ok and status == "limited":
        tag = "PASS(limited case now passes: update vba_cases.py/help)"
    print(f"{tag:5} [{group}] {name}" + (f"  ({detail})" if detail and not ok else ""), flush=True)


def reexec_as_build_user(out):
    os.makedirs(out, exist_ok=True)
    subprocess.run(["chown", "-R", BUILD_USER, out], check=True)
    os.execvp("runuser", ["runuser", "-u", BUILD_USER, "--", sys.executable] + sys.argv)


def pv(name, value):
    from com.sun.star.beans import PropertyValue
    prop = PropertyValue()
    prop.Name, prop.Value = name, value
    return prop


class Office:
    def __init__(self, program, out, port):
        self.program, self.out, self.port = program, out, port
        self.profile = os.path.join(out, f"profile-{port}")

    def start(self):
        shutil.rmtree(self.profile, ignore_errors=True)
        env = {k: v for k, v in os.environ.items() if k != "URE_BOOTSTRAP"}
        env.update(HOME=os.path.join(self.out, "home"), LANG="C.UTF-8", LC_ALL="C.UTF-8")
        os.makedirs(env["HOME"], exist_ok=True)
        args = [f"-env:UserInstallation=file://{self.profile}", "--norestore", "--headless", "--nologo"]
        for _ in range(3):  # exit 81 = restart requested while the fresh profile is created
            if subprocess.run([os.path.join(self.program, "soffice.bin"), "--terminate_after_init"] + args,
                              env=env, timeout=180, check=False).returncode == 0:
                break
        self.proc = subprocess.Popen([os.path.join(self.program, "soffice")] + args
                                     + [f"--accept=socket,host=127.0.0.1,port={self.port};urp;"], env=env)
        import uno
        local = uno.getComponentContext()
        deadline = time.time() + 120
        while True:
            try:
                resolver = local.ServiceManager.createInstanceWithContext("com.sun.star.bridge.UnoUrlResolver", local)
                self.ctx = resolver.resolve(f"uno:socket,host=127.0.0.1,port={self.port};urp;StarOffice.ComponentContext")
                break
            except Exception:  # noqa: BLE001 - NoConnectException until soffice listens
                if time.time() > deadline:
                    raise
                time.sleep(1)
        time.sleep(2)
        self.desktop = self.ctx.ServiceManager.createInstanceWithContext("com.sun.star.frame.Desktop", self.ctx)
        return self

    def stop(self):
        try:
            self.desktop.terminate()
        except Exception:  # noqa: BLE001 - the bridge drops while soffice exits
            pass
        try:
            self.proc.wait(timeout=30)
        except subprocess.TimeoutExpired:
            self.proc.terminate()
            self.proc.wait(timeout=20)

    def new(self, kind, hidden=False):
        if hidden:
            return self.desktop.loadComponentFromURL(f"private:factory/{kind}", "_blank", 0,
                                                     (pv("Hidden", True), pv("MacroExecutionMode", 3)))
        # Not Hidden: VBA objects such as Selection or End(xlDown) need the document view.
        # MacroExecutionMode USE_CONFIG (3) as for File > New; the API default never runs cell UDFs.
        return self.desktop.loadComponentFromURL(f"private:factory/{kind}", "_blank", 0, (pv("MacroExecutionMode", 3),))

    def load(self, path, run_macros=True):
        import uno
        if path.startswith(FIXTURES + os.sep):
            # Work on a copy: a lock file left next to a fixture by an ended office blocks loading it.
            self.copies = getattr(self, "copies", 0) + 1  # unique name: an ended office may leave a lock
            copy = os.path.join(self.out, "fixtures", f"{self.port}-{self.copies}-{os.path.basename(path)}")
            os.makedirs(os.path.dirname(copy), exist_ok=True)
            shutil.copyfile(path, copy)
            path = copy
        # ALWAYS_EXECUTE_NO_WARN = 4: the test opens its own files; users get the security prompt (config check).
        return self.desktop.loadComponentFromURL(uno.systemPathToFileUrl(path), "_blank", 0,
                                                 (pv("MacroExecutionMode", 4 if run_macros else 0),))


def config_value(ctx, path):
    node, key = path.rsplit("/", 1)
    provider = ctx.ServiceManager.createInstanceWithContext("com.sun.star.configuration.ConfigurationProvider", ctx)
    return provider.createInstanceWithArguments("com.sun.star.configuration.ConfigurationAccess", (pv("nodepath", node),)).getByName(key)


def prepare(doc, kind):
    """Prepare the document exactly as "Macro VBA" does; return its VBA library."""
    library, _module, _code, _created = vba.prepare_document(doc, "calc" if kind == "scalc" else "writer")
    return library, doc.BasicLibraries.getByName(library)


def run(doc, library, module, function):
    script = doc.getScriptProvider().getScript(
        f"vnd.sun.star.script:{library}.{module}.{function}?language=Basic&location=document")
    return script.invoke((), (), ())[0]


def case_module(case):
    body = "\n".join("  " + line for line in case["body"].splitlines())
    return (f"{vba_template.OPTION_LINE}\nFunction T()\n  Dim r As Variant\n  On Error GoTo Fail\n{body}\n  T = CStr(r)\n"
            f"  Exit Function\nFail:\n  T = \"ERR \" & Err.Number & \": \" & Err.Description\nEnd Function\n"
            + case.get("extra", "") + "\n")


def compiles(office, kind, code):
    """A compile error opens an error box, which aborts a headless office when the document has a
    view: compile first in a hidden document, where the failed call just returns nothing."""
    doc = office.new(kind, hidden=True)
    try:
        name, library = prepare(doc, kind)
        vba.add_module(library, "HstCompile", code.replace("Function T()", "Function T()\n  T = \"c\"\n  Exit Function", 1))
        return run(doc, name, "HstCompile", "T") is not None
    finally:
        doc.close(True)


def module_code(doc, library, module):
    libs = doc.BasicLibraries
    if not libs.hasByName(library):
        return None
    libs.loadLibrary(library)
    lib = libs.getByName(library)
    return lib.getByName(module) if lib.hasByName(module) else None
