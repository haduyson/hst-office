#!/usr/bin/env python3
# SPDX-License-Identifier: AGPL-3.0-only
"""Stress: cycling the user interface modes with two documents of each module open never crashes an INSTALLED HST
Office (Windows).

The Windows counterpart of check-ui-mode-cycle-stress.py; scenario and verdict: ui_mode_cycle_stress.py (PASS, FAIL
only on a crash, INCONCLUSIVE on a hang or a harness error). On a crash the office's Application Error events since the
start (faulting module and offset, e.g. KERNELBASE.dll+0x6567c) go into the detail and <out>/crash-events.txt. Run it in
an interactive session (tests/runtime/windows-own-session-task.ps1 over SSH). Usage: "<install>\\program\\python.exe"
tests/runtime/check-windows-ui-mode-cycle-stress.py --install DIR --out DIR [--rounds 20] [--port 2177].
Exit 1 only when the office crashed.
"""
import argparse
import datetime
import os
import subprocess
import sys

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import ui_mode_cycle_stress as stress  # noqa: E402
import windows_gui as wg  # noqa: E402

CRASH_EVENTS = r"""
$since = [datetime]::Parse('%s')
Get-WinEvent -FilterHashtable @{LogName='Application'; ProviderName='Application Error'; StartTime=$since} `
    -ErrorAction SilentlyContinue | Where-Object { $_.Message -match 'soffice' } |
    ForEach-Object { $p = $_.Properties; '{0} {1}+{2} code {3} ({4})' -f $_.TimeCreated.ToString('s'), $p[3].Value,
        $p[7].Value, $p[6].Value, $p[0].Value }
"""


def own_office_pids(profile):
    """soffice processes started with this check's profile (never another session's or agent's office)."""
    marker = profile.replace("\\", "/").lower()
    script = ("Get-CimInstance Win32_Process -Filter \"Name like 'soffice%'\" | ForEach-Object { "
              "'{0}|{1}' -f $_.ProcessId, $_.CommandLine }")
    listing = subprocess.run(["powershell", "-NoProfile", "-Command", script], capture_output=True, text=True,
                             check=False).stdout
    return [int(row.split("|", 1)[0]) for row in listing.splitlines()
            if "|" in row and marker in row.split("|", 1)[1].replace("\\", "/").lower()]


def load_adapter():
    """The Adapter of check-windows-ui-mode-tabs.py (wg.WinOffice with the interface the scenario expects)."""
    import importlib.util
    spec = importlib.util.spec_from_file_location("check_windows_ui_mode_tabs",
                                                  os.path.join(HERE, "check-windows-ui-mode-tabs.py"))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.Adapter


def main():
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--install", required=True)
    parser.add_argument("--out", required=True)
    parser.add_argument("--rounds", type=int, default=20)
    parser.add_argument("--port", type=int, default=2177)
    args = parser.parse_args()
    out = os.path.abspath(args.out)
    os.makedirs(out, exist_ok=True)
    office = wg.WinOffice(args.install, os.path.join(out, "profile"), args.port, os.path.join(out, "log"), nodefault=True)
    started = datetime.datetime.now().replace(microsecond=0)

    def kill_own():
        for pid in own_office_pids(office.profile):
            subprocess.run(["taskkill", "/F", "/PID", str(pid)], capture_output=True, check=False)

    def on_hang():
        wg.screenshot(os.path.join(out, "hang.png"), cursor=False)
        kill_own()

    def is_crash(error):
        return (office.proc is not None and office.proc.poll() is not None) or not own_office_pids(office.profile) \
            or "disposed" in str(error)

    def crash_detail():
        events = subprocess.run(["powershell", "-NoProfile", "-Command", CRASH_EVENTS % started.isoformat()],
                                capture_output=True, text=True, check=False).stdout.strip()
        with open(os.path.join(out, "crash-events.txt"), "w", encoding="utf-8") as handle:
            handle.write(events + "\n")
        return "[Application Error: %s]" % ("; ".join(events.splitlines()) or "none recorded")

    office.start(fresh=True)
    seen = wg.dismiss_startup(office, os.path.join(out, "startup.png"), timeout=30, settle=5)
    # A document loaded right after a start-up question was ended over UNO has crashed this harness (not this
    # check's defect): restart until a start shows no question, as check-windows-ui-mode-tabs.py does.
    for start in range(2, 5):
        if not seen:
            break
        office.stop()
        office.start()
        seen = wg.dismiss_startup(office, os.path.join(out, "startup-%d.png" % start), timeout=15, settle=3)
    started = datetime.datetime.now().replace(microsecond=0)
    try:
        return stress.run(load_adapter()(office), args.rounds, out, on_hang, is_crash, crash_detail)
    finally:
        try:
            office.stop()
        finally:
            kill_own()


if __name__ == "__main__":
    raise SystemExit(main())
