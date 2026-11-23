#!/usr/bin/env python3
# SPDX-License-Identifier: LicenseRef-HST-Proprietary
# Copyright (C) 2026 HASON TECH
"""gtk3 dialogs of a catalog first used by a .ui file, in the C locale (hst-gtk-ui-translation-c-locale.patch).

In the C locale load_ui_file translates the .ui texts itself and creates the catalog of the interface's domain. The
domain went to Translate::Create as a view into the file, and boost::locale took the rest of the .ui as the domain
name and its encoding: the cui catalog then had no texts and threw boost::locale::conv::invalid_charset_error for
every non-ASCII source text, so Tip of the Day (shown with the first document of the day, e.g. Start Center ->
"Bảng tính") and Format > Paragraph aborted the office.

Starts its own office (fresh profile, gtk3, LC_ALL=C.UTF-8, Vietnamese UI) on a free port, opens a Writer document,
then opens and closes each dialog of DIALOGS with a dispatch on a worker thread (the dialog is modal). Each one must
open without an exception and leave the office running; its window title must be the Vietnamese one when xdotool is
there. Run under Xvfb:
    <office program>/python check-gtk-ui-catalog-c-locale.py --soffice <office program>/soffice.bin --out DIR
Exit 1 on a failure.
"""
import argparse, os, shutil, socket, subprocess, sys, tempfile, threading, time  # noqa: E401

import uno  # noqa: F401  (the office's python)

# command, a word of the Vietnamese title (None: not checked)
DIALOGS = ((".uno:TipOfTheDay", "Mẹo"), (".uno:ParagraphDialog", "Đoạn văn"))
REGISTRY = """<?xml version="1.0" encoding="UTF-8"?>
<oor:items xmlns:oor="http://openoffice.org/2001/registry" xmlns:xs="http://www.w3.org/2001/XMLSchema">
<item oor:path="/org.openoffice.Office.Linguistic/General"><prop oor:name="UILocale" oor:op="fuse"><value>vi-VN</value></prop></item>
</oor:items>
"""


def free_port():
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


def start(cmd, env, log, port):
    """The office and a connection to it; a first start in a fresh profile ends with 81 and is started again."""
    local = uno.getComponentContext()
    resolver = local.ServiceManager.createInstanceWithContext("com.sun.star.bridge.UnoUrlResolver", local)
    proc = subprocess.Popen(cmd, env=env, stdout=log, stderr=subprocess.STDOUT)
    for _ in range(180):
        if proc.poll() == 81:
            proc = subprocess.Popen(cmd, env=env, stdout=log, stderr=subprocess.STDOUT)
        elif proc.poll() is not None:
            break
        try:
            return proc, resolver.resolve(f"uno:socket,host=127.0.0.1,port={port};urp;StarOffice.ComponentContext")
        except Exception:  # noqa: BLE001 - not listening yet
            time.sleep(1)
    proc.kill()
    raise SystemExit("FAIL: no connection to the office")


def window_titles():
    if not shutil.which("xdotool"):
        return None
    run = subprocess.run(["xdotool", "search", "--onlyvisible", "--name", ".", "getwindowname", "%@"],
                         capture_output=True, text=True, timeout=30)
    return run.stdout.splitlines()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--soffice", required=True)
    parser.add_argument("--out", required=True)
    args = parser.parse_args()
    os.makedirs(args.out, exist_ok=True)
    profile = tempfile.mkdtemp(prefix="hst-c-locale-", dir=args.out)
    os.makedirs(os.path.join(profile, "user"))
    with open(os.path.join(profile, "user", "registrymodifications.xcu"), "w", encoding="utf-8") as handle:
        handle.write(REGISTRY)
    port = free_port()
    env = {k: v for k, v in os.environ.items() if not k.startswith(("PYTHON", "URE_", "UNO_", "LC_", "LANG"))}
    env.update(LC_ALL="C.UTF-8", SAL_USE_VCLPLUGIN="gtk3", NO_AT_BRIDGE="1")
    cmd = [args.soffice, "-env:UserInstallation=" + uno.systemPathToFileUrl(profile), "--norestore", "--nologo",
           f"--accept=socket,host=127.0.0.1,port={port};urp;", "--writer"]
    failures = []
    with open(os.path.join(args.out, "office.log"), "w", encoding="utf-8") as log:
        proc, ctx = start(cmd, env, log, port)
        try:
            smgr = ctx.ServiceManager
            desktop = smgr.createInstanceWithContext("com.sun.star.frame.Desktop", ctx)
            doc = desktop.loadComponentFromURL("private:factory/swriter", "_blank", 0, ())
            time.sleep(5)
            helper = smgr.createInstanceWithContext("com.sun.star.frame.DispatchHelper", ctx)
            toolkit = smgr.createInstanceWithContext("com.sun.star.awt.Toolkit", ctx)
            for command, title in DIALOGS:
                errors = []

                def dispatch(command=command, errors=errors):
                    try:
                        helper.executeDispatch(doc.CurrentController.Frame, command, "", 0, ())
                    except Exception as exc:  # noqa: BLE001 - reported below
                        errors.append(str(exc)[:300])

                worker = threading.Thread(target=dispatch, daemon=True)
                worker.start()
                time.sleep(6)
                titles = window_titles()
                if titles is not None and title and not any(title in t for t in titles):
                    failures.append(f"{command}: no window titled with {title!r} ({titles})")
                active = toolkit.getActiveTopWindow()
                if active is not None and hasattr(active, "endExecute"):
                    active.endExecute()
                elif shutil.which("xdotool"):
                    subprocess.run(["xdotool", "key", "Escape"], timeout=30)
                worker.join(20)
                if errors:
                    failures.append(f"{command}: {errors[0]}")
                if proc.poll() is not None:
                    failures.append(f"{command}: the office ended (exit {proc.returncode})")
                    break
                print(f"{command}: {'ok' if not failures else 'checked'}", flush=True)
        finally:
            if proc.poll() is None:
                proc.terminate()
                try:
                    proc.wait(30)
                except subprocess.TimeoutExpired:
                    proc.kill()
    for failure in failures:
        print("FAIL:", failure)
    print("PASS" if not failures else "FAILED")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
