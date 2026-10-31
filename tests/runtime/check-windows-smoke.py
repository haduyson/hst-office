#!/usr/bin/env python3
# SPDX-License-Identifier: AGPL-3.0-only
"""Smoke test of the bundled HST Vietnamese tools inside an INSTALLED HST Office (written for Windows CI).

Run with the office's own interpreter so `import uno` works:
    "<install>\\program\\python.exe" tests/runtime/check-windows-smoke.py --install "<install>" --out <dir>

Steps: (1) import every extension module with the office Python and load the shared data files, (2) start the
office with a UNO socket, (3) check the HST protocol handlers are registered, (4) dispatch every HST command
from a thread and record which window opens (a modal dialog is expected for the wizards; it is then closed with
endExecute), (5) check the F1 help root URL resolves to an existing page. Exit status 1 on any FAIL.
Results: <out>/smoke-results.json. Python tracebacks of the extension go to soffice stderr (<out>/soffice.err).
"""
import argparse
import glob
import importlib
import json
import os
import subprocess
import sys
import threading
import time
import traceback

ROWS = []
EN_TITLES = ("Administrative document (ND30)", "Welcome to HST Office", "Import CSV", "Convert legacy Vietnamese text to Unicode")


def record(name, ok, detail=""):
    ROWS.append({"check": name, "status": "PASS" if ok else "FAIL", "detail": str(detail)[:1500]})
    print("%s  %s  %s" % ("PASS" if ok else "FAIL", name, str(detail)[:300]), flush=True)
    return ok


def find_extension(install):
    for path in glob.glob(os.path.join(install, "share", "extensions", "hst-vietnamese-tools")):
        return path
    return None


def import_checks(ext):
    sys.path.insert(0, os.path.join(ext, "python"))
    for module in ("hst_office.data_files", "hst_office.nd30", "hst_office.dialogs", "hst_office.wizard_nd30", "hst_office.actions",
                   "hst_office.dispatch", "hst_office.welcome_job", "hst_office.update_job"):
        try:
            importlib.import_module(module)
            record("import " + module, True)
        except Exception:  # noqa: BLE001
            record("import " + module, False, traceback.format_exc())
    try:
        from hst_office import data_files, nd30
        rules = nd30.rules()
        record("load nd30.json", bool(rules["documentTypes"]), "%d document types" % len(rules["documentTypes"]))
        for code in ("vi", "en"):
            record("load locale " + code, "nd30" in data_files.load_locale(code))
    except Exception:  # noqa: BLE001
        record("load data files", False, traceback.format_exc())


def start_office(program, profile, port, err_path, env):
    import uno
    cmd = [os.path.join(program, "soffice.exe"), "--norestore", "--nologo", "--nodefault", "-env:UserInstallation=" + profile,
           "--accept=socket,host=127.0.0.1,port=%d;urp;" % port]
    proc = subprocess.Popen(cmd, stdout=open(err_path + ".out", "w"), stderr=open(err_path, "w"), env=env)
    local = uno.getComponentContext()
    resolver = local.ServiceManager.createInstanceWithContext("com.sun.star.bridge.UnoUrlResolver", local)
    for _ in range(90):
        try:
            return proc, resolver.resolve("uno:socket,host=127.0.0.1,port=%d;urp;StarOffice.ComponentContext" % port)
        except Exception:  # noqa: BLE001
            if proc.poll() is not None:
                raise RuntimeError("soffice exited with %s before the UNO socket opened" % proc.returncode)
            time.sleep(1)
    raise RuntimeError("UNO socket did not open in 90 s")


def top_windows(toolkit):
    return [toolkit.getTopWindow(i) for i in range(toolkit.getTopWindowCount())]


def window_title(window):
    for getter in (lambda w: w.getTitle(), lambda w: w.getAccessibleContext().getAccessibleName()):
        try:
            value = getter(window)
            if value:
                return value
        except Exception:  # noqa: BLE001
            continue
    return ""


SHOT_DIR = None


def shot(label):
    """Optional full-screen PNG (Windows CI passes --screenshots); never fails the smoke run."""
    if not SHOT_DIR:
        return
    name = "".join(c if c.isalnum() else "_" for c in label)[:40]
    script = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "scripts", "windows", "capture-screenshot.ps1")
    subprocess.run(["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", script, "-Path", os.path.join(SHOT_DIR, "%d-%s.png" % (len(ROWS), name))],
                   timeout=60, check=False)


