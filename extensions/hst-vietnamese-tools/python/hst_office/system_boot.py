# SPDX-License-Identifier: AGPL-3.0-only
"""Did the computer start again after the previous session's last sign of life?

A session that never closed and left no crash or hang record ("not closed") was either ended while the system kept
running (the user ended it in Task Manager, a silent exit) or went down with the system: power lost, the battery ran
out while the computer slept, a forced or update restart the office was not told about. User reports that only said
"sleep mode" could not tell these apart. Sleep and hibernation by themselves end nothing: the office has no power
handling and wakes up with the system.

The next start compares when the system started with the last moment the office answered (the heartbeat, else the
session's start). Boot time = wall clock minus uptime: GetTickCount64 on Windows (it counts time asleep and
hibernated, unlike the "unbiased" interrupt time), btime of /proc/stat on Linux, kern.boottime on macOS. A shut down
with Windows fast startup hibernates the kernel and keeps the uptime running, so "running" there means "no restart
seen", not "the office was killed": the line says what was measured. No names, only times.
"""
import platform
import re
import subprocess
import time

SLACK = 60  # uptime and the wall clock drift by seconds, time-service corrections by more


def boot_time(system=None, now=None):
    """Epoch seconds when the system last started, or None when unreadable."""
    system = system or platform.system()
    now = time.time() if now is None else now
    try:
        if system == "Windows":
            import ctypes
            ticks = ctypes.windll.kernel32.GetTickCount64
            ticks.restype = ctypes.c_ulonglong
            return now - ticks() / 1000.0
        if system == "Linux":
            with open("/proc/stat", encoding="ascii") as handle:
                for line in handle:
                    if line.startswith("btime "):
                        return float(line.split()[1])
        if system == "Darwin":
            out = subprocess.run(["sysctl", "-n", "kern.boottime"], capture_output=True, text=True,
                                 timeout=5).stdout
            found = re.search(r"sec = (\d+)", out)
            return float(found.group(1)) if found else None
    except Exception:  # noqa: BLE001 - diagnostics must never stop the start
        return None
    return None


def since(previous, boot):
    """"restarted" when the system started after the previous session's last sign of life, "running" when it was
    already up then, None when either time is unknown (pure)."""
    if not previous or not boot:
        return None
    last = previous.get("beat") or previous.get("started")
    if not last:
        return None
    return "restarted" if boot > float(last) + SLACK else "running"


def facts(previous):
    """The crash-report line about the system's start (pure)."""
    state, boot = (previous or {}).get("system"), (previous or {}).get("boot")
    if not state:
        return []
    clock = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(boot))
    if state == "restarted":
        return ["System started at %s, after the session's last sign of life: the computer restarted or lost power "
                "while the office ran" % clock]
    return ["System up since %s, before the session's last sign of life: no restart seen (a fast-startup shut "
            "down keeps this time)" % clock]
