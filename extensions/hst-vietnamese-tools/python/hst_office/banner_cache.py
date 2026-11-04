# SPDX-License-Identifier: AGPL-3.0-only
"""Verified profile cache with atomic publication and a cross-process 24-hour attempt stamp."""
import base64
import json
import os
from pathlib import Path
import tempfile

from .banner_schema import INTERVAL, MAX_IMAGE, MAX_MANIFEST
from .banner_verify import verify_image, verify_manifest


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


def cached_image(root, spec):
    for suffix in (".png", ".jpg", ".webp"):
        path = image_path(root, spec, suffix)
        if path.is_file() and verify_image(read_bounded(path, MAX_IMAGE), spec) == suffix:
            return str(path)
    raise ValueError("missing banner image")


def load(root, key, name="current.json"):
    envelope = json.loads(read_bounded(Path(root) / name, 2 * MAX_MANIFEST))
    data = base64.b64decode(envelope["manifest"], validate=True)
    doc = verify_manifest(data, envelope["signature"], key)
    paths = {i["id"]: {scale: cached_image(root, spec) for scale, spec in i["image"].items()} for i in doc["items"]}
    return doc, paths


def publish(root, data, signature, doc, paths):
    """All images must already be verified and installed before the manifest becomes visible."""
    root = Path(root)
    keep = {Path(p).name for scales in paths.values() for p in scales.values()}
    try:  # Keep the prior generation's images while widgets finish drawing their current snapshot.
        previous_bytes = read_bounded(root / "current.json", 2 * MAX_MANIFEST)
        old = json.loads(previous_bytes)
        previous = json.loads(base64.b64decode(old["manifest"], validate=True))
        for item in previous["items"]:
            for spec in item["image"].values():
                keep.update(spec["sha256"] + ext for ext in (".png", ".jpg", ".webp"))
        atomic_write(root / "previous.json", previous_bytes)
    except (OSError, ValueError, KeyError, TypeError):
        pass
    envelope = {"manifest": base64.b64encode(data).decode("ascii"), "signature": signature.decode("ascii")}
    atomic_write(root / "current.json", json.dumps(envelope).encode("utf-8"))
    for path in (root / "images").glob("*"):
        if path.name not in keep and path.is_file():
            try:
                path.unlink()
            except OSError:
                pass  # cleanup must never invalidate an already committed generation


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
