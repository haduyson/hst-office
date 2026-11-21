# SPDX-License-Identifier: AGPL-3.0-only
""""Cập nhật ngay" on macOS: the question warns before the office closes that the Mac will ask for the administrator
password (the helper asks only after the office is gone, so a skipped password prompt would look like a no-op)."""
import os
import tempfile
import unittest
from unittest import mock

import _paths  # noqa: F401
import test_update_job  # noqa: F401 - installs the UNO module stubs before hst_office.update_install is imported
from hst_office import update_install as install  # noqa: E402
from hst_office import update_install_ui as install_ui  # noqa: E402
from hst_office.update_texts import TEXTS  # noqa: E402

RESULT = {"path": "/tmp/x.dmg", "entry": {"sha256": "a" * 64}, "release": {"version": "1.0.3"}}
INFO = {"release": "1.0.2", "channel": "stable", "test_mode": False}


class NeedsPassword(unittest.TestCase):
    def setUp(self):
        self.root = tempfile.mkdtemp()
        self.bundle = os.path.join(self.root, "HST Office.app")
        os.mkdir(self.bundle)

    def test_writable_bundle_and_folder_need_no_password(self):
        self.assertFalse(install_ui.needs_password(self.bundle, writable=lambda path: True))

    def test_root_owned_bundle_or_folder_needs_the_password(self):
        self.assertTrue(install_ui.needs_password(self.bundle, writable=lambda path: path != self.bundle))
        self.assertTrue(install_ui.needs_password(self.bundle, writable=lambda path: path != self.root))

    def test_no_bundle_outside_macos(self):
        self.assertFalse(install_ui.needs_password(None))


class Question(unittest.TestCase):
    def ask(self, password):
        with mock.patch.object(install.ui, "release_info_for", return_value=INFO), \
                mock.patch.object(install.update_config, "settings", return_value={"AllowInstall": True}), \
                mock.patch.object(install.cmd, "preflight", return_value=None), \
                mock.patch.object(install.platform, "system", return_value="Darwin"), \
                mock.patch.object(install, "_download_dialog", return_value={"result": RESULT}), \
                mock.patch.object(install, "office_paths", return_value=("/A/HST Office.app/Contents/MacOS/soffice",
                                                                         "/A/HST Office.app")), \
                mock.patch.object(install, "needs_password", return_value=password) as needs, \
                mock.patch.object(install, "texts", return_value=TEXTS["vi"]), \
                mock.patch.object(install, "_ask", return_value="later") as ask:
            install.start(mock.Mock(), mock.Mock())
        needs.assert_called_once_with("/A/HST Office.app")
        return ask.call_args.args[3], ask.call_args.args[5]

    def test_password_is_announced_in_the_question(self):
        text, height = self.ask(True)
        self.assertIn("1.0.3", text)
        self.assertIn("mật khẩu quản trị", text)
        self.assertGreater(height, 28)

    def test_no_mention_when_the_app_can_be_replaced_without_it(self):
        text, height = self.ask(False)
        self.assertNotIn("mật khẩu", text)
        self.assertEqual(height, 28)


class Texts(unittest.TestCase):
    def test_both_languages_have_the_warning(self):
        for language in ("vi", "en"):
            self.assertIn("%s", TEXTS[language]["ready_password"])


if __name__ == "__main__":
    unittest.main()
