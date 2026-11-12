# SPDX-License-Identifier: AGPL-3.0-only
"""Store of "Phiên bản trước" under stress: recovery from a damaged index and the lock between office processes."""
import json
import multiprocessing
import os
import time
import unittest

import _paths  # noqa: F401 - puts hst_office on sys.path
from hst_office import version_store as vs
from test_version_store import StoreBase, _add_many, _hold_lock, _read, _write


class IndexRecovery(StoreBase):
    def setUp(self):
        super().setUp()
        self.clock.now = time.time()  # a rebuilt entry takes its capture time from the copy's real file time
    def test_damaged_index_is_rebuilt_from_the_copies(self):
        path = self.doc("Biên bản.docx", b"first")
        self.store.capture(path)
        _write(path, b"second", mtime=1_799_990_100)
        self.clock.now += 5
        self.store.capture(path)
        index = os.path.join(self.store.folder(path), vs.INDEX_NAME)
        for damage in (b"{not json", b'{"versions": [{"file": "../../evil"}]}', b"\xff\xfe", b"[]"):
            _write(index, damage)
            versions = self.store.versions(path)
            self.assertEqual(sorted(_read(v.path) for v in versions), [b"first", b"second"])
            self.assertEqual(json.loads(_read(index))["path"], path)
        _write(path, b"second", mtime=1_799_990_200)
        self.assertIn(self.store.capture(path), ("stored", "duplicate"))

    def test_copy_missing_from_the_index_is_kept_and_listed(self):
        path = self.doc("a.odt", b"one")
        self.store.capture(path)
        folder = self.store.folder(path)
        listed = self.store.versions(path)[0].name
        orphan = os.path.join(folder, "20270101T000000Z-0123abcd.odt")
        _write(orphan, b"crashed before the index write")
        os.remove(os.path.join(folder, listed))  # an entry whose copy is gone
        versions = self.store.versions(path)
        self.assertEqual([v.name for v in versions], [os.path.basename(orphan)])
        self.assertEqual(versions[0].sha256, vs.file_sha256(orphan))


class Locking(StoreBase):
    def test_two_processes_adding_at_once_keep_a_consistent_store(self):
        path = self.doc("chung.docx", b"start")
        ctx = multiprocessing.get_context("spawn")
        workers = [ctx.Process(target=_add_many, args=(self.root, path, 6, tag)) for tag in ("p1", "p2")]
        for worker in workers:
            worker.start()
        for worker in workers:
            worker.join(60)
            self.assertEqual(worker.exitcode, 0)
        versions = vs.VersionStore(self.root).versions(path)
        self.assertEqual(len(versions), vs.KEEP_PER_FILE)
        for version in versions:
            self.assertEqual(vs.file_sha256(version.path), version.sha256)
        names = {n for n in os.listdir(self.store.folder(path)) if vs.VERSION_NAME.match(n)}
        self.assertEqual(names, {v.name for v in versions})

    def test_busy_lock_gives_up_after_the_timeout(self):
        ctx = multiprocessing.get_context("spawn")
        ready, release = ctx.Event(), ctx.Event()
        holder = ctx.Process(target=_hold_lock, args=(self.root, ready, release))
        holder.start()
        try:
            self.assertTrue(ready.wait(30))
            path = self.doc("a.odt", b"x")
            started = time.monotonic()
            with self.assertRaises(vs.StoreBusy):
                vs.VersionStore(self.root, lock_timeout=0.3).capture(path)
            self.assertLess(time.monotonic() - started, 5)
            self.assertFalse([n for n in os.listdir(vs.VersionStore(self.root).folder(path))
                              if n.startswith(vs.STAGING_PREFIX)])  # the staged copy is not left behind
        finally:
            release.set()
            holder.join(30)
        self.assertEqual(vs.VersionStore(self.root).capture(path), "stored")


if __name__ == "__main__":
    unittest.main()
