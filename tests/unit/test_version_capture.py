# SPDX-License-Identifier: AGPL-3.0-only
"""When "Phiên bản trước" copies a file: in the background once the document is modified, kept at OnSave before
the office writes; a bounded wait otherwise; skipped for a new file, a file over 100 MB, or with the feature off.
A failure never reaches the save."""
import os
import tempfile
import threading
import time
import unittest
from unittest import mock

import install_id_support  # noqa: F401 - UNO stubs before any hst_office import
from hst_office import version_capture as vc
from hst_office import version_job
from hst_office import version_store as vs


def _write(path, data, mtime):
    with open(path, "wb") as handle:
        handle.write(data)
    os.utime(path, (mtime, mtime))


def _read(path):
    with open(path, "rb") as handle:
        return handle.read()


class SlowStore(vs.VersionStore):
    """A store whose background copy never finishes until it is cancelled (a hung network drive)."""

    def __init__(self, root):
        super().__init__(root)
        self.started = threading.Event()

    def stage(self, path, cancel=None, deadline=None, max_bytes=vs.MAX_FILE_BYTES):
        if cancel is None:  # the copy OnSave would make itself: just as slow
            raise vs.Cancelled()
        self.started.set()
        while not cancel.is_set():
            time.sleep(0.01)
        raise vs.Cancelled()


