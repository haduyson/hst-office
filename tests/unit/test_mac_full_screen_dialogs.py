# SPDX-License-Identifier: LicenseRef-HST-Proprietary
"""macOS: a dialog of the office itself (Format > Character) follows a document opened in native full screen
(mac_full_screen_dialogs). No office: the broadcaster, windows and timers are fakes; AppKit is mocked."""
import unittest
from unittest import mock

import _paths  # noqa: F401
import test_dialog_on_screen as screen  # noqa: F401 - installs the UNO stubs
from hst_office import dialog_registry  # noqa: E402
from hst_office import mac_full_screen_dialogs as mfs  # noqa: E402


class WatchTests(unittest.TestCase):
    def setUp(self):
        mfs._STATE["listener"] = None
        self.addCleanup(mfs._STATE.update, {"listener": None})
        self.office, self.timers = screen.DisplayOffice(), screen.Timers()
        self.document = screen.Window(True)

    def test_an_opened_document_gets_the_stranded_dialogs_after_it_settled(self):
        self.assertTrue(mfs.start(self.office, platform="darwin", timer=self.timers))
        self.assertTrue(mfs.start(self.office, platform="darwin", timer=self.timers))  # once per process
        self.assertEqual(len(self.office.broadcaster.listeners), 1)
        self.office.broadcaster.fire("OnTitleChanged", self.document)
        self.assertEqual(self.timers.pending, [])
        self.office.broadcaster.fire("OnViewCreated", self.document)
        self.assertEqual([d for d, _ in self.timers.pending], [mfs.DELAY])
        with mock.patch("hst_office.mac_native_window.adopt_dialogs", return_value=1) as adopt, \
                mock.patch.object(mfs.diag_log, "info") as info:
            self.timers.fire()
            self.office.pump()
        adopt.assert_called_once_with(self.document)
        info.assert_called_once()

    def test_an_open_hst_dialog_moves_itself_and_a_hidden_window_takes_nothing(self):
        with mock.patch("hst_office.mac_native_window.adopt_dialogs") as adopt:
            with mock.patch.object(dialog_registry, "OPEN", [object()]):
                self.assertEqual(mfs.adopt(self.document), 0)
            self.assertEqual(mfs.adopt(screen.Window(False)), 0)
        adopt.assert_not_called()

    def test_windows_and_linux_watch_nothing(self):
        for platform in ("win32", "linux"):
            self.assertFalse(mfs.start(self.office, platform=platform))
        self.assertEqual(self.office.broadcaster.listeners, [])


if __name__ == "__main__":
    unittest.main()
