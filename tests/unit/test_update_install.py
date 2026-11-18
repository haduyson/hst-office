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
                mock.patch.object(install.resume, "write"), \
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
                mock.patch.object(install.resume, "write"), mock.patch.object(install.resume, "discard"), \
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
            peer = mock.Mock()
            peer.isVisible.return_value = True
            self.assertIsNone(install.start(mock.Mock(), peer))
        fail.assert_called_once_with(mock.ANY, peer, "err_elevation")


TEXT = {"install_title": "t", "err_quit": "q", "retry": "r", "later": "l"}


class QuitRefused(unittest.TestCase):
    """The office did not close (a dialog or a save prompt): the user is told, never a silent "nothing happened"."""

    def run_install(self, results, answers):
        peer = mock.Mock()
        peer.isVisible.return_value = True
        with mock.patch.object(install, "launch_and_quit", side_effect=results) as launch, \
                mock.patch.object(install.launch, "end_own_dialogs", return_value=0), \
                mock.patch.object(install, "texts", return_value=TEXT), \
                mock.patch.object(install, "_ask", side_effect=answers) as ask:
            install.install(mock.Mock(), peer, RESULT, INFO)
        return launch, ask

    def test_refused_quit_is_reported_and_can_be_retried(self):
        launch, ask = self.run_install([False, True], ["retry"])
        self.assertEqual(launch.call_count, 2)
        self.assertEqual(ask.call_count, 1)
        self.assertEqual(ask.call_args.args[3], "q")

    def test_later_keeps_the_office_open(self):
        launch, ask = self.run_install([False], ["later"])
        self.assertEqual(launch.call_count, 1)
        self.assertEqual(ask.call_count, 1)

    def test_quitting_office_shows_nothing(self):
        for result in (True, None):  # quitting, or installing was turned off by the administrator meanwhile
            launch, ask = self.run_install([result], [])
            ask.assert_not_called()


class OwnDialogsFirst(unittest.TestCase):
    def test_open_extension_dialogs_are_ended_and_the_quit_waits_a_turn(self):
        posted = []
        ctx = mock.Mock()
        with mock.patch.object(install.launch, "end_own_dialogs", side_effect=[1, 0]) as end, \
                mock.patch.object(install.ui, "on_main_thread", side_effect=lambda c, fn: posted.append(fn)), \
                mock.patch.object(install, "launch_and_quit", return_value=True) as launch:
            install.install(ctx, None, RESULT, INFO)
            launch.assert_not_called()  # the welcome dialog of another window is still in its modal loop
            self.assertEqual(len(posted), 1)
            posted[0]()
        self.assertEqual(end.call_count, 2)
        launch.assert_called_once_with(ctx, RESULT, INFO)

    def test_the_wait_is_bounded(self):
        posted = []
        with mock.patch.object(install.launch, "end_own_dialogs", return_value=1), \
                mock.patch.object(install.ui, "on_main_thread", side_effect=lambda c, fn: posted.append(fn)), \
                mock.patch.object(install, "launch_and_quit", return_value=True) as launch:
            install.install(mock.Mock(), None, RESULT, INFO)
            while posted:
                posted.pop()()
        launch.assert_called_once()

    def test_end_own_dialogs_ends_every_open_extension_dialog(self):
        from hst_office import dialogs
        first, second = mock.Mock(), mock.Mock()
        second.endExecute.side_effect = RuntimeError("disposed")
        with mock.patch.object(dialogs, "OPEN", [first, second]):
            self.assertEqual(install.launch.end_own_dialogs(), 1)
        first.endExecute.assert_called_once_with()


class PendingRecord(unittest.TestCase):
    """The documents to reopen are recorded before the quit, and forgotten when the office stays open."""

    def launch(self, closing):
        import tempfile
        cache = tempfile.mkdtemp()
        ctx = mock.Mock()
        with mock.patch.object(install.platform, "system", return_value="Linux"), \
                mock.patch.object(install.installer, "cache_dir", return_value=cache), \
                mock.patch.object(install.linux_install, "linux_kind", return_value="deb"), \
                mock.patch.object(install, "office_paths", return_value=("/opt/hst-office1.0/program/soffice", None)), \
                mock.patch.object(install.update_config, "settings", return_value={"AllowInstall": True}), \
                mock.patch.object(install.resume, "document_urls", return_value=["file:///home/u/a.docx"]), \
                mock.patch.object(install.launch, "spawn_and_quit", return_value=closing) as quit_:
            result = install.launch_and_quit(ctx, dict(RESULT, path="/home/u/.cache/hst-office/update/x.deb"), INFO)
        quit_.assert_called_once()
        return result, install.resume.read(cache)

    def test_record_names_documents_and_releases_when_quitting(self):
        result, record = self.launch(True)
        self.assertIs(result, True)
        self.assertEqual((record["from"], record["to"], record["documents"]), ("1.0.0-beta.5", "1.0.0", ["file:///home/u/a.docx"]))

    def test_record_is_removed_when_the_office_stays_open(self):
        result, record = self.launch(False)
        self.assertIs(result, False)
        self.assertIsNone(record)


if __name__ == "__main__":
    unittest.main()
