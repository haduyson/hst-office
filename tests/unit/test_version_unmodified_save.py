# SPDX-License-Identifier: AGPL-3.0-only
"""Saving an unmodified document again keeps no new copy when its file is still what this office last wrote (OOXML
and ODF rewrite their save time, so the bytes always differ); a file changed by another program is still kept."""
import os
import tempfile
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


class UnmodifiedSave(unittest.TestCase):
    """The job's event sequence as the office runs it: OnSave (before writing), the write, OnSaveDone."""

    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.dir = tmp.name
        self.store = vs.VersionStore(os.path.join(tmp.name, "hst-versions"))
        self.path = os.path.join(tmp.name, "Báo cáo.docx")
        _write(self.path, b"opened from disk", 1_700_000_000)
        self.model = mock.Mock()
        self.model.isModified.return_value = False
        self.saves = 0
        self.addCleanup(vc._PENDING.clear)
        self.addCleanup(vc._WRITTEN.clear)
        for target, value in (("hst_office.version_config.store", lambda ctx: self.store),
                              ("hst_office.version_config.document_path", lambda model: self.path),
                              ("hst_office.version_config.enabled", lambda ctx: True)):
            patcher = mock.patch(target, value)
            patcher.start()
            self.addCleanup(patcher.stop)

    def save(self, modified=False):
        """One Save: returns the OnSave outcome. Every write has a new save time inside, like OOXML/ODF."""
        self.model.isModified.return_value = modified
        if modified:
            self.assertEqual(version_job.handle(None, "OnModifyChanged", self.model), "started")
            vc._PENDING[vs.key_for(self.path)].thread.join(10)
        outcome = version_job.handle(None, "OnSave", self.model)
        self.saves += 1
        _write(self.path, b"written by the office, save %d" % self.saves, 1_700_000_000 + 100 * self.saves)
        self.assertEqual(version_job.handle(None, "OnSaveDone", self.model), "recorded")
        self.model.isModified.return_value = False
        return outcome

    def versions(self):
        return [_read(v.path) for v in self.store.versions(self.path)]

    def test_unmodified_resave_keeps_no_new_copy(self):
        self.assertEqual(self.save(), "stored")  # first save after opening: no record yet, the file is kept
        self.assertEqual(self.save(), "unchanged")
        self.assertEqual(self.save(), "unchanged")
        self.assertEqual(self.versions(), [b"opened from disk"])

    def test_modified_save_keeps_the_overwritten_file(self):
        self.save()
        self.assertEqual(self.save(modified=True), "stored")
        self.assertEqual(self.versions(), [b"written by the office, save 1", b"opened from disk"])
        self.assertEqual(self.save(), "unchanged")

    def test_unmodified_save_after_an_external_change_keeps_that_file(self):
        self.save()
        _write(self.path, b"edited by another program", 1_700_000_050)
        self.assertEqual(self.save(), "stored")
        self.assertEqual(self.versions()[0], b"edited by another program")
        _write(self.path, b"written by the office, save X", 1_700_000_900)  # same size as save 2, other time
        self.assertEqual(self.save(), "stored")

    def test_save_as_records_only_the_new_file(self):
        self.save()
        old = self.path
        self.path = os.path.join(self.dir, "Báo cáo bản 2.docx")  # Save As: no OnSave, the model now has the new file
        _write(self.path, b"written by save as", 1_700_000_500)
        self.assertEqual(version_job.handle(None, "OnSaveAsDone", self.model), "recorded")
        self.assertEqual(self.save(), "unchanged")
        self.assertEqual(self.store.versions(self.path), [])
        self.path = old  # the old file keeps its own record: another program changes it, then it is reopened
        _write(self.path, b"changed after save as", 1_700_000_600)
        self.assertEqual(self.save(), "stored")

    def test_closing_or_turning_off_forgets_the_record(self):
        self.save()
        self.assertEqual(version_job.handle(None, "OnUnload", self.model), "discarded")
        self.assertEqual(vc._WRITTEN, {})
        self.assertEqual(self.save(), "stored")  # reopened: first save keeps the file again
        with mock.patch("hst_office.version_config.enabled", lambda ctx: False):
            self.assertEqual(version_job.handle(None, "OnSaveDone", self.model), "disabled")
        self.assertEqual(vc._WRITTEN, {})

    def test_record_of_a_missing_file_is_dropped(self):
        self.save()
        os.remove(self.path)
        self.assertEqual(vc.remember(self.path), "missing")
        self.assertEqual(vc._WRITTEN, {})


if __name__ == "__main__":
    unittest.main()
