# SPDX-License-Identifier: AGPL-3.0-only
"""Store of "Phiên bản trước": copies with metadata, no duplicate of the newest copy, the size limit, retention
(10 per file, 30 days, 2 GB overall, oldest first), Vietnamese paths, same names in different folders, the lock
between office processes and recovery from a damaged index."""
import json
import multiprocessing
import os
import tempfile
import time
import unittest
from unittest import mock

import _paths  # noqa: F401 - puts hst_office on sys.path
from hst_office import version_store as vs
from hst_office.version_files import store_lock


class Clock:
    def __init__(self, now=1_800_000_000.0):
        self.now = now

    def __call__(self):
        return self.now


def _read(path):
    with open(path, "rb") as handle:
        return handle.read()


def _write(path, data, mtime=None):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "wb") as handle:
        handle.write(data)
    if mtime is not None:
        os.utime(path, (mtime, mtime))


def _add_many(root, path, count, tag):
    """Child process of the lock test: add `count` different copies to the versions of the shared `path` (each copy
    is staged from a file of this process, so only the store, not the document, is shared)."""
    store = vs.VersionStore(root, lock_timeout=30)
    own = os.path.join(os.path.dirname(path), tag + ".bin")
    for i in range(count):
        _write(own, ("%s-%d" % (tag, i)).encode() * 100, mtime=1_700_000_000 + i)
        assert store.add(path, store.stage(own)) == "stored"


def _hold_lock(root, ready, release):
    with store_lock(root):
        ready.set()
        release.wait(20)


