# SPDX-License-Identifier: AGPL-3.0-only
""""Cập nhật ngay" without an office: where the macOS helper installs, and that an unexpected error is reported."""
import unittest
from unittest import mock

import _paths  # noqa: F401
import test_update_job  # noqa: F401 - installs the UNO module stubs before hst_office.update_install is imported
from hst_office import mac_app_location as location  # noqa: E402
from hst_office import update_install as install  # noqa: E402

RESULT = {"path": "/Users/u/Library/Caches/HSTOffice/update/HSTOffice_1.0.0_macOS_aarch64.dmg",
          "entry": {"sha256": "a" * 64}, "release": {"version": "1.0.0"}}
INFO = {"release": "1.0.0-beta.5", "channel": "beta", "test_mode": False}


class MacTarget(unittest.TestCase):
    def launch(self, bundle, writable=True):
        ctx = mock.Mock()
        ctx.ServiceManager.createInstanceWithContext.return_value.terminate.return_value = True
        with mock.patch.object(install.platform, "system", return_value="Darwin"), \
                mock.patch.object(install, "office_paths", return_value=(bundle + "/Contents/MacOS/soffice", bundle)), \
                mock.patch.object(install.update_config, "settings", return_value={"AllowInstall": True}), \
                mock.patch.object(install.launch, "write_helper", return_value="/Users/u/Library/Caches/HSTOffice/update/hst-update.sh"), \
                mock.patch.object(install.launch, "spawn") as spawn, \
                mock.patch.object(location, "_writable", return_value=writable), \
                mock.patch.object(install.cmd, "build_helper", wraps=install.cmd.build_helper) as build:
            install.launch_and_quit(ctx, RESULT, INFO)
        spawn.assert_called_once()
        return build.call_args.kwargs

    def test_read_only_disk_image_installs_into_applications_and_reopens_it(self):
        running = "/Volumes/HST Office/HST Office.app"
        arguments = self.launch(running, writable=False)
        self.assertEqual(arguments["app_dest"], "/Applications/HST Office.app")
        self.assertEqual(arguments["app_origin"], running)

    def test_bundle_already_in_applications_is_replaced_in_place(self):
        for writable in (True, False):  # not writable: the helper asks for the administrator password, as before
            with self.subTest(writable=writable):
                arguments = self.launch("/Applications/HST Office.app", writable=writable)
                self.assertEqual(arguments["app_dest"], "/Applications/HST Office.app")
                self.assertIsNone(arguments["app_origin"])


class NeverSilent(unittest.TestCase):
    def test_unexpected_error_is_reported_with_the_manual_download(self):
        with mock.patch.object(install.ui, "release_info_for", side_effect=RuntimeError("broken")), \
                mock.patch.object(install, "fail") as fail, mock.patch("traceback.print_exc"):
            self.assertIsNone(install.start(mock.Mock(), None))
        fail.assert_called_once_with(mock.ANY, None, "err_unexpected")

    def test_a_failing_message_does_not_escape(self):
        with mock.patch.object(install.ui, "release_info_for", side_effect=RuntimeError("broken")), \
                mock.patch.object(install, "fail", side_effect=RuntimeError("no dialog")), mock.patch("traceback.print_exc"):
            self.assertIsNone(install.start(mock.Mock(), None))


class WindowsElevation(unittest.TestCase):
    RESULT = {"path": r"C:\Users\u\AppData\Local\HSTOffice\update\HSTOffice_1.0.2_Win_x86-64_en-US_vi.msi",
              "entry": {"sha256": "a" * 64}, "release": {"version": "1.0.2"}}

    def launch(self, info):
        with mock.patch.object(install.platform, "system", return_value="Windows"), \
                mock.patch.object(install.installer, "cache_dir", return_value=r"C:\Users\u\AppData\Local\HSTOffice\update"), \
                mock.patch.object(install, "office_paths", return_value=(r"C:\Program Files\HSTOffice\program\soffice.exe", None)), \
                mock.patch.object(install.update_config, "settings", return_value={"AllowInstall": True}), \
                mock.patch.object(install.launch, "write_helper", return_value=r"C:\Users\u\AppData\Local\HSTOffice\update\hst-update.ps1"), \
                mock.patch.object(install.launch, "elevate_and_quit") as elevate, \
                mock.patch.object(install.launch, "spawn_and_quit") as spawn, \
                mock.patch.dict(install.os.environ, {install.DRY_RUN_ENV: "1"}):
            install.launch_and_quit(mock.Mock(), self.RESULT, info)
        return elevate, spawn

    def test_release_builds_start_the_helper_elevated_before_closing(self):
        elevate, spawn = self.launch(INFO)
        elevate.assert_called_once()
        spawn.assert_not_called()
        self.assertEqual(elevate.call_args.args[1][0], "powershell.exe")
        self.assertNotIn("-DryRun", elevate.call_args.args[1])

    def test_test_mode_dry_run_keeps_the_unelevated_helper(self):
        elevate, spawn = self.launch(dict(INFO, test_mode=True))
        elevate.assert_not_called()
        spawn.assert_called_once()

    def test_declined_elevation_is_reported_and_the_office_stays_open(self):
        result = {"result": self.RESULT}
        with mock.patch.object(install.ui, "release_info_for", return_value=INFO), \
                mock.patch.object(install.update_config, "settings", return_value={"AllowInstall": True}), \
                mock.patch.object(install.cmd, "preflight", return_value=None), \
                mock.patch.object(install, "_download_dialog", return_value=result), \
                mock.patch.object(install, "_ask", return_value="install"), \
                mock.patch.object(install, "texts", return_value={"install_title": "t", "ready": "%s", "install": "i", "later": "l"}), \
                mock.patch.object(install, "launch_and_quit", side_effect=install.launch.ElevationDeclined()), \
                mock.patch.object(install, "fail") as fail:
            self.assertIsNone(install.start(mock.Mock(), "peer"))
        fail.assert_called_once_with(mock.ANY, "peer", "err_elevation")


if __name__ == "__main__":
    unittest.main()
