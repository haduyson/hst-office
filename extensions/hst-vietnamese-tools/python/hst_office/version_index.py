# SPDX-License-Identifier: AGPL-3.0-only
"""index.json of one document's folder in the "Phiên bản trước" store (version_store): read, repair, write.

{"schema": 1, "path": <original path>, "versions": [{"file", "saved", "captured", "size", "sha256"}, ...]}, newest
captured first. A damaged or missing index is rebuilt from the copies; a copy the index does not list (a crash between
its rename and the index write) is added back, so no stored copy is ever lost. Callers hold the store lock.
"""
import json
import os
import re

from .version_files import file_sha256, remove_quietly, stamp_seconds, write_atomic

SCHEMA = 1
INDEX_NAME = "index.json"
VERSION_NAME = re.compile(r"^(\d{8}T\d{6}Z)-([0-9a-f]{8})(?:-\d+)?(\.[A-Za-z0-9]{1,10})?$")


class Version:
    """One stored copy; `saved` is when that content was saved (its file time), `captured` when it was copied here."""

    def __init__(self, folder, entry):
        self.name = entry["file"]
        self.path = os.path.join(folder, self.name)
        self.saved, self.captured = float(entry["saved"]), float(entry["captured"])
        self.size, self.sha256 = int(entry["size"]), entry["sha256"]


def _entry_from_copy(folder, name):
    """Index entry rebuilt from a stored copy: its name holds the content time, its own file time the capture."""
    match = VERSION_NAME.match(name)
    if not match:
        return None
    full = os.path.join(folder, name)
    try:
        return {"file": name, "saved": stamp_seconds(match.group(1)), "captured": os.stat(full).st_mtime,
                "size": os.path.getsize(full), "sha256": file_sha256(full)}
    except (OSError, ValueError):
        return None


def read_index(folder, path=None):
    """Valid index of `folder` ({"path", "versions": newest captured first}). A damaged or missing index is
    rebuilt from the copies, entries whose copy is gone are dropped, and a copy the index does not list (a crash
    between the rename and the index write) is added back, so no stored copy is ever lost. Caller holds the lock."""
    index_path = os.path.join(folder, INDEX_NAME)
    dirty = False
    try:
        with open(index_path, "rb") as handle:
            doc = json.loads(handle.read().decode("utf-8"))
        entries = [dict(e) for e in doc["versions"]]
        for entry in entries:
            if not VERSION_NAME.match(entry["file"]) or int(entry["size"]) < 0 \
                    or not re.match(r"^[0-9a-f]{64}$", entry["sha256"]):
                raise ValueError("bad entry")
            float(entry["saved"]), float(entry["captured"])
        doc = {"schema": SCHEMA, "path": str(doc.get("path") or ""), "versions": entries}
    except FileNotFoundError:
        doc = {"schema": SCHEMA, "path": "", "versions": []}
    except (ValueError, KeyError, TypeError, AttributeError, UnicodeDecodeError):
        doc, dirty = {"schema": SCHEMA, "path": "", "versions": []}, True
    names = set(os.listdir(folder)) if os.path.isdir(folder) else set()
    kept = [e for e in doc["versions"] if e["file"] in names]
    dirty |= len(kept) != len(doc["versions"])
    listed = {e["file"] for e in kept}
    for name in sorted(names - listed):
        entry = _entry_from_copy(folder, name)
        if entry:
            kept.append(entry)
            dirty = True
    if path and not doc["path"]:  # an index rebuilt without knowing the document learns its path
        doc["path"], dirty = path, dirty or bool(kept)
    kept.sort(key=lambda e: float(e["captured"]), reverse=True)
    doc["versions"] = kept
    if dirty:
        write_index(folder, doc)
    return doc


def write_index(folder, doc):
    if not doc["versions"]:
        remove_quietly(os.path.join(folder, INDEX_NAME))
        try:
            os.rmdir(folder)  # only when no staging file of a running copy is left in it
        except OSError:
            pass
        return
    os.makedirs(folder, exist_ok=True)
    write_atomic(os.path.join(folder, INDEX_NAME),
                 json.dumps(doc, ensure_ascii=False, indent=1, sort_keys=True).encode("utf-8"))
