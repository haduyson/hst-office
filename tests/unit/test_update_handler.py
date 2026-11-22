# SPDX-License-Identifier: LicenseRef-HST-Proprietary
# Copyright (C) 2026 HASON TECH
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

    def test_it_answers_for_its_commands_only(self):
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



class UpdateAvailableTests(unittest.TestCase):
    """org.hst.office.update:Available: the File panel entry and the File tab dot follow the release a check found."""

    def setUp(self):
        self.handler = handler_module.UpdateHandler("ctx")
        self.handler.initialize((SimpleNamespace(getContainerWindow=lambda: "peer"),))
        state = mock.patch.dict(handler_module.AVAILABLE, {"release": None, "listeners": []})
        state.start()
        self.addCleanup(state.stop)
        struct = mock.patch.object(handler_module.uno, "createUnoStruct", side_effect=lambda name: SimpleNamespace())
        struct.start()
        self.addCleanup(struct.stop)

    def states(self, control):
        return [c[0][0].IsEnabled for c in control.statusChanged.call_args_list]

    def test_listeners_hear_the_current_state_then_every_change(self):
        control = mock.Mock()
        self.handler.addStatusListener(control, url("Available"))
        handler_module.set_available(RELEASE)
        handler_module.set_available(None)
        self.assertEqual(self.states(control), [False, True, False])
        self.handler.removeStatusListener(control, url("Available"))
        handler_module.set_available(RELEASE)
        self.assertEqual(len(self.states(control)), 3)

    def test_a_disposed_listener_is_dropped(self):
        gone, alive = mock.Mock(), mock.Mock()
        self.handler.addStatusListener(gone, url("Available"))
        self.handler.addStatusListener(alive, url("Available"))
        gone.statusChanged.side_effect = RuntimeError("disposed")
        handler_module.set_available(RELEASE)
        self.assertEqual(self.states(alive), [False, True])
        self.assertEqual([c for c, _ in handler_module.AVAILABLE["listeners"]], [alive])

    def test_the_entry_installs_a_known_release_else_checks(self):
        with mock.patch.object(update_install, "start") as install, \
                mock.patch.object(self.handler, "_check") as check:
            self.handler.dispatch(url("Available"), ())
            handler_module.set_available(RELEASE)
            self.handler.dispatch(url("Available"), ())
        check.assert_called_once_with()
        install.assert_called_once_with("ctx", "peer")

    def test_skipping_the_release_takes_the_dot_off(self):
        handler_module.set_available(RELEASE)
        with mock.patch.object(update_ui, "save") as save, mock.patch.object(update_ui, "remove_infobar"), \
                mock.patch.dict(update_ui.STATE, {"release": RELEASE}):
            self.handler.dispatch(url("Skip"), ())
        save.assert_called_once_with("ctx", "SkippedVersion", RELEASE["version"])
        self.assertIsNone(handler_module.AVAILABLE["release"])

    def test_skip_in_the_check_dialog_takes_the_dot_off(self):
        dialog = mock.Mock()
        texts = mock.MagicMock()
        texts.__getitem__.side_effect = lambda key: "%s"
        with mock.patch("hst_office.dialogs.Dialog", return_value=dialog), \
                mock.patch.object(update_result, "texts", return_value=texts), \
                mock.patch.object(update_result.update_config, "load", return_value=({"AutoCheck": True}, ())), \
                mock.patch.object(update_ui, "can_install", return_value=False), \
                mock.patch.object(update_ui, "save") as save, mock.patch.dict(update_ui.STATE, {"release": None}):
            dialog.execute.return_value = 0
            update_result.show_result("ctx", "peer", RELEASE, "1.0.0", False)
            self.assertIs(handler_module.AVAILABLE["release"], RELEASE)
            skip = next(c.kwargs["callback"] for c in dialog.button.call_args_list if c.args[0] == "skip")
            skip()
        save.assert_any_call("ctx", "SkippedVersion", RELEASE["version"])
        self.assertIsNone(handler_module.AVAILABLE["release"])

    def test_the_check_dialog_and_the_infobar_publish_what_they_found(self):
        with mock.patch.object(update_ui, "show_infobar", return_value=True), \
                mock.patch.object(update_ui, "_broadcaster"), \
                mock.patch.dict(update_ui.STATE, {"release": None}):
            fake_desktop = mock.Mock()
            ctx = mock.Mock()
            ctx.ServiceManager.createInstanceWithContext.return_value = fake_desktop
            update_ui.notify(ctx, RELEASE, "1.0.0")
        self.assertIs(handler_module.AVAILABLE["release"], RELEASE)


if __name__ == "__main__":
    unittest.main()
