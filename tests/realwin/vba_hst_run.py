# SPDX-License-Identifier: AGPL-3.0-only
"""Run the VBA comparison corpus in HST Office through UNO; the HST counterpart of vba-reference-run.ps1.

Run with the office's bundled interpreter (program\\python.exe), from any session: the office runs headless
with a private profile under the output folder, so the user's HST profile and settings are not touched.
Every file is loaded from a fresh copy with MacroExecutionMode ALWAYS_EXECUTE_NO_WARN (a per-load argument,
not a setting); each case function is called through the document's script provider.

  python.exe vba_hst_run.py --install "C:\\Program Files\\HSTOffice" --corpus DIR --out FILE.json [--label TEXT]
"""
import argparse
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import threading
import time

PIPE = "hstvbacompare"
ALWAYS_EXECUTE_NO_WARN = 4


def call_with_timeout(func, timeout):
    """(state, value) with state done/raised/timeout: UNO calls cannot be interrupted, so they run on a thread."""
    box = {}

    def work():
        try:
            box["value"] = func()
        except BaseException as error:  # noqa: BLE001 - handed to the caller
            box["error"] = error

    thread = threading.Thread(target=work, daemon=True)
    thread.start()
    thread.join(timeout)
    if thread.is_alive():
        return "timeout", None
    return ("raised", box["error"]) if "error" in box else ("done", box.get("value"))


def pv(name, value):
    import uno
    prop = uno.createUnoStruct("com.sun.star.beans.PropertyValue")
    prop.Name, prop.Value = name, value
    return prop


class Office:
    def __init__(self, install, profile, visible=False):
        self.binary = Path(install) / "program" / "soffice.bin"
        self.args = [f"-env:UserInstallation={Path(profile).as_uri()}", "--norestore", "--nologo", "--nodefault",
                     "--nolockcheck"] + ([] if visible else ["--headless"])
        self.visible = visible
        self.proc = self.desktop = None

    def start(self):
        for _ in range(3):  # a fresh profile asks for one restart (exit 81) before it is usable
            done = subprocess.run([str(self.binary), "--terminate_after_init"] + self.args, timeout=300, check=False)
            if done.returncode == 0:
                break
        self.proc = subprocess.Popen([str(self.binary)] + self.args + [f"--accept=pipe,name={PIPE};urp;"])
        import uno
        local = uno.getComponentContext()
        resolver = local.ServiceManager.createInstanceWithContext("com.sun.star.bridge.UnoUrlResolver", local)
        deadline = time.time() + 120
        while True:
            try:
                ctx = resolver.resolve(f"uno:pipe,name={PIPE};urp;StarOffice.ComponentContext")
                break
            except Exception:  # noqa: BLE001 - not listening yet
                if self.proc.poll() == 81:  # the office asks for one restart right after a fresh profile
                    self.proc = subprocess.Popen([str(self.binary)] + self.args + [f"--accept=pipe,name={PIPE};urp;"])
                elif time.time() > deadline or self.proc.poll() is not None:
                    raise RuntimeError(f"office did not start, exit {self.proc.poll()}")
                time.sleep(0.5)
        self.desktop = ctx.ServiceManager.createInstanceWithContext("com.sun.star.frame.Desktop", ctx)

    def alive(self):
        return self.proc is not None and self.proc.poll() is None

    def kill(self):
        if self.proc and self.proc.poll() is None:
            subprocess.run(["taskkill", "/PID", str(self.proc.pid), "/T", "/F"], capture_output=True, check=False)
            try:
                self.proc.wait(timeout=20)
            except subprocess.TimeoutExpired:
                pass
        self.proc = self.desktop = None

    def restart(self):
        self.kill()
        self.start()


def library_with(doc, module):
    libraries = doc.BasicLibraries
    for name in libraries.getElementNames():
        libraries.loadLibrary(name)
        if libraries.getByName(name).hasByName(module):
            return name
    raise RuntimeError(f"no Basic library holds module {module}; libraries: {list(libraries.getElementNames())}")


