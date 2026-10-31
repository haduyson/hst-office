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

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")  # the Windows console is cp1252

ROWS = []
OUT = None


def record(name, ok, detail=""):
    ROWS.append({"check": name, "status": "PASS" if ok else "FAIL", "detail": str(detail)[:1500]})
    print("%s  %s  %s" % ("PASS" if ok else "FAIL", name, str(detail)[:300]), flush=True)
    if OUT:  # written after every check so a hang still leaves evidence
        with open(os.path.join(OUT, "smoke-results.json"), "w", encoding="utf-8") as handle:
            json.dump({"results": ROWS, "failed": sum(r["status"] == "FAIL" for r in ROWS)}, handle, ensure_ascii=False, indent=1)
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


def close_dialog(window):
    """End a modal dialog: endExecute when the peer offers XDialog, otherwise press Escape in the foreground window."""
    try:
        window.endExecute()
    except Exception:  # noqa: BLE001
        subprocess.run(["powershell", "-NoProfile", "-Command",
                        "Add-Type -AssemblyName System.Windows.Forms; [System.Windows.Forms.SendKeys]::SendWait('{ESC}')"],
                       timeout=30, check=False)


def is_new(window, known):
    return all(window != other for other in known)  # pyuno proxies compare by UNO object identity


def pump(toolkit, work, wait_for_window):
    """Run `work` in a thread; close every window that opens meanwhile. Returns (descriptions, error text).

    A description is "title WxH" (pixels); a window larger than the screen work area is reported as OVERSIZE.
    """
    known = top_windows(toolkit)
    state = {"error": ""}

    def target():
        try:
            work()
        except Exception:  # noqa: BLE001
            state["error"] += traceback.format_exc()

    thread = threading.Thread(target=target, daemon=True)
    thread.start()
    found, deadline = [], time.time() + 40
    area = toolkit.getWorkArea()
    while time.time() < deadline and (thread.is_alive() or (wait_for_window and not found)):
        for window in top_windows(toolkit):
            if is_new(window, known):
                known.append(window)
                time.sleep(4)  # let the dialog lay out (peer size settles), paint and get its title
                try:
                    size = window.getPosSize()
                except Exception:  # noqa: BLE001
                    size = area.__class__(0, 0, 0, 0)
                label = "%s %dx%d" % (window_title(window), size.Width, size.Height)
                if size.Width > area.Width or size.Height > area.Height:
                    label += " OVERSIZE(work area %dx%d)" % (area.Width, area.Height)
                found.append(label)
                shot(label)
                close_dialog(window)
        time.sleep(0.3)
    thread.join(10)
    if thread.is_alive():
        state["error"] += "still blocked after 50 s\n"
    return found, state["error"]


def open_document(ctx, desktop, kind):
    """Open a visible document from a thread: the first-start welcome dialog blocks the load until it is closed."""
    from com.sun.star.beans import PropertyValue
    toolkit = ctx.ServiceManager.createInstanceWithContext("com.sun.star.awt.Toolkit", ctx)
    box = {}
    flag = PropertyValue()
    flag.Name, flag.Value = "Hidden", False
    titles, error = pump(toolkit, lambda: box.update(doc=desktop.loadComponentFromURL("private:factory/" + kind, "_blank", 0, (flag,))), False)
    record("open %s (windows during load: %s)" % (kind, titles), "doc" in box and not error, error)
    return box.get("doc")


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
    state = {"error": ""}

    def work():
        try:
            dispatch.dispatch(url, ())
        except Exception:  # noqa: BLE001
            state["error"] = traceback.format_exc()

    titles, error = pump(toolkit, work, wait_for_window=True)
    state["error"] += error
    return titles, state["error"]


def tab_checks(ctx, desktop):
    """Document tabs (HST Office): three documents form one tab group with one shown window, the tab
    command switches, closing a tab shows the neighbour. Runs in the office of the smoke test."""
    def frames():
        access = desktop.getFrames()
        return [access.getByIndex(i) for i in range(access.getCount())]

    def shown():
        return [f for f in frames() if f.getContainerWindow().isVisible()]

    def wait(predicate, timeout=20):
        end = time.time() + timeout
        while time.time() < end:
            try:
                if predicate():
                    return True
            except Exception:  # noqa: BLE001 - UNO objects change while windows open and close
                pass
            time.sleep(0.3)
        return False

    helper = ctx.ServiceManager.createInstanceWithContext("com.sun.star.frame.DispatchHelper", ctx)
    start = len(frames())
    docs = [open_document(ctx, desktop, kind) for kind in ("swriter", "scalc", "simpress")]
    record("tabs: three documents open", all(docs) and len(frames()) == start + 3, len(frames()))
    record("tabs: one shown window (others parked)", wait(lambda: len(shown()) == 1), len(shown()))
    before = shown()[0].getTitle()
    began = time.time()
    helper.executeDispatch(shown()[0], ".uno:NextDocumentTab", "_self", 0, ())
    record("tabs: NextDocumentTab shows another tab",
           wait(lambda: len(shown()) == 1 and shown()[0].getTitle() != before),
           "%s, %.2f s" % (shown()[0].getTitle() if shown() else "-", time.time() - began))
    for doc in docs:
        doc.setModified(False)
    helper.executeDispatch(shown()[0], ".uno:CloseWin", "_self", 0, ())
    record("tabs: closing a tab shows the neighbour",
           wait(lambda: len(frames()) == start + 2 and len(shown()) == 1 and shown()[0].isActive()),
           "frames=%d shown=%d" % (len(frames()), len(shown())))
    for doc in docs:
        try:
            doc.close(True)
        except Exception:  # noqa: BLE001 - already closed
            pass


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
    global SHOT_DIR, OUT
    OUT = out
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
        for service in ("org.hst.office.vi.DispatchProvider", "org.hst.office.vi.UpdateDispatchProvider"):
            try:
                record("service registered " + service, ctx.ServiceManager.createInstanceWithContext(service, ctx) is not None)
            except Exception:  # noqa: BLE001
                record("service registered " + service, False, traceback.format_exc())
        for kind, urls in (("swriter", ["org.hst.office.vi:Nd30Wizard", "org.hst.office.vi:ConvertEncoding", "org.hst.office.vi:ShowSolutions",
                                        "org.hst.office.update:Check"]),
                           ("scalc", ["org.hst.office.vi:ImportCsv", "org.hst.office.vi:FormatDate", "org.hst.office.vi:FormatVnd",
                                      "org.hst.office.vi:FormatPercent"])):
            doc = open_document(ctx, desktop, kind)
            if doc is None:
                continue
            frame = doc.getCurrentController().getFrame()
            for url in urls:
                try:
                    titles, error = run_command(ctx, frame, url, True)
                except Exception:  # noqa: BLE001
                    titles, error = None, traceback.format_exc()
                dialog_commands = ("Nd30Wizard", "ShowSolutions", "ImportCsv", "ConvertEncoding")
                wants = any(url.endswith(c) for c in dialog_commands)
                ok = titles is not None and not error and (bool(titles) or not wants) and not any("OVERSIZE" in t for t in titles)
                record("dispatch %s (%s)" % (url, kind), ok, "windows=%s %s" % (titles, error))
            try:
                doc.close(True)
            except Exception:  # noqa: BLE001 - a leftover dialog may veto closing; the next step restarts nothing
                pass
        try:
            tab_checks(ctx, desktop)
        except Exception:  # noqa: BLE001
            record("document tabs", False, traceback.format_exc())
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
