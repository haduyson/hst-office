# SPDX-License-Identifier: LicenseRef-HST-Proprietary
# Copyright (C) 2026 HASON TECH
"""Office side of the macOS app launchers: refused for a .dmg copy, off macOS and for other software's start; the
one-time notice; the options buttons "Gỡ biểu tượng ứng dụng" / "Thêm lại biểu tượng ứng dụng"."""
import os
import unittest
from unittest import mock

import _paths  # noqa: F401
from hst_office import mac_app_launchers as ml
from hst_office import mac_app_launchers_ui as ui
from test_mac_app_launchers import HOST_ID, Machine

class OfficeSide(Machine):
    def test_refused_for_a_dmg_copy_and_for_other_softwares_start(self):
        with mock.patch.object(ui.platform, "system", return_value="Darwin"), \
                mock.patch("hst_office.mac_app_location._running_bundle",
                           return_value="/Volumes/HST Office/HST Office.app"), \
                mock.patch.object(ui.launchers, "sync") as sync:
            self.assertFalse(ui.sync_at_startup(None))
            with mock.patch.object(ui, "_automated", return_value=True), \
                    mock.patch("hst_office.mac_app_location._running_bundle", return_value=self.bundle):
                self.assertFalse(ui.sync_at_startup(None))
        sync.assert_not_called()
        with mock.patch.object(ui.platform, "system", return_value="Linux"):
            self.assertFalse(ui.sync_at_startup(None))
            self.assertFalse(ui.notice_once(None))

    def test_notice_is_shown_once(self):
        shown = []
        with mock.patch.object(ui.platform, "system", return_value="Darwin"), \
                mock.patch.dict(os.environ, {"HOME": self.home}), \
                mock.patch.object(ui, "_show_notice", side_effect=lambda ctx, folder: shown.append(folder)), \
                mock.patch.object(ui, "_automated", return_value=False):
            self.sync()
            self.assertTrue(ui.notice_once(None))
            self.assertFalse(ui.notice_once(None))
        self.assertEqual(shown, [self.system])
        self.assertIn("(/Applications)", ui.notice_text(ml.SYSTEM_FOLDER, "en"))
        self.assertIn("HST PDF", ui.notice_text(ml.SYSTEM_FOLDER, "vi"))

    def test_texts(self):
        user = os.path.join(self.home, "Applications")
        self.assertIn("~/Applications", ui.notice_text(user, "vi"))
        self.assertIn("Gỡ biểu tượng ứng dụng", ui.notice_text(self.system, "vi"))
        self.assertIn("Gỡ biểu tượng ứng dụng", ui.notice_text(self.system, "en"))

    def test_options_remove_asks_first_then_removes(self):
        self.sync()
        answers = []
        with mock.patch.object(ui, "_installed_bundle", return_value=self.bundle), \
                mock.patch.dict(os.environ, {"HOME": self.home}):
            ui.remove_from_options(None, lambda text, ask=False, button=None: answers.append(text) or False)
            self.assertEqual(ml.present(self.system, HOST_ID), list(ml.NAMES))  # "Để sau": nothing changed
            ui.remove_from_options(None, lambda text, ask=False, button=None: answers.append(text) or True)
            self.assertEqual(ml.present(self.system, HOST_ID), [])
            self.assertTrue(ml.load_state(self.home)["removed"])
        self.assertEqual(answers, [ui.OPTIONS["remove_ask"], ui.OPTIONS["remove_ask"], ui.OPTIONS["removed"]])

    def test_options_refuse_a_dmg_copy(self):
        from hst_office.app_shortcuts_ui import MOVE_FIRST
        shown = []
        with mock.patch.object(ui, "_installed_bundle", return_value=None):
            ui.add_from_options(None, lambda text, **k: shown.append(text))
            ui.remove_from_options(None, lambda text, **k: shown.append(text))
        self.assertEqual(shown, [MOVE_FIRST, MOVE_FIRST])


if __name__ == "__main__":
    unittest.main()