class StoreBase(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = os.path.join(self.tmp.name, "profile", "hst-versions")
        self.docs = os.path.join(self.tmp.name, "docs")
        self.clock = Clock()
        self.store = vs.VersionStore(self.root, clock=self.clock)

    def doc(self, name, data, mtime=1_799_990_000):
        path = os.path.join(self.docs, name)
        _write(path, data, mtime)
        return path


class CopyAndMetadata(StoreBase):
    def test_capture_keeps_bytes_and_metadata(self):
        path = self.doc("Báo cáo.docx", b"version one", mtime=1_799_990_000)
        self.assertEqual(self.store.capture(path), "stored")
        (version,) = self.store.versions(path)
        with open(version.path, "rb") as handle:
            self.assertEqual(handle.read(), b"version one")
        self.assertEqual(version.size, 11)
        self.assertEqual(version.saved, 1_799_990_000)
        self.assertEqual(version.captured, self.clock.now)
        self.assertEqual(version.sha256, vs.file_sha256(path))
        self.assertTrue(version.name.endswith(".docx"))
        self.assertTrue(version.name.startswith("20270115T051320Z-"))  # UTC time of the content
        index = json.loads(_read(os.path.join(self.store.folder(path), vs.INDEX_NAME)))
        self.assertEqual(index["path"], path)
        self.assertEqual(index["versions"][0]["sha256"], version.sha256)

    def test_newest_first_and_identical_content_is_not_stored_twice(self):
        path = self.doc("a.xlsx", b"one")
        self.assertEqual(self.store.capture(path), "stored")
        self.assertEqual(self.store.capture(path), "duplicate")
        _write(path, b"two", mtime=1_799_990_100)
        self.clock.now += 10
        self.assertEqual(self.store.capture(path), "stored")
        _write(path, b"one", mtime=1_799_990_200)  # equal to an older copy, not the newest: kept
        self.clock.now += 10
        self.assertEqual(self.store.capture(path), "stored")
        contents = [_read(v.path) for v in self.store.versions(path)]
        self.assertEqual(contents, [b"one", b"two", b"one"])
        self.assertFalse([n for n in os.listdir(self.store.folder(path)) if n.startswith(vs.STAGING_PREFIX)])

    def test_missing_file_and_size_limit(self):
        with self.assertRaises(FileNotFoundError):
            self.store.capture(os.path.join(self.docs, "chưa có.docx"))
        path = self.doc("big.pptx", b"x" * 2048)
        with self.assertRaises(ValueError):
            self.store.capture(path, max_bytes=1024)
        self.assertEqual(self.store.versions(path), [])
        self.assertEqual(self.store.capture(path, max_bytes=None), "stored")  # restore keeps any size
        self.assertEqual(vs.MAX_FILE_BYTES, 100 * 1024 * 1024)

    def test_vietnamese_paths_and_unicode_forms_are_one_document(self):
        import unicodedata
        path = self.doc(os.path.join("Tài liệu", "Kế hoạch năm 2027.odt"), b"noi dung")
        self.store.capture(path)
        decomposed = unicodedata.normalize("NFD", path)
        self.assertEqual(vs.key_for(decomposed), vs.key_for(path))
        self.assertEqual(len(self.store.versions(decomposed)), 1)

    def test_same_name_in_different_folders_never_mix(self):
        first = self.doc(os.path.join("Phòng A", "Báo cáo.docx"), b"A")
        second = self.doc(os.path.join("Phòng B", "Báo cáo.docx"), b"B")
        self.store.capture(first)
        self.store.capture(second)
        self.assertNotEqual(self.store.folder(first), self.store.folder(second))
        self.assertEqual([_read(v.path) for v in self.store.versions(first)], [b"A"])
        self.assertEqual([_read(v.path) for v in self.store.versions(second)], [b"B"])

    def test_usage_and_clear(self):
        a, b = self.doc("a.odt", b"12345"), self.doc("b.ods", b"123")
        self.store.capture(a)
        self.store.capture(b)
        self.assertEqual(self.store.usage(), (2, 2, 8))
        self.assertEqual(self.store.clear(), 2)
        self.assertEqual(self.store.usage(), (0, 0, 0))
        self.assertEqual(self.store.versions(a), [])
        self.assertTrue(os.path.exists(a) and os.path.exists(b))  # the documents themselves are untouched


class Retention(StoreBase):
    def test_at_most_ten_per_file_oldest_removed(self):
        path = self.doc("hop-dong.docx", b"")
        for i in range(12):
            _write(path, b"content %d" % i, mtime=1_799_000_000 + i)
            self.clock.now += 1
            self.store.capture(path)
        versions = self.store.versions(path)
        self.assertEqual(len(versions), vs.KEEP_PER_FILE)
        self.assertEqual(_read(versions[0].path), b"content 11")
        self.assertEqual(_read(versions[-1].path), b"content 2")
        stored = [n for n in os.listdir(self.store.folder(path)) if vs.VERSION_NAME.match(n)]
        self.assertEqual(len(stored), vs.KEEP_PER_FILE)

    def test_copies_older_than_thirty_days_are_removed(self):
        path = self.doc("cu.xlsx", b"old")
        self.store.capture(path)
        _write(path, b"newer", mtime=1_799_990_500)
        self.clock.now += 20 * 86400
        self.store.capture(path)
        self.clock.now += 11 * 86400  # the first copy is now 31 days old, the second 11
        versions = self.store.versions(path)
        self.assertEqual([_read(v.path) for v in versions], [b"newer"])
        self.clock.now += 20 * 86400
        self.assertEqual(self.store.versions(path), [])
        self.assertFalse(os.path.exists(self.store.folder(path)))

    def test_whole_store_limit_removes_the_oldest_copies_of_any_file(self):
        a, b = self.doc("a.odt", b"a" * 400), self.doc("b.odt", b"b" * 400)
        with mock.patch.object(vs, "MAX_TOTAL_BYTES", 1000):
            self.store.capture(a)
            self.clock.now += 1
            self.store.capture(b)
            _write(a, b"A" * 400, mtime=1_799_990_100)
            self.clock.now += 1
            self.store.capture(a)  # 1200 bytes: the oldest copy (a's first) goes at the next store-wide prune
            self.assertEqual(self.store.usage()[2], 1200)  # a save never pays for reading every index
            self.store.prune()
            self.assertEqual([_read(v.path) for v in self.store.versions(a)], [b"A" * 400])
            self.assertEqual(len(self.store.versions(b)), 1)
            self.assertEqual(self.store.usage()[2], 800)

    def test_limits_match_the_owner_decision(self):
        self.assertEqual((vs.KEEP_PER_FILE, vs.MAX_AGE_SECONDS, vs.MAX_TOTAL_BYTES),
                         (10, 30 * 86400, 2 * 1024 ** 3))

    def test_stale_staging_files_are_removed(self):
        path = self.doc("a.odt", b"x")
        self.store.capture(path)
        folder = self.store.folder(path)
        stale = os.path.join(folder, vs.STAGING_PREFIX + "1-old.tmp")
        fresh = os.path.join(folder, vs.STAGING_PREFIX + "1-new.tmp")
        _write(stale, b"s", mtime=self.clock.now - 2 * 86400)
        _write(fresh, b"s", mtime=self.clock.now)
        self.store.prune()
        self.assertFalse(os.path.exists(stale))
        self.assertTrue(os.path.exists(fresh))  # may belong to a copy still running in another office process


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
