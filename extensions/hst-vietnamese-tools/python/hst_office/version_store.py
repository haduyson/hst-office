# SPDX-License-Identifier: AGPL-3.0-only
"""Store of "Phiên bản trước": copies of a file as it was on disk just before a save overwrote it.

Layout under the user profile (<profile>/user/hst-versions, version_config.store): one folder per document, named by the
SHA-1 of its normalized full path (same names in different folders never mix), holding the copies
"<UTC time of the content>-<sha256[:8]><ext>" and index.json (version_index). Copies never leave the machine.

Rules (owner decision, plans/261112-1159-previous-versions): at most KEEP_PER_FILE copies per document and none older
than MAX_AGE_SECONDS; the whole store at most MAX_TOTAL_BYTES, the oldest copies of any document go first. Files over
MAX_FILE_BYTES are not copied. A copy equal (SHA-256) to the newest copy of the same document is not stored again.

Every change of an index or a copy happens under one store-wide OS lock (store.lock, bounded wait, released by the
kernel when a process dies) and is written to a temporary file then renamed, so another office process, a crash or a
full disk leaves either the old or the new state. Copying the document (stage) runs outside the lock, into a
".staging-*" file of its folder, so a slow disk never holds the lock. Pure Python (tests/unit/test_version_store.py).
"""
import os
import re
import shutil
import time
import uuid

# Cancelled, Changed and StoreBusy are raised from here too; callers catch them from this module
from .version_files import (LOCK_TIMEOUT, Cancelled, Changed, Staged, StoreBusy, file_sha256,  # noqa: F401
                            hash_copy, key_for, remove_quietly, store_lock, utc_stamp)
from .version_index import INDEX_NAME, VERSION_NAME, Version, read_index, write_index  # noqa: F401

MAX_FILE_BYTES = 100 * 1024 * 1024
KEEP_PER_FILE = 10
MAX_AGE_SECONDS = 30 * 86400
MAX_TOTAL_BYTES = 2 * 1024 * 1024 * 1024
STAGING_PREFIX = ".staging-"
STALE_STAGING_SECONDS = 86400  # a staging file this old belongs to no running copy (office killed mid-copy)
EXTENSION = re.compile(r"^\.[A-Za-z0-9]{1,10}$")


