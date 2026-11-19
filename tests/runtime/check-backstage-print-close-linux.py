#!/usr/bin/env python3
# SPDX-License-Identifier: AGPL-3.0-only
"""Linux: the ways a document ends while its File panel shows the Print page with a print job
(hst-backstage-print-job-ends-before-close.patch); the Linux counterpart of check-backstage-print-close.py.
A visible office per case and application (Writer, Sheets) on the X display of DISPLAY (your own Xvfb), any VCL
plugin (gtk3 builds the panel from native widgets, so the page is opened by .uno:Print and shown by a screenshot):
  sigterm     a changed document, then SIGTERM to soffice.bin (what systemd/logind send at the end of the session),
              AutoRecovery on: the office ends by itself (exit code 0) and leaves no crash report.
  macroclose  XCloseable.close(True) from a Python macro of the profile (main thread): the office stays.
  macroterm   Desktop.terminate() from the same macro: exit code 0.
  quit        .uno:Quit (File > Thoát): exit code 0.
  ctrlw       Ctrl+W (xdotool, to the focused office window): the document closes, the office stays.
A crash counts by the exit code, by a soffice.bin that died on a signal (its status in /proc, or gone with a crash
report in the profile's crash folder).
Usage: <office>/program/python check-backstage-print-close-linux.py --soffice <office>/program/soffice --out DIR
       [--cases a,b] [--apps swriter,scalc] [--shot 'import -window root {}']
Exit 1 on a failure.
"""
import argparse
import glob
import importlib.util
import os
import signal
import subprocess
import sys
import tempfile
import threading
import time

HERE = os.path.dirname(os.path.abspath(__file__))
_SPEC = importlib.util.spec_from_file_location("check_backstage_print", os.path.join(HERE, "check-backstage-print.py"))
BASE = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(BASE)
CASES = ("sigterm", "macroclose", "macroterm", "quit", "ctrlw")
MACRO = """
def close_doc(*args):
    XSCRIPTCONTEXT.getDocument().close(True)
def terminate(*args):
    XSCRIPTCONTEXT.getDesktop().terminate()
"""
failures = []


def check(ok, text):
    print(("PASS  " if ok else "FAIL  ") + text, flush=True)
    failures.extend([] if ok else [text])


def bin_pids(work):
    """soffice.bin processes started with this case's profile."""
    marker = os.path.basename(work) + "/profile"
    pids = []
    for cmdline in glob.glob("/proc/[0-9]*/cmdline"):
        try:
            with open(cmdline, "rb") as handle:
                argv = handle.read().split(b"\0")
        except OSError:
            continue
        if argv and argv[0].endswith(b"soffice.bin") and any(marker.encode() in a for a in argv):
            pids.append(int(cmdline.split("/")[2]))
    return pids


def crash_reports(work):
    return glob.glob(os.path.join(work, "profile", "user", "crash", "*"))


def start(case, work, soffice):
    real_popen = subprocess.Popen
    if case == "sigterm":  # AutoRecovery on: the session end stores the documents (the product's way)
        subprocess.Popen = lambda argv, **kw: real_popen([a for a in argv if a != "--norestore"], **kw)
    try:
        office = BASE.VisibleOffice(soffice, work, None)
    finally:
        subprocess.Popen = real_popen
    scripts = os.path.join(work, "profile", "user", "Scripts", "python")
    os.makedirs(scripts, exist_ok=True)
    with open(os.path.join(scripts, "hstprintclose.py"), "w", encoding="utf-8") as handle:
        handle.write(MACRO)
    return office


def load(office, app):
    from com.sun.star.beans import PropertyValue
    arg = PropertyValue()
    arg.Name, arg.Value = "OnMainThread", True
    return office.desktop.loadComponentFromURL(f"private:factory/{app}", "_blank", 0, (arg,))


def run(case, app, args):
    work = os.path.join(args.out, f"{case}-{app}")
    office = start(case, work, args.soffice)
    tag, doc = f"{case} {app}", None
    shot = (lambda name: subprocess.run(args.shot.format(os.path.join(args.out, name + ".png")), shell=True)) \
        if args.shot else (lambda name: None)
    try:
        office.close_welcome()
        doc = load(office, app)
        frame = doc.getCurrentController().getFrame()
        title = frame.Title
        pids = bin_pids(work)
        time.sleep(3)
        if case == "sigterm":
            if app == "swriter":
                doc.getText().setString("đã sửa")
            else:
                doc.Sheets.getByIndex(0).getCellByPosition(0, 0).setString("đã sửa")
        office.ui.executeCommandForProvider(".uno:Print", frame)
        time.sleep(8)  # the job comes back to the page; the preview is painted on idle
        shot(f"{case}-{app}-page")
        if case == "sigterm":
            for pid in pids:
                os.kill(pid, signal.SIGTERM)
        elif case in ("macroclose", "macroterm"):
            url = ("vnd.sun.star.script:hstprintclose.py$" + ("close_doc" if case == "macroclose" else "terminate")
                   + "?language=Python&location=user")
            threading.Thread(target=lambda: office.ui.executeCommandForProvider(url, frame), daemon=True).start()
        elif case == "quit":
            threading.Thread(target=lambda: office.ui.executeCommandForProvider(".uno:Quit", frame), daemon=True).start()
        else:
            subprocess.run(["xdotool", "key", "--clearmodifiers", "ctrl+w"], timeout=30, check=False)
        for _ in range(60):
            if office.proc.poll() is not None:
                break
            time.sleep(0.5)
        time.sleep(3)
        shot(f"{case}-{app}-after")
        code = office.proc.poll()
        if case in ("sigterm", "macroterm", "quit"):
            check(code == 0, f"{tag}: the office ended with exit code 0 (got {code})")
        else:
            check(code is None and bool(bin_pids(work)), f"{tag}: the office keeps running (exit {code})")
            names = [f.Title for f in office.desktop.getFrames()] if code is None else []
            check(title not in names, f"{tag}: the document closed ({names})")
        reports = crash_reports(work)
        check(not reports, f"{tag}: no crash report {reports}")
    finally:
        try:
            if doc is not None and office.proc.poll() is None:
                doc.setModified(False)
        except Exception:  # noqa: BLE001 - the document may be gone
            pass
        if office.proc.poll() is None:
            office.stop()
        for pid in bin_pids(work):  # an office of this case that did not end
            os.kill(pid, signal.SIGKILL)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--soffice", required=True)
    parser.add_argument("--out", default=tempfile.mkdtemp(prefix="hst-bsprint-close-linux-"))
    parser.add_argument("--cases", default=",".join(CASES))
    parser.add_argument("--apps", default="swriter,scalc")
    parser.add_argument("--shot", help="screenshot command with {} for the file, e.g. 'import -window root {}'")
    args = parser.parse_args()
    args.out = os.path.abspath(args.out)
    os.makedirs(args.out, exist_ok=True)
    for case in args.cases.split(","):
        for app in args.apps.split(","):
            try:
                run(case, app, args)
            except Exception as error:  # noqa: BLE001 - one case's failure is its result
                check(False, f"{case} {app}: run ({type(error).__name__}: {error})")
    print(f"{len(failures)} failure(s)", flush=True)
    sys.exit(1 if failures else 0)


if __name__ == "__main__":
    main()
