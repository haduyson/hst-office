# SPDX-License-Identifier: AGPL-3.0-only
"""The first start after "Cập nhật ngay": documents reopened, success noted, a helper that never installed reported."""
import json
import os
import tempfile
import unittest
from unittest import mock

import _paths  # noqa: F401
import test_update_job  # noqa: F401 - installs the UNO module stubs
from hst_office import update_resume as resume  # noqa: E402

NOW = 1_800_000_000
DOCS = ["file:///home/u/B%C3%A1o%20c%C3%A1o.docx", "file:///home/u/s.xlsx"]


def frames(*urls):
    """A desktop whose frames show documents at `urls` (None: the Start Center, no model)."""
    items = []
    for url in urls:
        frame = mock.Mock()
        if url is None:
            frame.getController.return_value.getModel.return_value = None
        else:
            frame.getController.return_value.getModel.return_value.getURL.return_value = url
        items.append(frame)
    desktop = mock.Mock()
    desktop.getFrames.return_value.getCount.return_value = len(items)
    desktop.getFrames.return_value.getByIndex.side_effect = items.__getitem__
    return desktop


class Record(unittest.TestCase):
    def setUp(self):
        self.cache = tempfile.mkdtemp()

    def test_round_trip(self):
        resume.write(self.cache, "1.0.3", "1.0.4", DOCS, now=NOW)
        self.assertEqual(resume.read(self.cache), {"schema": 1, "from": "1.0.3", "to": "1.0.4", "time": NOW, "documents": DOCS})
        resume.discard(self.cache)
        self.assertIsNone(resume.read(self.cache))
        resume.discard(self.cache)  # nothing there: no error

    def test_invalid_records_are_removed(self):
        path = os.path.join(self.cache, resume.PENDING_NAME)
        for body in ("not json", json.dumps({"schema": 2}), json.dumps({"schema": 1, "from": "1", "to": "2", "time": NOW,
                                                                        "documents": ["https://example.com/a.docx"]})):
            with open(path, "w", encoding="utf-8") as handle:
                handle.write(body)
            self.assertIsNone(resume.read(self.cache))
            self.assertFalse(os.path.exists(path))

    def test_document_urls_keeps_local_files_once(self):
        desktop = frames(DOCS[0], None, "private:factory/swriter", DOCS[1], DOCS[0], "https://example.com/x.docx")
        self.assertEqual(resume.document_urls(desktop), DOCS)


class Decide(unittest.TestCase):
    RECORD = {"from": "1.0.3", "to": "1.0.4", "time": NOW}

    def decide(self, current, failure=False, age=60):
        return resume.decide(self.RECORD, current, failure, NOW + age)

    def test_new_release_runs(self):
        self.assertEqual(self.decide("1.0.4"), ("installed", False))

    def test_failure_is_left_to_update_outcome(self):
        self.assertEqual(self.decide("1.0.3", failure=True), ("failed", False))

    def test_helper_still_working_keeps_the_record(self):
        self.assertEqual(self.decide("1.0.3", age=5 * 60), ("wait", True))

    def test_helper_that_never_installed_is_reported(self):
        self.assertEqual(self.decide("1.0.3", age=resume.HELPER_GRACE + 1), ("stopped", False))

    def test_old_or_foreign_records_are_dropped(self):
        self.assertEqual(self.decide("1.0.3", age=resume.MAX_AGE + 1), ("stale", False))
        self.assertEqual(self.decide("1.0.5"), ("stale", False))
        self.assertEqual(self.decide("1.0.4", age=-3600), ("stale", False))


class Handle(unittest.TestCase):
    def setUp(self):
        self.cache = tempfile.mkdtemp()
        resume.write(self.cache, "1.0.3", "1.0.4", DOCS, now=NOW)

    def handle(self, current, failure=False, age=60):
        frame = mock.Mock()
        with mock.patch.object(resume, "reopen", return_value=frame) as reopen, \
                mock.patch.object(resume, "_show_installed") as installed, \
                mock.patch.object(resume, "_show_stopped") as stopped:
            action = resume.handle(mock.Mock(), self.cache, current, failure, now=NOW + age)
        return action, reopen, installed, stopped

    def test_installed_reopens_and_notes(self):
        action, reopen, installed, stopped = self.handle("1.0.4")
        self.assertEqual(action, "installed")
        reopen.assert_called_once_with(mock.ANY, DOCS)
        installed.assert_called_once_with(mock.ANY, reopen.return_value, "1.0.4")
        stopped.assert_not_called()
        self.assertIsNone(resume.read(self.cache))

    def test_failed_install_reopens_without_a_second_message(self):
        action, reopen, installed, stopped = self.handle("1.0.3", failure=True)
        self.assertEqual(action, "failed")
        reopen.assert_called_once()
        installed.assert_not_called()
        stopped.assert_not_called()

    def test_stopped_helper_is_reported_once(self):
        action, reopen, installed, stopped = self.handle("1.0.3", age=resume.HELPER_GRACE + 60)
        self.assertEqual(action, "stopped")
        stopped.assert_called_once()
        self.assertIsNone(resume.read(self.cache))

    def test_manual_start_while_the_helper_works_does_nothing(self):
        action, reopen, installed, stopped = self.handle("1.0.3", age=60)
        self.assertEqual(action, "wait")
        reopen.assert_not_called()
        self.assertIsNotNone(resume.read(self.cache))


class Reopen(unittest.TestCase):
    def test_missing_files_are_skipped_and_the_first_frame_returned(self):
        with tempfile.TemporaryDirectory() as root:
            present = os.path.join(root, "a.odt")
            open(present, "w").close()
            ctx = mock.Mock()
            desktop = ctx.ServiceManager.createInstanceWithContext.return_value
            stub = mock.Mock(fileUrlToSystemPath=lambda url: url[len("file://"):])
            with mock.patch.dict("sys.modules", {"uno": stub}):
                frame = resume.reopen(ctx, ["file://" + os.path.join(root, "gone.odt"), "file://" + present])
        desktop.loadComponentFromURL.assert_called_once_with("file://" + present, "_default", 0, ())
        self.assertIs(frame, desktop.loadComponentFromURL.return_value.getCurrentController.return_value.getFrame.return_value)


if __name__ == "__main__":
    unittest.main()
