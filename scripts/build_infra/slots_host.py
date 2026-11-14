# SPDX-License-Identifier: AGPL-3.0-only
"""Host probes of the admission controller (memory, swap, disk, slot locks) and the disk-refusal hint
that names the largest /data/hst-agents directories. Patched in tests.
"""
import fcntl
import json
import os
import shutil
import subprocess
import time

from .slots_model import GIB

def meminfo():
    values = {}
    with open("/proc/meminfo", encoding="ascii") as f:
        for line in f:
            key, rest = line.split(":", 1)
            values[key] = int(rest.split()[0]) * 1024
    return values


def mem_available_gib():
    return meminfo()["MemAvailable"] / GIB


def swap_used_gib():
    m = meminfo()
    return (m["SwapTotal"] - m["SwapFree"]) / GIB


def slice_cgroup(name):
    """cgroup v2 directory of a systemd slice: a dash nests slices (hst-build.slice is hst.slice/hst-build.slice)."""
    parts = name[:-len(".slice")].split("-")
    return "/sys/fs/cgroup/" + "/".join("-".join(parts[:i + 1]) + ".slice" for i in range(len(parts)))


def scope_memory_gib(scope):
    if not scope:
        return 0.0
    path = f"{slice_cgroup(os.environ.get('HST_LOCAL_SLICE') or 'system.slice')}/{scope}.scope/memory.current"
    try:
        with open(path, encoding="ascii") as f:
            return int(f.read().strip()) / GIB
    except (OSError, ValueError):
        return 0.0


def disk_free_gib(path):
    return shutil.disk_usage(path).free / GIB


def pid_alive(pid):
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


def slot_dirs(root):
    base = os.path.join(root, "slots")
    try:
        names = os.listdir(base)
    except FileNotFoundError:
        return []
    return sorted(int(n) for n in names if n.isdigit() and os.path.isdir(os.path.join(base, n, "src")))


def slot_locked(root, slot):
    """True when a local-build.sh run holds the slot's lock (also catches runs not registered here yet)."""
    path = os.path.join(root, "slots", str(slot), ".lock")
    try:
        fd = os.open(path, os.O_RDWR)
    except FileNotFoundError:
        return False
    try:
        fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        return True
    finally:
        os.close(fd)
    return False


def agents_top(root, agents_dir="/data/hst-agents", count=5, max_age=600, du=None):
    """The largest agent directories ("name size" strings), cached in locks/agents-usage.json for max_age seconds:
    a disk refusal names who is filling /data (agents read /data/hst-office-build/src/lo instead of copying trees)."""
    cache = os.path.join(root, "locks", "agents-usage.json")
    try:
        with open(cache, encoding="utf-8") as f:
            data = json.load(f)
        if time.time() - data["time"] < max_age:
            return data["top"]
    except (OSError, ValueError, KeyError):
        pass
    if du is None:
        try:
            done = subprocess.run(["du", "-sk", "--max-depth=1", agents_dir], capture_output=True, text=True,
                                  timeout=300, check=False)
            du = done.stdout
        except subprocess.TimeoutExpired:
            return []
    sizes = []
    for line in du.splitlines():
        kib, _, path = line.partition("\t")
        if kib.isdigit() and path.rstrip("/") != agents_dir.rstrip("/"):
            sizes.append((int(kib), os.path.basename(path)))
    top = [f"{name} {kib / 1048576:.1f}G" for kib, name in sorted(sizes, reverse=True)[:count]]
    os.makedirs(os.path.dirname(cache), exist_ok=True)
    with open(cache, "w", encoding="utf-8") as f:
        json.dump({"time": time.time(), "top": top}, f)
    return top


def explain(root, reason):
    """Add the largest /data/hst-agents consumers to a disk refusal."""
    if not reason.startswith("disk"):
        return reason
    top = agents_top(root)
    return reason + ("; largest in /data/hst-agents: " + ", ".join(top) if top else "")