def run_command(ctx, frame, url_text, expect_dialog):
    """Dispatch in a thread; return (new window titles, thread exception text or '')."""
    import uno
    smgr = ctx.ServiceManager
    toolkit = smgr.createInstanceWithContext("com.sun.star.awt.Toolkit", ctx)
    transformer = smgr.createInstanceWithContext("com.sun.star.util.URLTransformer", ctx)
    url = uno.createUnoStruct("com.sun.star.util.URL")
    url.Complete = url_text
    _, url = transformer.parseStrict(url)
    dispatch = frame.queryDispatch(url, "_self", 0)
    if dispatch is None:
        return None, "queryDispatch returned None: no handler claims " + url_text
    before = {id(w) for w in top_windows(toolkit)}
    state = {"error": ""}

    def work():
        try:
            dispatch.dispatch(url, ())
        except Exception:  # noqa: BLE001
            state["error"] = traceback.format_exc()

    thread = threading.Thread(target=work, daemon=True)
    thread.start()
    titles, deadline = [], time.time() + 30
    while time.time() < deadline and (thread.is_alive() or not titles):
        for window in top_windows(toolkit):
            if id(window) not in before:
                title = window_title(window)
                titles.append(title)
                before.add(id(window))
                time.sleep(1.5)  # let it paint before the screenshot
                shot(title or "window")
                try:
                    window.endExecute()
                except Exception as exc:  # noqa: BLE001
                    state["error"] += "endExecute failed: %s\n" % exc
        if not thread.is_alive():
            break
        time.sleep(0.3)
    thread.join(10)
    if thread.is_alive():
        state["error"] += "dispatch still blocked after 40 s\n"
    return titles, state["error"]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--install", required=True, help="office install root (contains program/)")
    ap.add_argument("--out", required=True)
    ap.add_argument("--port", type=int, default=2106)
    ap.add_argument("--screenshots", help="directory for PNG screenshots of every window that opens")
    args = ap.parse_args()
    install, out = os.path.abspath(args.install), os.path.abspath(args.out)
    program = os.path.join(install, "program")
    os.makedirs(out, exist_ok=True)
    global SHOT_DIR
    SHOT_DIR = os.path.abspath(args.screenshots) if args.screenshots else None
    if SHOT_DIR:
        os.makedirs(SHOT_DIR, exist_ok=True)
    ext = find_extension(install)
    record("bundled extension present", ext is not None, ext or "share/extensions/hst-vietnamese-tools missing")
    if ext:
        record("extension files", True, sorted(os.listdir(ext)))
        import_checks(ext)
    code = 1
    proc = None
    try:
        import uno
        from com.sun.star.beans import PropertyValue
        env = dict(os.environ, PYUNO_LOGLEVEL="ARGS", PYUNO_LOGTARGET=os.path.join(out, "pyuno.log"))
        profile = "file:///" + os.path.join(out, "profile").replace("\\", "/")
        proc, ctx = start_office(program, profile, args.port, os.path.join(out, "soffice.err"), env)
        desktop = ctx.ServiceManager.createInstanceWithContext("com.sun.star.frame.Desktop", ctx)
        record("office started", True, ctx.ServiceManager.createInstanceWithContext("com.sun.star.configuration.ConfigurationProvider", ctx) is not None)
        for service in ("org.hst.office.vi.DispatchProvider", "org.hst.office.update.UpdateDispatchProvider"):
            try:
                record("service registered " + service, ctx.ServiceManager.createInstanceWithContext(service, ctx) is not None)
            except Exception:  # noqa: BLE001
                record("service registered " + service, False, traceback.format_exc())
        hidden = PropertyValue()
        hidden.Name, hidden.Value = "Hidden", False
        for kind, urls in (("swriter", ["org.hst.office.vi:Nd30Wizard", "org.hst.office.vi:ConvertEncoding", "org.hst.office.vi:ShowSolutions",
                                        "org.hst.office.update:Check"]),
                           ("scalc", ["org.hst.office.vi:ImportCsv", "org.hst.office.vi:FormatDate", "org.hst.office.vi:FormatVnd",
                                      "org.hst.office.vi:FormatPercent"])):
            doc = desktop.loadComponentFromURL("private:factory/" + kind, "_blank", 0, (hidden,))
            frame = doc.getCurrentController().getFrame()
            for url in urls:
                try:
                    titles, error = run_command(ctx, frame, url, True)
                except Exception:  # noqa: BLE001
                    titles, error = None, traceback.format_exc()
                dialog_commands = ("Nd30Wizard", "ShowSolutions", "ImportCsv", "ConvertEncoding")
                wants = any(url.endswith(c) for c in dialog_commands)
                ok = titles is not None and not error and (bool(titles) or not wants)
                record("dispatch %s (%s)" % (url, kind), ok, "windows=%s %s" % (titles, error))
            doc.close(True)
        try:  # F1 help: the configured root must resolve to an existing file inside the install
            provider = ctx.ServiceManager.createInstanceWithContext("com.sun.star.configuration.ConfigurationProvider", ctx)
            arg = PropertyValue()
            arg.Name, arg.Value = "nodepath", "/org.openoffice.Office.Common/Help"
            root = provider.createInstanceWithArguments("com.sun.star.configuration.ConfigurationAccess", (arg,)).getByName("HelpRootURL")
            expanded = ctx.getValueByName("/singletons/com.sun.star.util.theMacroExpander").expandMacros(root.replace("vnd.sun.star.expand:", ""))
            path = uno.fileUrlToSystemPath(expanded)
            record("help root exists", os.path.isfile(path), "%s -> %s" % (root, path))
        except Exception:  # noqa: BLE001
            record("help root exists", False, traceback.format_exc())
        try:
            desktop.terminate()
        except Exception:  # noqa: BLE001
            pass
    except Exception:  # noqa: BLE001
        record("smoke harness", False, traceback.format_exc())
    finally:
        if proc is not None:
            try:
                proc.wait(30)
            except subprocess.TimeoutExpired:
                proc.kill()
    failed = [r for r in ROWS if r["status"] == "FAIL"]
    with open(os.path.join(out, "smoke-results.json"), "w", encoding="utf-8") as handle:
        json.dump({"results": ROWS, "failed": len(failed)}, handle, ensure_ascii=False, indent=1)
    print("%d checks, %d failed" % (len(ROWS), len(failed)))
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
