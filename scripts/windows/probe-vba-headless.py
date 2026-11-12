# SPDX-License-Identifier: AGPL-3.0-only
"""Run VBA macros in an installed HST Office, headless, with the office's own Python (program\\python.exe).

    python.exe probe-vba-headless.py --soffice <program\\soffice.exe> --out <dir>

Sheets and Writer: a new hidden document gets a VBA-mode library (as the "Macro VBA" command makes it) with a module
that begins "Option VBASupport 1" and uses the Excel/Word object model (Range, Worksheets, ActiveDocument). Each is run,
saved as .xlsm/.docm, closed, loaded again with macros allowed and run again, so the VBA project import and export
are covered too. Prints one "ok:"/"FAIL:" line per check; exit 1 on any failure. The office runs on a fresh,
temporary user profile."""
import argparse
import os
import shutil
import subprocess
import sys
import tempfile
import time

import uno
from com.sun.star.beans import PropertyValue

PIPE = "hst_vba_probe"
NORMAL_MODULE = 1  # com.sun.star.script.ModuleType.NORMAL
CASES = (  # (factory, filter, extension, setup text, VBA function body, expected result)
    ("scalc", "Calc MS Excel 2007 VBA XML", "xlsm", None,
     'Range("A1").Value = 6\n  Range("A2").Formula = "=A1*7"\n  Worksheets(1).Name = "Data"\n'
     '  T = CStr(Range("A2").Value) & "|" & ActiveWorkbook.Worksheets(1).Name', "42|Data"),
    ("swriter", "MS Word 2007 XML VBA", "docm", "Xin chao HST",
     'T = Left(ActiveDocument.Content.Text, 8) & "|" & ActiveDocument.Paragraphs.Count', "Xin chao|1"),
)


def pv(name, value):
    prop = PropertyValue()
    prop.Name, prop.Value = name, value
    return prop


def connect(soffice, profile):
    args = [soffice, "--headless", "--invisible", "--norestore", "--nologo", "--nodefault",
            "-env:UserInstallation=" + uno.systemPathToFileUrl(profile), f"--accept=pipe,name={PIPE};urp;"]
    process = subprocess.Popen(args)
    resolver = uno.getComponentContext().ServiceManager.createInstanceWithContext(
        "com.sun.star.bridge.UnoUrlResolver", uno.getComponentContext())
    deadline = time.monotonic() + 180
    while True:
        try:
            ctx = resolver.resolve(f"uno:pipe,name={PIPE};urp;StarOffice.ComponentContext")
            return process, ctx.ServiceManager.createInstanceWithContext("com.sun.star.frame.Desktop", ctx)
        except Exception:  # noqa: BLE001 - NoConnectException until the office listens
            if process.poll() is not None or time.monotonic() > deadline:
                raise RuntimeError(f"office did not start (exit {process.poll()})")
            time.sleep(2)


def add_vba_module(doc, body):
    libs = doc.BasicLibraries
    if not libs.hasByName("VBAProject"):
        libs.createLibrary("VBAProject")
    libs.VBACompatibilityMode = True
    libs.ProjectName = "VBAProject"
    library = libs.getByName("VBAProject")
    info = uno.createUnoStruct("com.sun.star.script.ModuleInfo")
    info.ModuleType = NORMAL_MODULE
    library.insertModuleInfo("HstProbe", info)
    library.insertByName("HstProbe", f"Option VBASupport 1\nFunction T()\n  {body}\nEnd Function\n")


def run(doc):
    script = doc.getScriptProvider().getScript(
        "vnd.sun.star.script:VBAProject.HstProbe.T?language=Basic&location=document")
    return str(script.invoke((), (), ())[0])


def check(label, got, want, failures):
    ok = got == want
    print(f"{'ok' if ok else 'FAIL'}: {label}: got {got!r}, want {want!r}", flush=True)
    if not ok:
        failures.append(label)


def probe(desktop, out, failures):
    for factory, filter_name, extension, text, body, want in CASES:
        doc = desktop.loadComponentFromURL(f"private:factory/{factory}", "_blank", 0,
                                           (pv("Hidden", True), pv("MacroExecutionMode", 4)))
        try:
            if text:
                doc.Text.setString(text)
            add_vba_module(doc, body)
            check(f"{factory} VBA macro in a new document", run(doc), want, failures)
            url = uno.systemPathToFileUrl(os.path.join(out, f"vba-probe.{extension}"))
            doc.storeToURL(url, (pv("FilterName", filter_name),))
        finally:
            doc.close(True)
        doc = desktop.loadComponentFromURL(url, "_blank", 0, (pv("Hidden", True), pv("MacroExecutionMode", 4)))
        try:
            check(f"{factory} VBA macro after saving and loading .{extension}", run(doc), want, failures)
        finally:
            doc.close(True)


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--soffice", required=True)
    parser.add_argument("--out", required=True)
    args = parser.parse_args()
    if not os.path.isfile(args.soffice):
        print(f"FAIL: no office at {args.soffice}")
        return 1
    out = os.path.abspath(args.out)
    os.makedirs(out, exist_ok=True)
    failures = []
    profile = tempfile.mkdtemp(prefix="hst-vba-profile-")
    process, desktop = connect(args.soffice, profile)
    try:
        probe(desktop, out, failures)
    except Exception as error:  # noqa: BLE001 - a UNO error ends the probe as a failure, not a traceback only
        print(f"FAIL: {type(error).__name__}: {getattr(error, 'Message', error)}")
        failures.append("exception")
    finally:
        try:
            desktop.terminate()
        except Exception:  # noqa: BLE001 - the bridge closes as the office exits
            pass
        try:
            process.wait(timeout=60)
        except subprocess.TimeoutExpired:
            process.kill()
        shutil.rmtree(profile, ignore_errors=True)
    print(f"VBA headless probe: {len(failures)} failures.")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
