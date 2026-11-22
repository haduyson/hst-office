# SPDX-License-Identifier: LicenseRef-HST-Proprietary
# Copyright (C) 2026 HASON TECH
""""Để sau" on the update infobar and in the Kiểm tra cập nhật dialog: the notice closes, the version is not skipped,
the File panel entry stays and the next automatic check (24 hours later) announces it again. The office is stubbed."""
import unittest
from types import SimpleNamespace
from unittest import mock

import install_id_support  # noqa: F401 - UNO stubs before any hst_office import
from hst_office import update_handler as handler_module  # noqa: E402
from hst_office import update_result, update_ui  # noqa: E402
from hst_office.dialogs import CANCEL  # noqa: E402

RELEASE = {"version": "1.0.1", "notes": "https://office.hasontech.vn/ghi-chu", "installers": {}}


def url(path):
    return SimpleNamespace(Protocol=handler_module.PROTOCOL, Path=path)


class LaterTests(unittest.TestCase):
    def setUp(self):
        self.handler = handler_module.UpdateHandler("ctx")
        self.handler.initialize((SimpleNamespace(getContainerWindow=lambda: "peer"),))
        state = mock.patch.dict(handler_module.AVAILABLE, {"release": None, "listeners": []})
        state.start()
        self.addCleanup(state.stop)

    def test_later_is_a_command_of_the_handler(self):
        self.assertIs(self.handler.queryDispatch(url("Later"), "", 0), self.handler)

    def test_later_on_the_infobar_only_closes_it(self):
        """"Để sau": the version is not skipped and stays on the File panel; the next automatic check tells again."""
        handler_module.set_available(RELEASE)
        with mock.patch.object(update_ui, "save") as save, mock.patch.object(update_ui, "remove_infobar") as remove:
            self.handler.dispatch(url("Later"), ())
        remove.assert_called_once_with(self.handler.frame)
        save.assert_not_called()
        self.assertIs(handler_module.AVAILABLE["release"], RELEASE)

    def test_the_infobar_offers_later_before_skip(self):
        controller = mock.Mock()
        controller.hasInfobar.return_value = False
        frame = mock.Mock()
        frame.getController.return_value = controller
        pairs = []
        with mock.patch.object(update_ui.uno, "createUnoStruct", side_effect=lambda name: SimpleNamespace()), \
                mock.patch.object(update_ui.uno, "getComponentContext", return_value="ctx", create=True), \
                mock.patch.object(update_ui, "can_install", return_value=True), \
                mock.patch.object(update_ui, "texts", return_value=mock.MagicMock(**{"__getitem__.side_effect": lambda k: k + " %s"})):
            self.assertTrue(update_ui.show_infobar(frame, RELEASE, "1.0.0"))
        pairs = controller.appendInfobar.call_args[0][4]
        self.assertEqual([p.Second for p in pairs], [update_ui.PROTOCOL + c for c in
                                                     ("Install", "Download", "Notes", "Later", "Skip")])
        self.assertEqual(pairs[3].First, "later %s")

    def check_dialog_buttons(self, release, failed=False):
        dialog = mock.Mock()
        texts = mock.MagicMock()
        texts.__getitem__.side_effect = lambda key: "%s"
        with mock.patch("hst_office.dialogs.Dialog", return_value=dialog) as make, \
                mock.patch.object(update_result, "texts", return_value=texts), \
                mock.patch.object(update_result.update_config, "load", return_value=({"AutoCheck": True}, ())), \
                mock.patch.object(update_ui, "can_install", return_value=True), \
                mock.patch.object(update_ui, "save") as save, mock.patch.dict(update_ui.STATE, {"release": None}):
            update_result.show_result("ctx", "peer", release, "1.0.0", failed)
        buttons = {c.args[0]: c for c in dialog.button.call_args_list}
        return make.call_args[0][2], buttons, save

    def test_the_check_dialog_offers_later_that_skips_nothing(self):
        width, buttons, save = self.check_dialog_buttons(RELEASE)
        self.assertEqual(list(buttons), ["install", "download", "notes", "skip", "later"])
        later = buttons["later"]
        self.assertEqual(later.kwargs["kind"], CANCEL)  # closes like Esc, no callback
        self.assertNotIn("callback", later.kwargs)
        save.assert_not_called()
        # every button inside the dialog, none over another
        spans = [(c.args[2], c.args[2] + c.args[4]) for c in buttons.values()]
        self.assertTrue(all(a[1] <= b[0] for a, b in zip(spans, spans[1:])), spans)
        self.assertLessEqual(spans[-1][1] + 8, width)

    def test_up_to_date_keeps_close(self):
        _width, buttons, _save = self.check_dialog_buttons(None)
        self.assertEqual(list(buttons), ["close"])



if __name__ == "__main__":
    unittest.main()
