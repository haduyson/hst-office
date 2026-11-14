# SPDX-License-Identifier: AGPL-3.0-only
"""The soffice.bin processes that belong to one harness office, recognised by its private profile.

Every WinOffice starts soffice with -env:UserInstallation=<its own profile URL>; soffice.bin keeps that argument,
also after the first-start restart (when the soffice.exe the harness started has already ended). That URL is the
only test of ownership used here: the input gate lets keys reach only windows of these processes, and WinOffice.stop
ends only these processes, never another soffice (another agent's check, the owner's own office)."""
import json
import re
import subprocess
import time

_QUERY = ("Get-CimInstance Win32_Process -Filter \"Name='soffice.bin'\" | "
          "Select-Object ProcessId, Name, CommandLine | ConvertTo-Json -Compress")


def profile_pattern(url):
    """Matches `url` as the whole value of -env:UserInstallation (a profile ".../p" never matches ".../p2")."""
    return re.compile(r"-env:UserInstallation=" + re.escape(url.rstrip("/")) + r"/?(?=[\"\s]|$)", re.IGNORECASE)


def owned_pids(rows, url):
    """PIDs of the soffice.bin rows ({ProcessId, Name, CommandLine}) started with profile `url`."""
    pattern = profile_pattern(url)
    return sorted(int(row["ProcessId"]) for row in rows
                  if (row.get("Name") or "").lower() == "soffice.bin" and pattern.search(row.get("CommandLine") or ""))


def soffice_rows():
    """Every soffice.bin on this machine with its command line ([] when the query fails: nothing is then owned)."""
    try:
        text = subprocess.run(["powershell", "-NoProfile", "-Command", _QUERY], capture_output=True, text=True,
                              timeout=60, check=False).stdout.strip()
        rows = json.loads(text) if text else []
    except (OSError, ValueError, subprocess.SubprocessError):
        return []
    return [rows] if isinstance(rows, dict) else rows


def profile_bin_pids(url, rows=None):
    return owned_pids(soffice_rows() if rows is None else rows, url)


def _taskkill(pid, force):
    subprocess.run(["taskkill", "/PID", str(pid)] + (["/F"] if force else []), capture_output=True, timeout=30,
                   check=False)


def terminate(url, timeout=20, list_pids=None, kill=None, sleep=time.sleep):
    """End the soffice.bin processes of profile `url`: a polite taskkill, then /F for what is left after `timeout`
    seconds. The PIDs are looked up again before each step, so a reused PID of another process is never hit.
    Returns the PIDs that were found at first."""
    list_pids = list_pids or profile_bin_pids
    kill = kill or _taskkill
    first = list_pids(url)
    for pid in first:
        kill(pid, False)
    deadline = time.time() + timeout
    while list_pids(url) and time.time() < deadline:
        sleep(1)
    for pid in list_pids(url):
        kill(pid, True)
    return first


class ProfileOwner:
    """The input gate's owner check for one profile: a window's PID is ours when it is a soffice.bin of that profile.
    Known PIDs are cached; an unknown PID refreshes the list once (the office may have restarted itself)."""

    def __init__(self, url, list_pids=None):
        self.url, self.list_pids, self.pids = url, list_pids or profile_bin_pids, set()

    def owns(self, pid):
        if pid not in self.pids:
            self.pids = set(self.list_pids(self.url))
        return pid in self.pids
