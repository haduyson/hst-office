# SPDX-License-Identifier: AGPL-3.0-only
"""Khôi phục and Mở xem of "Phiên bản trước": the current file is stored before it is replaced, a failure at any
step leaves the file as it was, the document is closed before and opened again after, and Mở xem opens a read-only
copy named after the file and the version's time."""
import os
import tempfile
import time
import unittest
from unittest import mock

import install_id_support  # noqa: F401 - UNO stubs before any hst_office import
from hst_office import version_dialog as dialog
from hst_office import version_restore as vr
from hst_office import version_store as vs


def _write(path, data, mtime):
    with open(path, "wb") as handle:
        handle.write(data)
    os.utime(path, (mtime, mtime))


def _read(path):
    with open(path, "rb") as handle:
        return handle.read()


class Base(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.tmp = tmp.name
        self.store = vs.VersionStore(os.path.join(tmp.name, "hst-versions"))
        self.path = os.path.join(tmp.name, "Hồ sơ", "Kế hoạch.docx")
        os.makedirs(os.path.dirname(self.path))
        _write(self.path, b"version 1", 1_700_000_000)
        self.store.capture(self.path)
        _write(self.path, b"version 2 (current)", 1_700_000_500)
        self.old = self.store.versions(self.path)[0]

    def leftovers(self):
        return [n for n in os.listdir(os.path.dirname(self.path)) if n.startswith(".~hst-restore-")]


class FileSteps(Base):
    def test_restore_stores_the_current_file_first_then_replaces_it(self):
        self.assertEqual(vr.keep_current(self.store, self.path), "stored")
        staged = vr.stage_restore(self.old, self.path)
        self.assertEqual(os.path.dirname(staged), os.path.dirname(self.path))  # same folder: atomic rename
        vr.replace(staged, self.path)
        self.assertEqual(_read(self.path), b"version 1")
        contents = [_read(v.path) for v in self.store.versions(self.path)]
        self.assertEqual(contents, [b"version 2 (current)", b"version 1"])
        self.assertEqual(self.leftovers(), [])

    def test_current_file_that_cannot_be_kept_stops_the_restore(self):
        with mock.patch.object(self.store, "capture", side_effect=OSError("disk full")):
            with self.assertRaises(vr.RestoreError) as caught:
                vr.keep_current(self.store, self.path)
        self.assertEqual(caught.exception.code, "keep")
        with mock.patch.object(self.store, "capture", side_effect=vs.StoreBusy()):
            with self.assertRaises(vr.RestoreError) as caught:
                vr.keep_current(self.store, self.path)
        self.assertEqual(caught.exception.code, "busy")
        os.remove(self.path)
        self.assertEqual(vr.keep_current(self.store, self.path), "missing")  # deleted outside: nothing to keep

    def test_missing_or_damaged_version(self):
        with open(self.old.path, "ab") as handle:
            handle.write(b"bit rot")
        with self.assertRaises(vr.RestoreError) as caught:
            vr.stage_restore(self.old, self.path)
        self.assertEqual(caught.exception.code, "corrupt")
        os.remove(self.old.path)
        with self.assertRaises(vr.RestoreError) as caught:
            vr.stage_restore(self.old, self.path)
        self.assertEqual(caught.exception.code, "missing")
        self.assertEqual(self.leftovers(), [])
        self.assertEqual(_read(self.path), b"version 2 (current)")

    def test_replace_that_keeps_failing_leaves_the_file(self):
        staged = vr.stage_restore(self.old, self.path)
        clock = iter([0.0, 0.1, 5.0])
        with mock.patch("os.replace", side_effect=PermissionError("in use")):
            with self.assertRaises(vr.RestoreError) as caught:
                vr.replace(staged, self.path, wait=1.0, clock=lambda: next(clock), sleep=lambda s: None)
        self.assertEqual(caught.exception.code, "replace")
        self.assertEqual(_read(self.path), b"version 2 (current)")
        self.assertEqual(self.leftovers(), [])

    def test_view_copy_is_named_after_the_file_and_time(self):
        base = os.path.join(self.tmp, "temp")
        os.makedirs(os.path.join(base, vr.VIEW_FOLDER))
        old_view = os.path.join(base, vr.VIEW_FOLDER, "old.docx")
        _write(old_view, b"x", time.time() - 3 * 86400)
        first = vr.view_copy(self.old, self.path, localtime=time.gmtime, base=base)
        second = vr.view_copy(self.old, self.path, localtime=time.gmtime, base=base)
        self.assertEqual(os.path.basename(first), "Kế hoạch (bản 14-11-2023 22.13.20).docx")
        self.assertEqual(os.path.basename(second), "Kế hoạch (bản 14-11-2023 22.13.20 2).docx")
        self.assertEqual(_read(first), b"version 1")
        self.assertFalse(os.path.exists(old_view))


class DialogFlow(Base):
    """version_dialog.restore with the office replaced by mocks."""

    def run_restore(self, close_error=None, replace_error=None, load_error=None):
        model = mock.Mock()
        model.getLocation.return_value = "file:///kế-hoạch.docx"
        events = []
        model.close.side_effect = close_error or (lambda deliver: events.append(("close", _read(self.path))))
        loaded = mock.Mock(side_effect=load_error or (lambda ctx, url: events.append(("open", url))))
        patches = [mock.patch("hst_office.version_config.store", return_value=self.store),
                   mock.patch.object(dialog, "_load", loaded),
                   mock.patch.object(dialog, "_error", side_effect=lambda ctx, peer, code: events.append(("error", code))),
                   mock.patch("hst_office.diag_log.exception"), mock.patch("hst_office.diag_log.info")]
        if replace_error:
            patches.append(mock.patch("hst_office.version_restore.replace",
                                      side_effect=vr.RestoreError(replace_error)))
        for patcher in patches:
            patcher.start()
            self.addCleanup(patcher.stop)
        dialog.restore(None, model, self.path, self.old)
        return model, events

    def test_keeps_current_closes_replaces_and_reopens(self):
        model, events = self.run_restore()
        self.assertEqual(events, [("close", b"version 2 (current)"), ("open", "file:///kế-hoạch.docx")])
        model.close.assert_called_once_with(True)
        self.assertEqual(_read(self.path), b"version 1")
        self.assertEqual(_read(self.store.versions(self.path)[0].path), b"version 2 (current)")

    def test_document_that_will_not_close_is_left_alone(self):
        _, events = self.run_restore(close_error=RuntimeError("veto"))
        self.assertEqual(events, [("error", "close")])
        self.assertEqual(_read(self.path), b"version 2 (current)")
        self.assertEqual(self.leftovers(), [])

    def test_failed_replace_reopens_the_unchanged_file_and_says_so(self):
        _, events = self.run_restore(replace_error="replace")
        self.assertEqual([e[0] for e in events], ["close", "open", "error"])
        self.assertEqual(events[-1], ("error", "replace"))

    def test_reopen_failure_is_reported(self):
        _, events = self.run_restore(load_error=RuntimeError("no window"))
        self.assertEqual(events[-1], ("error", "reopen"))
        self.assertEqual(_read(self.path), b"version 1")

    def test_state_texts(self):
        self.assertEqual(dialog._state_text(None, False, True, False), dialog.T.NOT_SAVED)
        self.assertEqual(dialog._state_text(None, True, True, False), dialog.T.NOT_LOCAL)
        self.assertEqual(dialog._state_text("/a.odt", True, False, False), dialog.T.DISABLED)
        self.assertEqual(dialog._state_text("/a.odt", True, False, True), dialog.T.DISABLED_LOCKED)
        self.assertEqual(dialog._state_text("/a.odt", True, True, False), "")


if __name__ == "__main__":
    unittest.main()
