# SPDX-License-Identifier: AGPL-3.0-only
""""Phiên bản trước" with AutoSave ("Tự động lưu"): an AutoSave keeps a copy only for the first AutoSave of an opening
or when the newest copy is older than 30 minutes; a save by the user always keeps one. While AutoSave would keep
nothing, OnModifyChanged copies nothing either."""
import os
import tempfile
import time
import unittest
from unittest import mock

import install_id_support  # noqa: F401 - UNO stubs before any hst_office import
from hst_office import version_capture as vc
from hst_office import version_job
from hst_office import version_store as vs


class _Arg:
    def __init__(self, name, value):
        self.Name, self.Value = name, value


class _Model:
    """The model of an open document as the job sees it: modified flag and the AutoSave arguments of sfx2."""

    def __init__(self):
        self.modified = False
        self.autosave = True  # HstUserAutoSave: the toggle is on
        self.autosaving = False  # HstUserAutoSaving: inside an AutoSave store

    def isModified(self):
        return self.modified

    def getArgs2(self, names):
        values = {"HstUserAutoSave": self.autosave, "HstUserAutoSaving": self.autosaving}
        return tuple(_Arg(n, values[n]) for n in names if n in values)


class _OldCoreModel(_Model):
    def getArgs2(self, names):
        raise AttributeError("getArgs2")


class AutoSaveCoalescing(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.now = [time.time()]  # the store compares its clock with real file times (stale staging files)
        self.store = vs.VersionStore(os.path.join(tmp.name, "hst-versions"), clock=lambda: self.now[0])
        self.path = os.path.join(tmp.name, "Hợp đồng.docx")
        self.writes = 0
        self._write()
        self.model = _Model()
        for cleanup in (vc._PENDING.clear, vc._WRITTEN.clear, vc._AUTOSAVED.clear):
            self.addCleanup(cleanup)
        for target, value in (("hst_office.version_config.store", lambda ctx: self.store),
                              ("hst_office.version_config.document_path", lambda model: self.path),
                              ("hst_office.version_config.enabled", lambda ctx: True),
                              ("hst_office.version_capture.time.time", lambda: self.now[0])):
            patcher = mock.patch(target, value)
            patcher.start()
            self.addCleanup(patcher.stop)

    def _write(self):
        self.writes += 1
        with open(self.path, "wb") as handle:
            handle.write(b"content %d" % self.writes)
        stamp = 1_700_000_000 + self.writes
        os.utime(self.path, (stamp, stamp))

    def change(self):
        self.model.modified = True
        outcome = version_job.handle(None, "OnModifyChanged", self.model)
        pending = vc._PENDING.get(vs.key_for(self.path))
        if pending is not None:
            pending.thread.join(10)
        return outcome

    def save(self, auto):
        self.model.autosaving = auto
        outcome = version_job.handle(None, "OnSave", self.model)
        self._write()
        self.model.autosaving = False
        version_job.handle(None, "OnSaveDone", self.model)
        self.model.modified = False
        return outcome

    def copies(self):
        return len(self.store.versions(self.path))

    def test_first_autosave_of_an_opening_keeps_the_file_before_the_session(self):
        self.assertEqual(self.change(), "started")
        self.assertEqual(self.save(auto=True), "stored")
        self.assertEqual(self.copies(), 1)

    def test_autosaves_every_3_minutes_keep_one_copy_per_30_minutes(self):
        outcomes = []
        for _ in range(20):  # one hour of AutoSave every 3 minutes
            self.change()
            outcomes.append(self.save(auto=True))
            self.now[0] += 3 * 60
        self.assertEqual(outcomes.count("stored"), 2)  # the first one, then one 30 minutes later
        self.assertEqual(outcomes[0], "stored")
        self.assertEqual(outcomes[10], "stored")
        self.assertEqual(set(outcomes) - {"stored"}, {"coalesced"})
        self.assertEqual(self.copies(), 2)

    def test_no_background_copy_while_autosave_keeps_nothing(self):
        self.change()
        self.save(auto=True)
        self.now[0] += 3 * 60
        self.assertEqual(self.change(), "coalesced")
        self.assertNotIn(vs.key_for(self.path), vc._PENDING)

    def test_a_save_by_the_user_always_keeps_a_copy(self):
        self.change()
        self.save(auto=True)
        self.now[0] += 60
        self.change()  # coalesced: nothing staged
        self.assertEqual(self.save(auto=False), "stored")  # copied at OnSave instead
        self.assertEqual(self.copies(), 2)

    def test_autosave_off_stages_as_before(self):
        self.change()
        self.save(auto=True)
        self.model.autosave = False  # the user turned the toggle off
        self.now[0] += 60
        self.assertEqual(self.change(), "started")

    def test_a_new_opening_keeps_its_first_autosave_again(self):
        self.change()
        self.save(auto=True)
        version_job.handle(None, "OnUnload", self.model)
        self.now[0] += 5 * 60
        self.change()
        self.assertEqual(self.save(auto=True), "stored")

    def test_an_office_without_autosave_arguments_keeps_every_save(self):
        self.model = _OldCoreModel()
        for _ in range(3):
            self.assertEqual(self.change(), "started")
            self.assertEqual(self.save(auto=False), "stored")
            self.now[0] += 60

    def test_newest_captured(self):
        self.assertIsNone(self.store.newest_captured(self.path))
        self.change()
        self.save(auto=False)
        self.assertEqual(self.store.newest_captured(self.path), self.now[0])


if __name__ == "__main__":
    unittest.main()
