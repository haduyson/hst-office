# SPDX-License-Identifier: AGPL-3.0-only
"""The org.hst.office.update: command handler (update_handler.py): every command reaches the update code it imports on
use, and the "Kiểm tra cập nhật" menu state follows the ManualCheck lock. The office is stubbed."""
import unittest
from types import SimpleNamespace
from unittest import mock

import install_id_support  # noqa: F401 - UNO stubs before any hst_office import
from hst_office import update_handler as handler_module  # noqa: E402
from hst_office import update_install, update_job, update_result, update_ui  # noqa: E402
from hst_office import update_install_id  # noqa: E402

RELEASE = {"version": "1.0.1", "notes": "https://office.hasontech.vn/ghi-chu", "installers": {}}


def url(path):
    return SimpleNamespace(Protocol=handler_module.PROTOCOL, Path=path)


class UpdateHandlerTests(unittest.TestCase):
    def setUp(self):
        self.frame = SimpleNamespace(getContainerWindow=lambda: "peer")
        self.handler = handler_module.UpdateHandler("ctx")
        self.handler.initialize((self.frame,))
        logged = mock.patch.object(handler_module.diag_log, "exception")
        self.logged = logged.start()
        self.addCleanup(logged.stop)
        state = mock.patch.dict(update_ui.STATE, {"release": RELEASE})
        state.start()
        self.addCleanup(state.stop)

    def tearDown(self):
        self.logged.assert_not_called()

    def test_it_answers_for_its_five_commands_only(self):
        for command in handler_module.COMMANDS:
            self.assertIs(self.handler.queryDispatch(url(command), "", 0), self.handler)
        self.assertIsNone(self.handler.queryDispatch(url("Other"), "", 0))
        self.assertIsNone(self.handler.queryDispatch(SimpleNamespace(Protocol="org.hst.office.vi:", Path="Check"), "", 0))
        self.assertEqual(handler_module.PROTOCOL, update_ui.PROTOCOL)

    def test_check_starts_the_background_check(self):
        info = {"release": "1.0.0", "channel": "stable"}
        with mock.patch.object(update_ui, "settings", return_value={"ManualCheck": True}), \
                mock.patch.object(update_ui, "release_info_for", return_value=info), \
                mock.patch.object(update_install_id, "add_to", side_effect=lambda ctx, i: dict(i, id="x")), \
                mock.patch.object(update_job, "start_background") as start:
            self.handler.dispatch(url("Check"), ())
        start.assert_called_once()
        self.assertEqual(start.call_args[0][1], dict(info, id="x"))

    def test_check_locked_off_contacts_nothing(self):
        with mock.patch.object(update_ui, "settings", return_value={"ManualCheck": False}), \
                mock.patch.object(update_job, "start_background") as start:
            self.handler.dispatch(url("Check"), ())
        start.assert_not_called()

    def test_check_without_release_stamp_reports_could_not_check(self):
        with mock.patch.object(update_ui, "settings", return_value={"ManualCheck": True}), \
                mock.patch.object(update_ui, "release_info_for", side_effect=KeyError("release")), \
                mock.patch.object(update_result, "show_result") as show, \
                mock.patch.object(update_job, "start_background") as start:
            self.handler.dispatch(url("Check"), ())
        start.assert_not_called()
        show.assert_called_once_with("ctx", "peer", None, "", True)
        self.logged.reset_mock()  # the missing stamp is logged on purpose

    def test_download_notes_skip_and_install(self):
        with mock.patch.object(update_ui, "open_url") as open_url, \
                mock.patch.object(update_ui, "release_download", return_value="https://office.hasontech.vn/tai/x.msi"):
            self.handler.dispatch(url("Download"), ())
            self.handler.dispatch(url("Notes"), ())
        self.assertEqual([c[0][1] for c in open_url.call_args_list],
                         ["https://office.hasontech.vn/tai/x.msi", RELEASE["notes"]])
        with mock.patch.object(update_ui, "save") as save, mock.patch.object(update_ui, "remove_infobar") as remove:
            self.handler.dispatch(url("Skip"), ())
        save.assert_called_once_with("ctx", "SkippedVersion", "1.0.1")
        remove.assert_called_once_with(self.frame)
        with mock.patch.object(update_install, "start") as start:
            self.handler.dispatch(url("Install"), ())
        start.assert_called_once_with("ctx", "peer")

    def test_no_release_known_does_nothing(self):
        with mock.patch.dict(update_ui.STATE, {"release": None}), mock.patch.object(update_ui, "open_url") as open_url:
            self.handler.dispatch(url("Download"), ())
            self.handler.dispatch(url("Notes"), ())
        open_url.assert_not_called()

    def test_check_menu_state_follows_the_manual_check_lock(self):
        for allowed in (True, False):
            control = mock.Mock()
            with mock.patch.object(handler_module.update_config, "settings", return_value={"ManualCheck": allowed}), \
                    mock.patch.object(handler_module.uno, "createUnoStruct", side_effect=lambda name: SimpleNamespace()):
                self.handler.addStatusListener(control, url("Check"))
                self.handler.addStatusListener(control, url("Download"))  # no state for the other commands
            control.statusChanged.assert_called_once()
            self.assertIs(control.statusChanged.call_args[0][0].IsEnabled, allowed)


if __name__ == "__main__":
    unittest.main()
