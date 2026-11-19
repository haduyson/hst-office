# SPDX-License-Identifier: AGPL-3.0-only
"""Pop-up after the automatic check: once a day per version, waits for a busy start, falls back to the infobar."""
import os
import tempfile
import unittest
from unittest import mock

import _paths  # noqa: F401
import test_update_job  # noqa: F401 - installs the UNO module stubs
from hst_office import update_popup as popup  # noqa: E402
from hst_office import update_handler as handler  # noqa: E402
from hst_office import update_ui as ui  # noqa: E402

NOW = 1_800_000_000
RELEASE = {"version": "1.0.4", "critical": False, "notes": "https://office.hasontech.vn/", "downloads": {}}


class Due(unittest.TestCase):
    def test_once_a_day_per_version(self):
        self.assertTrue(popup.due(None, "1.0.4", NOW))
        shown = {"version": "1.0.4", "shown": NOW}
        self.assertFalse(popup.due(shown, "1.0.4", NOW + popup.REMIND_AFTER - 1))
        self.assertTrue(popup.due(shown, "1.0.4", NOW + popup.REMIND_AFTER))
        self.assertTrue(popup.due(shown, "1.0.5", NOW + 60))  # a newer release is announced at once
        self.assertTrue(popup.due(shown, "1.0.4", NOW - 3600))  # clock set back
        self.assertTrue(popup.due({"version": "1.0.4", "shown": "x"}, "1.0.4", NOW))

    def test_reminder_round_trip(self):
        with tempfile.TemporaryDirectory() as cache:
            self.assertIsNone(popup.load(cache))
            popup.remember(os.path.join(cache, "sub"), "1.0.4", NOW)
            self.assertEqual(popup.load(os.path.join(cache, "sub")), {"version": "1.0.4", "shown": NOW})


class Notify(unittest.TestCase):
    def setUp(self):
        self.cache = tempfile.mkdtemp()
        for target, name, value in ((popup, "_cache", self.cache), (popup, "_busy", False), (popup, "show", None), (ui, "notify", None)):
            patcher = mock.patch.object(target, name, return_value=value)
            patcher.start()
            self.addCleanup(patcher.stop)

    def test_due_popup_is_shown_and_remembered(self):
        popup.show.return_value = True
        popup.notify(mock.Mock(), RELEASE, "1.0.3", now=NOW)
        popup.show.assert_called_once()
        ui.notify.assert_not_called()
        self.assertEqual(popup.load(self.cache), {"version": "1.0.4", "shown": NOW})
        self.assertIs(ui.STATE["release"], RELEASE)  # the handler's Install/Download/Skip commands use it

    def test_the_file_panel_hears_of_the_release_the_popup_shows(self):
        popup.show.return_value = True
        with mock.patch.dict(handler.AVAILABLE, {"release": None, "listeners": []}):
            popup.notify(mock.Mock(), RELEASE, "1.0.3", now=NOW)
            self.assertIs(handler.AVAILABLE["release"], RELEASE)

    def test_shown_today_falls_back_to_the_infobar(self):
        popup.remember(self.cache, "1.0.4", NOW)
        popup.notify(mock.Mock(), RELEASE, "1.0.3", now=NOW + 3600)
        popup.show.assert_not_called()
        ui.notify.assert_called_once()

    def test_no_window_falls_back_to_the_infobar_and_asks_again_later(self):
        popup.show.return_value = False
        popup.notify(mock.Mock(), RELEASE, "1.0.3", now=NOW)
        ui.notify.assert_called_once()
        self.assertIsNone(popup.load(self.cache))

    def test_busy_start_waits(self):
        popup._busy.return_value = True
        with mock.patch.object(popup.threading, "Timer") as timer:
            popup.notify(mock.Mock(), RELEASE, "1.0.3", now=NOW)
        timer.return_value.start.assert_called_once()
        popup.show.assert_not_called()
        ui.notify.assert_not_called()

    def test_waiting_is_bounded(self):
        popup._busy.return_value = True
        popup.show.return_value = True
        popup.notify(mock.Mock(), RELEASE, "1.0.3", now=NOW, tries=popup.WAIT_TRIES)
        popup.show.assert_called_once()

    def test_no_second_popup_while_one_is_showing(self):
        shown = mock.Mock()
        with mock.patch.object(popup, "_CURRENT", [shown]):
            popup.notify(mock.Mock(), RELEASE, "1.0.3", now=NOW)
            popup.show.assert_not_called()
            ui.notify.assert_not_called()
            popup.close_all()
            self.assertEqual(popup._CURRENT, [])
        shown.dialog.dispose.assert_called_once_with()

    def test_error_falls_back_to_the_infobar(self):
        popup.show.side_effect = RuntimeError("no toolkit")
        with mock.patch("traceback.print_exc"):
            popup.notify(mock.Mock(), RELEASE, "1.0.3", now=NOW)
        ui.notify.assert_called_once()


class Buttons(unittest.TestCase):
    """What the pop-up's buttons do, after the pop-up has closed."""

    def setUp(self):
        state = mock.patch.dict(handler.AVAILABLE, {"release": RELEASE, "listeners": []})
        state.start()
        self.addCleanup(state.stop)

    def test_skip_saves_the_version_and_takes_the_dot_off_the_file_tab(self):
        with mock.patch.object(ui, "save") as save:
            popup.run_action("ctx", RELEASE, "skip")
        save.assert_called_once_with("ctx", "SkippedVersion", "1.0.4")
        self.assertIsNone(handler.AVAILABLE["release"])

    def test_later_changes_nothing(self):
        with mock.patch.object(ui, "save") as save, mock.patch.object(ui, "open_url") as open_url:
            popup.run_action("ctx", RELEASE, "later")
        save.assert_not_called()
        open_url.assert_not_called()
        self.assertIs(handler.AVAILABLE["release"], RELEASE)

    def test_download_opens_the_download_page(self):
        with mock.patch.object(ui, "open_url") as open_url, \
                mock.patch.object(ui, "release_download", return_value="https://x/"):
            popup.run_action("ctx", RELEASE, "download")
        open_url.assert_called_once_with("ctx", "https://x/")

    def test_a_failing_button_never_raises(self):
        with mock.patch.object(ui, "save", side_effect=OSError("read-only")), \
                mock.patch.object(popup.diag_log, "exception") as logged:
            popup.run_action("ctx", RELEASE, "skip")
        logged.assert_called_once_with("update_popup")


if __name__ == "__main__":
    unittest.main()
