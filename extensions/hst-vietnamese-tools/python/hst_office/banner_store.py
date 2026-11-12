# SPDX-License-Identifier: AGPL-3.0-only
"""Signed metadata ordering and last-eligible fallback, atomically committed under an OS lock."""
import base64
from contextlib import contextmanager
import json
import os
from pathlib import Path

from . import banner_cache as cache
from .banner_schema import MAX_MANIFEST, active, image_specs
from .banner_verify import verify_image, verify_manifest

LIMIT = 6 * MAX_MANIFEST  # current signed envelope plus one last-eligible signed envelope


@contextmanager
def publication_lock(root, name="publish.lock"):
    """Kernel releases this lock on exit/crash; never expire a lock held by a suspended publisher.

    name: publish.lock for the feed; impressions.lock for the local display counts (banner_impressions)."""
    root = Path(root)
    root.mkdir(parents=True, exist_ok=True)
    with open(root / name, "a+b") as handle:
        if os.name == "nt":
            import msvcrt
            if handle.tell() == 0:
                handle.write(b"\0")
                handle.flush()
            handle.seek(0)
            msvcrt.locking(handle.fileno(), msvcrt.LK_LOCK, 1)
        else:
            import fcntl
            fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
        try:
            yield
        finally:
            if os.name == "nt":
                handle.seek(0)
                msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                fcntl.flock(handle.fileno(), fcntl.LOCK_UN)


def envelope(data, signature):
    return {"manifest": base64.b64encode(data).decode("ascii"), "signature": signature.decode("ascii")}


def metadata(root, key, allow_test=False):
    """Recover the ordering floor from authenticated metadata even if every image is missing."""
    records = []
    for name in ("current.json", "previous.json"):
        try:
            value = json.loads(cache.read_bounded(Path(root) / name, LIMIT))
        except (OSError, ValueError):
            continue
        for entry in (value, value.get("fallback") if isinstance(value, dict) else None):
            try:
                data = base64.b64decode(entry["manifest"], validate=True)
                doc = verify_manifest(data, entry["signature"], key, allow_test)
                record = (doc, data, entry["signature"].encode("ascii"))
                if record not in records:
                    records.append(record)
            except (ValueError, KeyError, TypeError):
                continue
    return sorted(records, key=lambda r: r[0]["generatedAt"], reverse=True)


def images(root, doc):
    return {i["id"]: {s: cache.cached_image(root, spec, s) for s, spec in image_specs(i)}
            for i in doc["items"]}


def load(root, key, allow_test=False):
    candidates = []
    for doc, _, _ in metadata(root, key, allow_test):
        try:
            candidates.append((doc, images(root, doc)))
        except (OSError, ValueError):
            continue
    return tuple(candidates)


def check_generation(records, doc, data):
    if records:
        floor = records[0][0]["generatedAt"]
        if doc["generatedAt"] < floor:
            raise ValueError("older banner generation")
        if any(d["generatedAt"] == doc["generatedAt"] and raw != data for d, raw, _ in records):
            raise ValueError("conflicting banner generation")


def publish(root, key, data, signature, blobs, now, version, allow_test=False):
    root = Path(root)
    doc = verify_manifest(data, signature, key, allow_test)
    with publication_lock(root):
        records = metadata(root, key, allow_test)  # Compare again AFTER downloads, under the publication lock.
        check_generation(records, doc, data)
        current = envelope(data, signature)
        fallback = None
        for old, raw, sig in records:
            if raw != data and any(active(i, now, version) for i in old["items"]):
                try:
                    images(root, old)
                    fallback = (old, raw, sig)
                    current["fallback"] = envelope(raw, sig)
                    break
                except (OSError, ValueError):
                    pass
        for item in doc["items"]:
            for scale, spec in image_specs(item):
                blob = blobs[item["id"]][scale]
                suffix = verify_image(blob, spec, scale)
                cache.atomic_write(cache.image_path(root, spec, suffix), blob)
        # A single atomic current envelope commits both the floor and the eligible fallback.
        # An identical poll must not rotate away the previous eligible campaign.
        previous = next((r for r in records if r[1] != data), None)
        if records and records[0][1] != data:
            cache.atomic_write(root / "previous.json", json.dumps(envelope(records[0][1], records[0][2])).encode())
            previous = records[0]
        cache.atomic_write(root / "current.json", json.dumps(current).encode())
        keep_docs = [doc] + [r[0] for r in (fallback, previous) if r]
        keep = {spec["sha256"] + ext for d in keep_docs for i in d["items"] for _, spec in image_specs(i)
                for ext in (".png", ".jpg", ".webp")}
        for path in (root / "images").glob("*"):
            if path.name not in keep and path.is_file():
                try:
                    path.unlink()
                except OSError:
                    pass
        return load(root, key, allow_test)
