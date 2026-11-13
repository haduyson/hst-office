# SPDX-License-Identifier: AGPL-3.0-only
"""Prove the in-document representation of HST citations on a real build.

Usage: python3 tests/runtime/check-citations-fieldmarks.py [--instdir DIR] [--out DIR] [--skip-perf]

A citation is a text fieldmark (type UNHANDLED) with the code "ADDIN HST_CITATION {json}" and
the formatted citation as its result; the bibliography is one fieldmark "ADDIN HST_BIBLIOGRAPHY"
over several paragraphs. Builds a sample document with the real commands (.uno:TextFormField,
.uno:TextFormFields), checks formatting, order, bulk update with one Undo step, tracked changes,
editing and Undo behaviour, saves .docx and .odt, reloads both, reads the .docx with the standard
library as another word processor would, and times a thesis-sized document. Writes
evidence.json (and the saved files) to --out; exit 1 on any failure.
"""
import argparse
import json
import os
import shutil
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, HERE)


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


def run_checks(ctx, out, skip_perf):
    import uno
    import citations_fieldmark_checks as checks
    import citations_fieldmark_edits as edits
    import citations_fieldmark_sample as sample
    from citations_fieldmark_uno import Session, prop
    rec = Recorder()
    desktop = ctx.ServiceManager.createInstanceWithContext("com.sun.star.frame.Desktop", ctx)
    hidden = (prop("Hidden", True),)
    doc = desktop.loadComponentFromURL("private:factory/swriter", "_blank", 0, hidden)
    saved, reference = {}, {}
    try:
        session = Session(ctx, doc)
        sample.build(session)
        rec.stage("format", checks.check_formatting, rec, doc)
        rec.stage("bibliography", checks.check_bibliography, rec, doc, True)
        rec.stage("order", checks.check_order, rec, doc)
        rec.stage("update", checks.check_bulk_update, rec, session)
        rec.stage("single-update", checks.check_single_update, rec, session)
        rec.stage("tracked-changes", checks.check_tracked_changes, rec, session)
        reference = checks.snapshot(doc)
        rec.check("saved-codes-are-the-inserted-ones", {c: v[0] for c, v in reference.items()}
                  == sample.expected_codes(), sorted(reference))
        for ext, filt in (("docx", "MS Word 2007 XML"), ("odt", "writer8")):
            saved[ext] = os.path.join(out, f"citations.{ext}")
            doc.storeToURL(uno.systemPathToFileUrl(saved[ext]), (prop("FilterName", filt),))
    finally:
        doc.close(True)
    for ext, path in saved.items():
        reopened = desktop.loadComponentFromURL(uno.systemPathToFileUrl(path), "_blank", 0, hidden)
        try:
            rec.stage(f"reload-{ext}", checks.check_reloaded, rec, reopened, f"reload-{ext}", reference)
            rec.stage(f"reload-{ext}-order", checks.check_order, rec.prefixed(f"reload-{ext}"), reopened)
        finally:
            reopened.close(True)
    rec.stage("docx-xml", checks.check_docx_reader, rec, saved["docx"], reference)
    edit_doc = desktop.loadComponentFromURL("private:factory/swriter", "_blank", 0, hidden)
    try:
        rec.stage("edit", edits.run, rec, Session(ctx, edit_doc))
    finally:
        edit_doc.close(True)
    if not skip_perf:
        import citations_fieldmark_perf as perf
        rec.stage("perf", perf.run, rec, ctx, desktop, out)
    return rec.results


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--instdir", default=os.path.join(ROOT, "upstream/libreoffice/instdir"))
    parser.add_argument("--out", default=os.path.join(ROOT, "tests/output/citations-fieldmarks"))
    parser.add_argument("--skip-perf", action="store_true", help="skip the 200-page timing document")
    args = parser.parse_args()
    args.out = os.path.abspath(args.out)  # the profile must be an absolute file:// URL
    program = os.path.join(os.path.abspath(args.instdir), "program")
    child_env = {k: v for k, v in os.environ.items() if k != "URE_BOOTSTRAP"}
    if os.path.exists(os.path.join(program, "uno.py")):  # the build's own Python-UNO bridge
        sys.path.insert(0, program)
        os.environ["URE_BOOTSTRAP"] = "vnd.sun.star.pathname:" + os.path.join(program, "fundamentalrc")
    shutil.rmtree(args.out, ignore_errors=True)
    profile = os.path.join(args.out, "profile")
    os.makedirs(profile)
    user = "-env:UserInstallation=file://" + profile
    for _ in range(3):  # exit code 81 = restart requested while the fresh profile is created
        warm = subprocess.run([os.path.join(program, "soffice.bin"), "--headless", "--norestore",
                               "--terminate_after_init", user], env=child_env, timeout=180, check=False)
        if warm.returncode == 0:
            break
    pipe = f"hstcitations{os.getpid()}"
    procs = []

    def launch():
        procs.append(subprocess.Popen([os.path.join(program, "soffice.bin"), "--headless", "--norestore",
                                       "--nologo", user, f"--accept=pipe,name={pipe};urp;"], env=child_env))
        return procs[-1]

    try:
        ctx, proc = connect(pipe, launch)
        results = run_checks(ctx, args.out, args.skip_perf)
    finally:
        proc = procs[-1]
        proc.terminate()
        try:
            proc.wait(timeout=30)
        except subprocess.TimeoutExpired:
            proc.kill()
    failed = sum(r["status"] == "FAIL" for r in results)
    with open(os.path.join(args.out, "evidence.json"), "w", encoding="utf-8") as handle:
        json.dump({"instdir": args.instdir, "failed": failed, "results": results}, handle,
                  indent=2, ensure_ascii=False, default=str)
    print(f"{len(results)} results, {failed} failed")
    return 1 if failed or not results else 0


if __name__ == "__main__":
    sys.exit(main())