def run_file(office, entry, source, work, timeout):  # noqa: C901 - one linear sequence of guarded steps
    row = dict(file=entry["file"], host=entry["host"], status="not-run", functions={})
    copy = work / entry["file"]
    shutil.copyfile(source, copy)
    import uno
    for attempt in range(2):  # a visible office can refuse the very first load while its start-up is still running
        state, doc = call_with_timeout(lambda: office.desktop.loadComponentFromURL(
            uno.systemPathToFileUrl(str(copy)), "_blank", 0, (pv("MacroExecutionMode", ALWAYS_EXECUTE_NO_WARN), pv("Hidden", not office.visible))), 120)
        if state != "raised" or attempt:
            break
        row["first_load"] = str(doc)[:200]
        time.sleep(5)
    if state != "done" or doc is None:
        row.update(status="load-" + state, error=str(doc)[:300])
        office.restart()
        return row
    row["status"] = "opened"
    try:
        library = library_with(doc, "Cases")
        row["vba_mode"] = bool(doc.BasicLibraries.VBACompatibilityMode)
    except Exception as error:  # noqa: BLE001 - recorded, the file still counts
        row.update(status="no-library", error=str(error)[:300])
        call_with_timeout(lambda: doc.close(True), 30)
        return row
    for name in entry["functions"]:
        script = f"vnd.sun.star.script:{library}.Cases.{name}?language=Basic&location=document"
        state, value = call_with_timeout(lambda: doc.getScriptProvider().getScript(script).invoke((), (), ())[0], timeout)
        if state == "done":
            row["functions"][name] = dict(status="ok" if value is not None else "error",
                                          value="" if value is None else str(value))
        elif state == "raised":
            row["functions"][name] = dict(status="error", value=f"{type(value).__name__}: {getattr(value, 'Message', value)}"[:600])
        else:
            row["functions"][name] = dict(status="error", value=f"timeout after {timeout}s")
            row["status"] = "timeout"
            office.restart()
            return row
        if not office.alive():
            row["status"] = "office-died"
            office.restart()
            return row
    state, _ = call_with_timeout(lambda: doc.close(True), 30)
    row["status"] = "done" if state == "done" else "close-" + state
    if state != "done":
        office.restart()
    return row


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--install", required=True)
    parser.add_argument("--corpus", required=True)
    parser.add_argument("--out", required=True)
    parser.add_argument("--label", default="")
    parser.add_argument("--timeout", type=int, default=90)
    parser.add_argument("--visible", action="store_true", help="normal UI in the user's session (interactive-task.ps1)")
    args = parser.parse_args()
    corpus, out = Path(args.corpus), Path(args.out)
    work = out.parent / (out.stem + "-work")
    shutil.rmtree(work, ignore_errors=True)
    work.mkdir(parents=True)
    manifest = json.loads((corpus / "manifest.json").read_text(encoding="utf-8"))
    report = dict(suite="hst", label=args.label, computer=os.environ.get("COMPUTERNAME"), started=time.strftime("%Y-%m-%dT%H:%M:%S"), files=[])
    version = Path(args.install) / "program" / "version.ini"
    if version.exists():
        report["version_ini"] = [line for line in version.read_text(errors="replace").splitlines() if "=" in line][:12]

    def save():
        out.write_text(json.dumps(report, indent=1, ensure_ascii=False), encoding="utf-8")

    office = Office(args.install, work / "profile", args.visible)
    report["mode"] = "visible" if args.visible else "headless"
    try:
        office.start()
        for entry in manifest:
            source = corpus / entry["file"]
            if not source.exists():
                report["files"].append(dict(file=entry["file"], host=entry["host"], status="missing", functions={}))
                continue
            try:
                report["files"].append(run_file(office, entry, source, work, args.timeout))
            except Exception as error:  # noqa: BLE001 - one file must not end the run
                report["files"].append(dict(file=entry["file"], host=entry["host"], status="harness-error", error=repr(error)[:400], functions={}))
                office.restart()
            save()
    finally:
        office.kill()
        report["finished"] = time.strftime("%Y-%m-%dT%H:%M:%S")
        save()
    return 0


if __name__ == "__main__":
    sys.exit(main())
