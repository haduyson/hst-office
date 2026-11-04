# SPDX-License-Identifier: AGPL-3.0-only
"""Verified profile cache with atomic publication and a cross-process 24-hour attempt stamp."""
import os
from pathlib import Path
import tempfile

from .banner_schema import INTERVAL, MAX_IMAGE
from .banner_verify import verify_image


def read_bounded(path, limit):
    with open(path, "rb") as handle:
        data = handle.read(limit + 1)
    if len(data) > limit:
        raise ValueError("banner file too large")
    return data


def atomic_write(path, data):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, name = tempfile.mkstemp(prefix=".banner-", dir=path.parent)
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(name, path)
    finally:
        if os.path.exists(name):
            os.unlink(name)


def image_path(root, spec, suffix):
    return Path(root) / "images" / (spec["sha256"] + suffix)


def cached_image(root, spec, scale=None):
    """Return the exact verified bytes, never a pathname to reopen during native decoding."""
    for suffix in (".png", ".jpg", ".webp"):
        path = image_path(root, spec, suffix)
        if path.is_file():
            data = read_bounded(path, MAX_IMAGE)
            if verify_image(data, spec, scale) == suffix:
                return data
    raise ValueError("missing banner image")


def claim_attempt(root, now):
    """(claimed, next_due). Stamp BEFORE network, including failures; lock shared by all office processes."""
    root = Path(root)
    root.mkdir(parents=True, exist_ok=True)
    lock = root / "attempt.lock"
    try:
        lock.mkdir()
    except FileExistsError:
        # Lock is held only during this tiny file transaction. Recover a crashed writer after 60 seconds.
        try:
            if now - lock.stat().st_mtime > 60:
                lock.rmdir()
        except OSError:
            pass
        return False, now + 60
    try:
        try:
            last = float(read_bounded(root / "last-attempt", 64))
            if 0 <= last and now < last + INTERVAL:
                return False, last + INTERVAL
        except (OSError, ValueError):
            pass
        atomic_write(root / "last-attempt", str(now).encode("ascii"))
        return True, now + INTERVAL
    finally:
        lock.rmdir()
