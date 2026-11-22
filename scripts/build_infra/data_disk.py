# SPDX-License-Identifier: LicenseRef-HST-Proprietary
# Copyright (C) 2026 HASON TECH
"""Early warning when the dev server's /data (the disk of the build queue) runs low.

Below data_warn_free_gib (25) the dispatcher writes a warning to its journal and alerts.log at most once an hour, and
`build-queue.sh list` prints it to every agent that looks at the queue. That is well above the levels where things
break (retention pressure at retention_pressure_free_gib, builds refused at 15-17 GiB), so there is time to clean up.
The largest /data directories are measured with du in a background thread (it can take minutes) and logged when
known; the dispatch loop never waits for it.
"""
import json
import os
import subprocess
import threading
import time

from .queue_retention import free_gib

WARN_EVERY = 3600
_STATE = {"warned": 0.0, "du_running": False}


def warning(store, cfg, free=None):
    """The warning line, or None when there is enough space."""
    free = free_gib(store.root) if free is None else free
    limit = cfg.get("data_warn_free_gib", 25)
    if free >= limit:
        return None
    mount = _mount_point(store.root)
    return (f"WARNING {mount}: {free:.1f} GiB free (< {limit} GiB) on the build queue's disk; free space now: "
            f"`build-queue.sh retention --dry-run`, your own /data/hst-agents/<name> trees, `du -xh -d1 {mount}`")


def check(store, cfg, log, now=None, free=None, top=None):
    """Dispatcher step. top: callable returning the largest directories (tests); default du in a thread."""
    now = time.time() if now is None else now
    line = warning(store, cfg, free)
    if line is None or now - _STATE["warned"] < WARN_EVERY:
        return None
    _STATE["warned"] = now
    _alert(store, line, log)
    if top is not None:
        _alert(store, f"largest in {_mount_point(store.root)}: {', '.join(top())}", log)
    elif not _STATE["du_running"]:
        _STATE["du_running"] = True
        threading.Thread(target=_du_and_alert, args=(store, log), daemon=True).start()
    return line


def _alert(store, msg, log):
    log(msg)
    with open(os.path.join(store.root, "alerts.log"), "a", encoding="utf-8") as f:
        f.write(f"{time.strftime('%F %T')} {msg}\n")


def _du_and_alert(store, log):
    try:
        mount = _mount_point(store.root)
        top = largest_dirs(mount)
        if top:
            _alert(store, f"largest in {mount}: {', '.join(top)}", log)
        with open(os.path.join(store.root, "data-disk.json"), "w", encoding="utf-8") as f:
            json.dump({"time": time.time(), "mount": mount, "top": top}, f)
    except Exception as exc:  # noqa: BLE001 - a background measurement must never take the dispatcher down
        log(f"measuring {store.root}'s disk failed: {exc!r}")
    finally:
        _STATE["du_running"] = False


def largest_dirs(mount, count=6, timeout=900, du_output=None):
    """["name 12.3G", ...] of the largest directories directly under mount (one filesystem only)."""
    if du_output is None:
        try:
            done = subprocess.run(["du", "-xk", "-d1", mount], capture_output=True, text=True, timeout=timeout,
                                  check=False)
        except subprocess.TimeoutExpired:
            return []
        du_output = done.stdout
    sizes = []
    for line in du_output.splitlines():
        kib, _, path = line.partition("\t")
        if kib.isdigit() and path.rstrip("/") != mount.rstrip("/"):
            sizes.append((int(kib), path))
    return [f"{path} {kib / 1048576:.1f}G" for kib, path in sorted(sizes, reverse=True)[:count]]


def _mount_point(path):
    path = os.path.realpath(path)
    while not os.path.ismount(path) and path != os.path.dirname(path):
        path = os.path.dirname(path)
    return path
