# SPDX-License-Identifier: AGPL-3.0-only
"""Office processes for scripts/perf/large-file-open.py: find, measure and stop soffice processes.

Uses psutil when the Python has it; otherwise /proc on Linux and tasklist/taskkill on Windows (an office's bundled
Python has no psutil)."""
import csv
import io
import os
import subprocess
import sys

WINDOWS = sys.platform == "win32"


def _tasklist():
    out = subprocess.run(["tasklist", "/FO", "CSV", "/NH"], capture_output=True, text=True, errors="replace").stdout
    rows = []
    for row in csv.reader(io.StringIO(out)):
        if len(row) >= 5 and row[0].lower().startswith("soffice"):
            kb = int("".join(ch for ch in row[4] if ch.isdigit()) or 0)
            rows.append((int(row[1]), kb * 1024))
    return rows


def office_pids():
    try:
        import psutil
        return [p.pid for p in psutil.process_iter(["name"]) if (p.info["name"] or "").lower().startswith("soffice")]
    except ImportError:
        pass
    if WINDOWS:
        return [pid for pid, _ in _tasklist()]
    pids = []
    for d in os.listdir("/proc"):
        if d.isdigit():
            try:
                with open("/proc/%s/comm" % d) as f:
                    if f.read().strip().startswith("soffice"):
                        pids.append(int(d))
            except OSError:
                pass
    return pids


def _parents():
    """{pid: parent pid} of all processes, or None when it cannot be read."""
    if WINDOWS:  # Toolhelp snapshot (wmic is gone from current Windows)
        import ctypes
        from ctypes import wintypes

        class Entry(ctypes.Structure):
            _fields_ = [("dwSize", wintypes.DWORD), ("cntUsage", wintypes.DWORD), ("th32ProcessID", wintypes.DWORD),
                        ("th32DefaultHeapID", ctypes.c_void_p), ("th32ModuleID", wintypes.DWORD),
                        ("cntThreads", wintypes.DWORD), ("th32ParentProcessID", wintypes.DWORD),
                        ("pcPriClassBase", ctypes.c_long), ("dwFlags", wintypes.DWORD),
                        ("szExeFile", ctypes.c_wchar * 260)]
        k32 = ctypes.windll.kernel32
        k32.CreateToolhelp32Snapshot.restype = wintypes.HANDLE
        snap = k32.CreateToolhelp32Snapshot(2, 0)  # TH32CS_SNAPPROCESS
        if not snap or snap == wintypes.HANDLE(-1).value:
            return None
        entry, parents = Entry(), {}
        entry.dwSize = ctypes.sizeof(Entry)
        ok = k32.Process32FirstW(snap, ctypes.byref(entry))
        while ok:
            parents[entry.th32ProcessID] = entry.th32ParentProcessID
            ok = k32.Process32NextW(snap, ctypes.byref(entry))
        k32.CloseHandle(snap)
        return parents or None
    parents = {}
    for d in os.listdir("/proc"):
        if d.isdigit():
            try:
                with open("/proc/%s/stat" % d) as f:
                    parents[int(d)] = int(f.read().rsplit(")", 1)[1].split()[1])
            except (OSError, IndexError, ValueError):
                pass
    return parents


def descendants(root, pids):
    """The given pids that descend from <root>: another harness's office on the same machine is not ours."""
    parents = _parents()
    if parents is None:
        return set(pids)
    mine = set()
    for pid in pids:
        p, seen = pid, 0
        while p and p != root and seen < 64:
            p, seen = parents.get(p, 0), seen + 1
        if p == root:
            mine.add(pid)
    return mine


def rss_mb(pids):
    """Resident (Windows: working set) memory of the given office processes, MB."""
    try:
        import psutil
        total = 0
        for pid in pids:
            try:
                total += psutil.Process(pid).memory_info().rss
            except Exception:  # noqa: BLE001 - the process ended
                pass
        return total / 1e6
    except ImportError:
        pass
    if WINDOWS:
        return sum(rss for pid, rss in _tasklist() if pid in pids) / 1e6
    total = 0
    for pid in pids:
        try:
            with open("/proc/%d/statm" % pid) as f:
                total += int(f.read().split()[1]) * os.sysconf("SC_PAGE_SIZE")
        except OSError:
            pass
    return total / 1e6


def kill(proc, own):
    for pid in own:
        if WINDOWS:
            subprocess.run(["taskkill", "/F", "/T", "/PID", str(pid)], capture_output=True)
        else:
            try:
                os.kill(pid, 9)
            except OSError:
                pass
    try:
        proc.kill()
    except OSError:
        pass


def limit_cpus(args, cpus):
    """Command line that starts the office on its first <cpus> logical processors (0: all), like a smaller PC."""
    if not cpus:
        return args
    if WINDOWS:  # a string: start's empty title argument does not survive list quoting
        return 'cmd /c start "" /B /WAIT /AFFINITY %X %s' % ((1 << cpus) - 1, subprocess.list2cmdline(args))
    return ["taskset", "-c", "0-%d" % (cpus - 1)] + args
