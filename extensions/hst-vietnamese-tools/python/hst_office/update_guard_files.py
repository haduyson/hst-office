# SPDX-License-Identifier: LicenseRef-HST-Proprietary
# Copyright (C) 2026 HASON TECH
"""The two small files of the update start-up guard (update_guard), in the update cache:

- updating.lock: written by update_install before it starts the external helper, removed by the helper when it ends;
- version-reopen.json: the last reopen of a replaced macOS bundle, so the same reopen is not repeated in a loop.

Both are bounded, regular-file-only JSON records; nothing leaves this machine.
"""
import json
import os
import stat
import time

from . import diag_log

LOCK_NAME = "updating.lock"  # removed by the helper (update_helper_scripts.SETUP / update_helper_scripts_windows)
REOPEN_NAME = "version-reopen.json"
MAX_SIZE = 1024
REOPEN_PAUSE = 10 * 60


def _write_json(path, record):
    temp = "%s.%d.tmp" % (path, os.getpid())
    with open(temp, "w", encoding="ascii") as handle:
        json.dump(record, handle)
    os.replace(temp, path)


def _read_json(path):
    try:
        descriptor = os.open(path, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0))
        with os.fdopen(descriptor, "rb") as handle:
            raw = handle.read(MAX_SIZE + 1) if stat.S_ISREG(os.fstat(handle.fileno()).st_mode) else b""
        record = json.loads(raw.decode("ascii")) if 0 < len(raw) <= MAX_SIZE else None
    except FileNotFoundError:
        return None
    except (OSError, ValueError):
        record = None
    return record if isinstance(record, dict) else {}


def _positive(value):
    return type(value) is int and 0 < value <= 2147483647


def write_lock(cache, helper=0, office=None, now=None):
    """Write updating.lock (atomic rename); helper 0 means "being started"."""
    if not (helper == 0 or _positive(helper)):
        raise ValueError("helper must be a process ID or 0")
    os.makedirs(cache, mode=0o700, exist_ok=True)
    record = {"schema": 1, "helper": helper, "office": os.getpid() if office is None else office,
              "time": int(time.time() if now is None else now)}
    _write_json(os.path.join(cache, LOCK_NAME), record)


def remove_lock(cache):
    try:
        os.unlink(os.path.join(cache, LOCK_NAME))
    except FileNotFoundError:
        pass


def read_lock(cache):
    """The lock as a dict, None when there is none, {} when it is not valid."""
    record = _read_json(os.path.join(cache, LOCK_NAME))
    if not record:
        return record
    valid = record.get("schema") == 1 and (record.get("helper") == 0 or _positive(record.get("helper"))) \
        and _positive(record.get("office")) and type(record.get("time")) is int
    return record if valid else {}


def reopen_due(cache, running, disk, now=None):
    """True unless this office already reopened for the same versions within REOPEN_PAUSE; records the attempt."""
    now = int(time.time() if now is None else now)
    path = os.path.join(cache, REOPEN_NAME)
    last = _read_json(path) or {}
    if last.get("running") == running and last.get("disk") == disk and type(last.get("time")) is int \
            and 0 <= now - last["time"] < REOPEN_PAUSE:
        return False
    try:
        os.makedirs(cache, mode=0o700, exist_ok=True)
        _write_json(path, {"running": running, "disk": disk, "time": now})
    except OSError:
        diag_log.exception("update_guard")
    return True