class VersionStore:
    def __init__(self, root, clock=time.time, lock_timeout=LOCK_TIMEOUT):
        self.root, self.clock, self.lock_timeout = root, clock, lock_timeout

    def folder(self, path):
        return os.path.join(self.root, key_for(path))

    def _lock(self):
        return store_lock(self.root, self.lock_timeout)

    # -- index -------------------------------------------------------------------------------------------------------
    # -- reading -----------------------------------------------------------------------------------------------------
    def versions(self, path):
        """Stored copies of `path`, newest first (expired ones are removed first)."""
        folder = self.folder(path)
        if not os.path.isdir(folder):
            return []
        with self._lock():
            return [Version(folder, e) for e in self._prune_folder_locked(folder, self.clock(), path)]

    def usage(self):
        """(number of documents, number of copies, bytes) of the whole store."""
        documents = copies = total = 0
        if not os.path.isdir(self.root):
            return 0, 0, 0
        with self._lock():
            for folder in self._folders():
                entries = read_index(folder)["versions"]
                if entries:
                    documents += 1
                    copies += len(entries)
                    total += sum(int(e["size"]) for e in entries)
        return documents, copies, total

    def _folders(self):
        try:
            names = os.listdir(self.root)
        except FileNotFoundError:
            return []
        return [os.path.join(self.root, n) for n in names
                if re.match(r"^[0-9a-f]{40}$", n) and os.path.isdir(os.path.join(self.root, n))]

    # -- copying -----------------------------------------------------------------------------------------------------
    def stage(self, path, cancel=None, deadline=None, max_bytes=MAX_FILE_BYTES):
        """Copy the document file as it is now into a staging file (outside the lock). Raises FileNotFoundError,
        Cancelled, Changed, or ValueError when the file is larger than `max_bytes` (None: no limit)."""
        before = os.stat(path)
        if max_bytes is not None and before.st_size > max_bytes:
            raise ValueError("too large")
        folder = self.folder(path)
        os.makedirs(folder, exist_ok=True)
        target = os.path.join(folder, "%s%d-%s.tmp" % (STAGING_PREFIX, os.getpid(), uuid.uuid4().hex))
        size, sha256 = hash_copy(path, target, cancel, deadline)
        after = os.stat(path)
        if (after.st_size, after.st_mtime_ns) != (before.st_size, before.st_mtime_ns) or size != before.st_size:
            remove_quietly(target)
            raise Changed()
        return Staged(target, size, before.st_mtime_ns, sha256)

    def add(self, path, staged):
        """Store a staged copy of `path`: "stored", or "duplicate" when it equals the newest copy (staged file removed)."""
        try:
            with self._lock():
                folder = self.folder(path)
                if not os.path.exists(staged.path):
                    return "failed"  # the store was emptied while the copy ran
                doc = read_index(folder, path)
                if doc["versions"] and doc["versions"][0]["sha256"] == staged.sha256:
                    return "duplicate"
                saved = staged.mtime_ns / 1e9
                ext = os.path.splitext(path)[1]
                ext = ext if EXTENSION.match(ext) else ""
                base = "%s-%s" % (utc_stamp(saved), staged.sha256[:8])
                name, n = base + ext, 1
                while os.path.exists(os.path.join(folder, name)):
                    n += 1
                    name = "%s-%d%s" % (base, n, ext)
                os.makedirs(folder, exist_ok=True)
                os.replace(staged.path, os.path.join(folder, name))
                doc["path"] = path
                doc["versions"].insert(0, {"file": name, "saved": saved, "captured": self.clock(),
                                           "size": staged.size, "sha256": staged.sha256})
                write_index(folder, doc)
                self._prune_folder_locked(folder, self.clock(), path)  # the store-wide limit: prune(), off this path
                return "stored"
        finally:
            staged.discard()  # no-op once renamed into the store

    def capture(self, path, cancel=None, deadline=None, max_bytes=MAX_FILE_BYTES):
        """Copy the file as it is now and store it (stage + add)."""
        return self.add(path, self.stage(path, cancel, deadline, max_bytes))

    # -- clean-up ----------------------------------------------------------------------------------------------------
    def prune(self):
        with self._lock():
            self._prune_locked()

    def _prune_folder_locked(self, folder, now, path=None):
        """KEEP_PER_FILE / MAX_AGE_SECONDS for one document, and staging files of copies that never finished.
        Returns the entries kept."""
        doc = read_index(folder, path)
        keep = [e for e in doc["versions"] if now - float(e["captured"]) <= MAX_AGE_SECONDS][:KEEP_PER_FILE]
        if len(keep) != len(doc["versions"]):
            for entry in doc["versions"]:
                if entry not in keep:
                    remove_quietly(os.path.join(folder, entry["file"]))
            doc["versions"] = keep
            write_index(folder, doc)
        for name in os.listdir(folder) if os.path.isdir(folder) else ():
            full = os.path.join(folder, name)
            if name.startswith((STAGING_PREFIX, ".tmp-")):
                try:
                    if now - os.stat(full).st_mtime > STALE_STAGING_SECONDS:
                        remove_quietly(full)
                except OSError:
                    pass
        return keep

    def _prune_locked(self):
        """Every document's own limits, then MAX_TOTAL_BYTES over the store (oldest copies of any document first).
        Reads every index, so it runs off the save path (version_capture.prune_soon)."""
        now = self.clock()
        everything = []  # (captured, size, folder, file)
        for folder in self._folders():
            keep = self._prune_folder_locked(folder, now)
            everything += [(float(e["captured"]), int(e["size"]), folder, e["file"]) for e in keep]
        total = sum(size for _, size, _, _ in everything)
        if total <= MAX_TOTAL_BYTES:
            return
        drop = {}
        for captured, size, folder, name in sorted(everything):
            if total <= MAX_TOTAL_BYTES:
                break
            drop.setdefault(folder, set()).add(name)
            total -= size
        for folder, names in drop.items():
            doc = read_index(folder)
            for name in names:
                remove_quietly(os.path.join(folder, name))
            doc["versions"] = [e for e in doc["versions"] if e["file"] not in names]
            write_index(folder, doc)

    def clear(self):
        """Delete every stored copy of every document. Returns the number of copies deleted."""
        if not os.path.isdir(self.root):
            return 0
        count = 0
        with self._lock():
            for folder in self._folders():
                try:
                    count += len(read_index(folder)["versions"])
                except OSError:
                    pass
                shutil.rmtree(folder, ignore_errors=True)
        return count