class Capture(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = os.path.join(tmp.name, "hst-versions")
        self.store = vs.VersionStore(self.root)
        self.path = os.path.join(tmp.name, "Tờ trình.docx")
        _write(self.path, b"on disk before the save", 1_700_000_000)
        self.addCleanup(vc._PENDING.clear)

    def save_over(self, data, mtime=1_700_000_100):
        """What the office does right after OnSave."""
        _write(self.path, data, mtime)

    def wait_staged(self):
        pending = vc._PENDING[vs.key_for(self.path)]
        pending.thread.join(10)
        return pending

    def test_modified_then_saved_keeps_the_bytes_that_were_overwritten_without_copying_at_save(self):
        self.assertEqual(vc.prepare(self.store, self.path), "started")
        self.assertEqual(vc.prepare(self.store, self.path), "pending")  # a second change: nothing new
        self.wait_staged()
        with mock.patch.object(self.store, "capture", side_effect=AssertionError("copied at save")):
            self.assertEqual(vc.before_save(self.store, self.path), "stored")
        self.save_over(b"new content")
        (version,) = self.store.versions(self.path)
        self.assertEqual(_read(version.path), b"on disk before the save")
        self.assertEqual(vc._PENDING, {})

    def test_a_stored_copy_starts_the_store_wide_prune_in_the_background(self):
        with mock.patch.object(vc, "prune_soon") as prune:
            self.assertEqual(vc.before_save(self.store, self.path), "stored")
            prune.assert_called_once_with(self.store)
            self.assertEqual(vc.before_save(self.store, self.path), "duplicate")
            prune.assert_called_once()
        with mock.patch.object(self.store, "prune") as prune:
            vc.prune_soon(self.store).join(5)
            prune.assert_called_once()

    def test_save_without_a_staged_copy_copies_within_the_wait(self):
        self.assertEqual(vc.before_save(self.store, self.path), "stored")
        self.assertEqual(vc.before_save(self.store, self.path), "duplicate")
        self.assertEqual(len(self.store.versions(self.path)), 1)

    def test_file_changed_after_staging_is_copied_again(self):
        vc.prepare(self.store, self.path)
        stale = self.wait_staged().staged.path
        _write(self.path, b"changed by another program", 1_700_000_050)
        self.assertEqual(vc.before_save(self.store, self.path), "stored")
        self.assertEqual(_read(self.store.versions(self.path)[0].path), b"changed by another program")
        self.assertFalse(os.path.exists(stale))

    def test_new_file_and_large_file_are_skipped(self):
        missing = os.path.join(os.path.dirname(self.path), "Mới.docx")
        self.assertEqual(vc.prepare(self.store, missing), "missing")
        self.assertEqual(vc.before_save(self.store, missing), "missing")
        self.assertEqual(vc.prepare(self.store, self.path, max_bytes=4), "too-large")
        self.assertEqual(vc.before_save(self.store, self.path, max_bytes=4), "too-large")
        self.assertEqual(self.store.versions(self.path), [])

    def test_hung_copy_costs_at_most_the_wait_and_leaves_nothing(self):
        store = SlowStore(self.root)
        vc.prepare(store, self.path)
        self.assertTrue(store.started.wait(5))
        started = time.monotonic()
        self.assertEqual(vc.before_save(store, self.path, wait=0.3), "timeout")
        self.assertLess(time.monotonic() - started, 2.0)
        self.assertEqual(vc._PENDING, {})

    def test_failures_become_a_status(self):
        with mock.patch.object(self.store, "capture", side_effect=vs.StoreBusy()):
            self.assertEqual(vc.before_save(self.store, self.path), "busy")
        with mock.patch.object(self.store, "capture", side_effect=vs.Changed()):
            self.assertEqual(vc.before_save(self.store, self.path), "changed")
        with mock.patch.object(self.store, "capture", side_effect=PermissionError("denied")), \
                mock.patch("hst_office.diag_log.exception"):
            self.assertEqual(vc.before_save(self.store, self.path), "failed")

    def test_closing_the_document_drops_its_staged_copy(self):
        vc.prepare(self.store, self.path)
        staged = self.wait_staged().staged.path
        vc.discard(self.path)
        self.assertFalse(os.path.exists(staged))
        self.assertEqual(vc._PENDING, {})


class Job(unittest.TestCase):
    """version_job.handle: which event does what, and the feature switch."""

    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.store = vs.VersionStore(os.path.join(tmp.name, "hst-versions"))
        self.path = os.path.join(tmp.name, "Quyết định.odt")
        _write(self.path, b"saved earlier", 1_700_000_000)
        self.model = mock.Mock()
        self.model.isModified.return_value = True
        self.addCleanup(vc._PENDING.clear)
        for target, value in (("hst_office.version_config.store", lambda ctx: self.store),
                              ("hst_office.version_config.document_path", lambda model: self.path)):
            patcher = mock.patch(target, value)
            patcher.start()
            self.addCleanup(patcher.stop)

    def enabled(self, value):
        patcher = mock.patch("hst_office.version_config.enabled", lambda ctx: value)
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_events(self):
        self.enabled(True)
        self.assertEqual(version_job.handle(None, "OnModifyChanged", self.model), "started")
        vc._PENDING[vs.key_for(self.path)].thread.join(10)
        self.assertEqual(version_job.handle(None, "OnSave", self.model), "stored")
        self.model.isModified.return_value = False
        self.assertIsNone(version_job.handle(None, "OnModifyChanged", self.model))  # back to unmodified after a save
        self.assertEqual(version_job.handle(None, "OnUnload", self.model), "discarded")
        self.assertIsNone(version_job.handle(None, "OnSaveAs", self.model))
        self.assertEqual(len(self.store.versions(self.path)), 1)

    def test_feature_off_copies_nothing(self):
        self.enabled(False)
        self.assertEqual(version_job.handle(None, "OnModifyChanged", self.model), "disabled")
        self.assertEqual(version_job.handle(None, "OnSave", self.model), "disabled")
        self.assertEqual(self.store.versions(self.path), [])
        self.assertEqual(vc._PENDING, {})

    def test_document_without_a_file_is_ignored(self):
        self.enabled(True)
        with mock.patch("hst_office.version_config.document_path", lambda model: None):
            self.assertIsNone(version_job.handle(None, "OnSave", self.model))

    def test_execute_never_raises(self):
        job = version_job.PreviousVersionsJob(None)
        with mock.patch.object(version_job, "handle", side_effect=RuntimeError("boom")), \
                mock.patch("hst_office.diag_log.exception") as logged:
            self.assertIsNone(job.execute(()))
        logged.assert_called_once()


if __name__ == "__main__":
    unittest.main()
