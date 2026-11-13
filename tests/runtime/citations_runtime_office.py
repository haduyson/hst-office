# SPDX-License-Identifier: AGPL-3.0-only
"""Shared by the citation runtime checks: a result recorder, and a headless office on a fresh profile reached over
a UNO pipe (check-citations-fieldmarks.py, check-citations-commands.py)."""
import json
import os
import pathlib
import shutil
import subprocess
import sys
import time


class Recorder:
    def __init__(self, prefix=""):
        self.prefix, self.results = prefix, []

    def check(self, name, ok, detail):
        self.results.append({"check": self.prefix + name, "status": "PASS" if ok else "FAIL",
                             "detail": detail})
        print(f"{'PASS' if ok else 'FAIL'}  {self.prefix}{name}  {json.dumps(detail, ensure_ascii=False, default=str)[:160]}")

    def info(self, name, detail):
        self.results.append({"check": self.prefix + name, "status": "INFO", "detail": detail})
        print(f"INFO  {self.prefix}{name}  {json.dumps(detail, ensure_ascii=False, default=str)[:160]}")

    def stage(self, name, fn, *args):
        """Run one group of checks; an exception fails that group instead of the whole run."""
        try:
            return fn(*args)
        except Exception as exc:  # report and go on: later groups use fresh documents
            self.check(f"{name}-error", False, f"{type(exc).__name__}: {exc}")
            return None

    def prefixed(self, label):
        child = Recorder(f"{label}-")
        child.results = self.results
        return child


def connect(pipe, launch, timeout=120):
    """Connect over the pipe; `launch()` starts soffice and is called again if it exits with
    81 (restart requested), which a fresh profile does once even after the warm-up run."""
    import uno
    local = uno.getComponentContext()
    deadline = time.time() + timeout
    proc = launch()
    time.sleep(6)  # calls made before startup settles get disposed
    while True:
        if proc.poll() == 81:
            proc = launch()
            time.sleep(6)
        try:
            resolver = local.ServiceManager.createInstanceWithContext("com.sun.star.bridge.UnoUrlResolver", local)
            return resolver.resolve(f"uno:pipe,name={pipe};urp;StarOffice.ComponentContext"), proc
        except Exception:  # NoConnectException until soffice listens
            if time.time() > deadline:
                raise
            time.sleep(1)


def run_office(instdir, out, run_checks, display=None):
    """Start an office from ``instdir`` with a fresh profile in ``out`` (headless, or with windows on the X
    ``display``), call run_checks(ctx, out) and write out/evidence.json; returns the exit code (1 on any FAIL)."""
    out = os.path.abspath(out)  # the profile must be an absolute file:// URL
    program = os.path.join(os.path.abspath(instdir), "program")
    child_env = {k: v for k, v in os.environ.items() if k != "URE_BOOTSTRAP"}
    if display:
        child_env.update(DISPLAY=display, SAL_USE_VCLPLUGIN="gen")
    headless = [] if display else ["--headless"]
    if os.path.exists(os.path.join(program, "uno.py")):  # the build's own Python-UNO bridge
        sys.path.insert(0, program)
        rc = "fundamental.ini" if os.name == "nt" else "fundamentalrc"
        os.environ["URE_BOOTSTRAP"] = "vnd.sun.star.pathname:" + os.path.join(program, rc)
    shutil.rmtree(out, ignore_errors=True)
    profile = os.path.join(out, "profile")
    os.makedirs(profile)
    user = "-env:UserInstallation=" + pathlib.Path(profile).as_uri()  # file:///D:/... on Windows
    for _ in range(3):  # exit code 81 = restart requested while the fresh profile is created
        warm = subprocess.run([os.path.join(program, "soffice.bin")] + headless + ["--norestore",
                               "--terminate_after_init", user], env=child_env, timeout=180, check=False)
        if warm.returncode == 0:
            break
    pipe = f"hstcitations{os.getpid()}"
    procs = []

    def launch():
        procs.append(subprocess.Popen([os.path.join(program, "soffice.bin")] + headless + ["--norestore",
                                       "--nologo", user, f"--accept=pipe,name={pipe};urp;"], env=child_env))
        return procs[-1]

    results = []
    try:
        ctx, _proc = connect(pipe, launch)
        results = run_checks(ctx, out)
    finally:
        proc = procs[-1]
        proc.terminate()
        try:
            proc.wait(timeout=30)
        except subprocess.TimeoutExpired:
            proc.kill()
    failed = sum(r["status"] == "FAIL" for r in results)
    with open(os.path.join(out, "evidence.json"), "w", encoding="utf-8") as handle:
        json.dump({"instdir": instdir, "failed": failed, "results": results}, handle,
                  indent=2, ensure_ascii=False, default=str)
    print(f"{len(results)} results, {failed} failed")
    return 1 if failed or not results else 0
