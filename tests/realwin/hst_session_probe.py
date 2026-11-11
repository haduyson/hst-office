# SPDX-License-Identifier: AGPL-3.0-only
"""In the console user's session, with the user's own HST profile (as a user would): start HST Office as the user
does, time the start to the document window, read the UI language and icon theme in use, take window-only
screenshots (window-shot.ps1) and close the office again.

Run with the office's bundled interpreter through interactive-task.ps1:
  python.exe hst_session_probe.py --install DIR --out DIR --runs 3 [--module writer]
Writes probe.json in --out. Starts nothing when an office already runs in this session (the user's own).
"""
import argparse
import json
from pathlib import Path
import subprocess
import sys
import time

from session_windows import dismiss_dialogs, office_windows, running_offices, set_topmost

PIPE = "hstrealwinprobe"
HERE = Path(__file__).resolve().parent


def connect(timeout=120):
    import uno
    local = uno.getComponentContext()
    resolver = local.ServiceManager.createInstanceWithContext("com.sun.star.bridge.UnoUrlResolver", local)
    deadline = time.time() + timeout
    while True:
        try:
            return resolver.resolve(f"uno:pipe,name={PIPE};urp;StarOffice.ComponentContext")
        except Exception:  # noqa: BLE001 - not listening yet
            if time.time() > deadline:
                raise
            time.sleep(0.3)


def config(ctx, path, name):
    import uno
    provider = ctx.ServiceManager.createInstanceWithContext("com.sun.star.configuration.ConfigurationProvider", ctx)
    arg = uno.createUnoStruct("com.sun.star.beans.PropertyValue")
    arg.Name, arg.Value = "nodepath", path
    try:
        return provider.createInstanceWithArguments("com.sun.star.configuration.ConfigurationAccess", (arg,)).getPropertyValue(name)
    except Exception as error:  # noqa: BLE001 - recorded
        return f"<{type(error).__name__}>"


def start_once(install, module, timeout=180):
    """Launch like a user (soffice.exe --writer); seconds to the first office window and to the document window."""
    started = time.perf_counter()
    proc = subprocess.Popen([str(Path(install) / "program" / "soffice.exe"), f"--{module}", "--norestore",
                             f"--accept=pipe,name={PIPE};urp;"])
    first = document = None
    while time.perf_counter() - started < timeout:
        windows = office_windows()
        now = round(time.perf_counter() - started, 2)
        if windows and first is None:
            first = now
        if any(" \u2014 HST" in title or " - HST" in title for title, w, h in windows if w > 400 and h > 300):  # "Untitled 1 — HST ..."
            document = now
            break
        time.sleep(0.05)
    return proc, dict(first_window_s=first, document_window_s=document, windows=[t for t, _w, _h in office_windows()])


def shoot(prefix):
    done = subprocess.run(["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(HERE / "window-shot.ps1"),
                           "-Prefix", str(prefix)], capture_output=True, text=True, timeout=120,
                          creationflags=0x08000000)  # CREATE_NO_WINDOW: no console on the user's desktop
    return done.returncode


def close(proc):
    """{method: terminate|taskkill, dialogs: titles dismissed first, gone: no soffice.bin left}."""
    result = dict(dialogs=dismiss_dialogs(), method="terminate", attempts=[])
    for _ in range(3):  # a veto while start-up jobs still run is retried, as a user would click close again
        try:
            ctx = connect(30)
            value = bool(ctx.ServiceManager.createInstanceWithContext("com.sun.star.frame.Desktop", ctx).terminate())
        except Exception as error:  # noqa: BLE001 - the bridge drops when the office quits
            value = f"{type(error).__name__}"
        result["attempts"].append(value)
        if value is not False:
            break
        time.sleep(5)
    try:
        proc.wait(timeout=60)
    except subprocess.TimeoutExpired:
        result["method"] = "taskkill"
        subprocess.run(["taskkill", "/PID", str(proc.pid), "/T", "/F"], capture_output=True)
    for _ in range(60):  # soffice.exe returns before soffice.bin has finished writing the profile
        if not running_offices():
            result["gone"] = True
            return result
        time.sleep(1)
    result["gone"] = False
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--install", required=True)
    parser.add_argument("--out", required=True)
    parser.add_argument("--runs", type=int, default=3)
    parser.add_argument("--module", default="writer")
    args = parser.parse_args()
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    report = dict(time=time.strftime("%Y-%m-%dT%H:%M:%S"), runs=[])
    save = lambda: (out / "probe.json").write_text(json.dumps(report, indent=1, ensure_ascii=False), encoding="utf-8")  # noqa: E731
    if running_offices():
        report["error"] = "an office already runs in this session; not touching it"
        save()
        return 3
    for index in range(args.runs):
        proc, timing = start_once(args.install, args.module)
        timing["run"] = "first" if index == 0 else "warm"
        time.sleep(10)  # a user does not close the window in the same second it appears
        if index == 0:
            report["lifted"] = set_topmost(True)
            try:
                shot = shoot(out / f"{args.module}-first")
            finally:
                set_topmost(False)
            ctx = connect()
            report["settings"] = dict(
                ooLocale=config(ctx, "/org.openoffice.Setup/L10N", "ooLocale"),
                UILocale=config(ctx, "/org.openoffice.Office.Linguistic/General", "UILocale"),
                SymbolStyle=config(ctx, "/org.openoffice.Office.Common/Misc", "SymbolStyle"),
                ProductVersion=config(ctx, "/org.openoffice.Setup/Product", "ooSetupVersionAboutBox"),
                screenshot_rc=shot)
            report["windows_after_start"] = [t for t, _w, _h in office_windows()]
        timing["closed"] = close(proc)
        report["runs"].append(timing)
        save()
        time.sleep(3)
    return 0


if __name__ == "__main__":
    sys.exit(main())
