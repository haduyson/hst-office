# SPDX-License-Identifier: AGPL-3.0-only
"""The once-per-version move offer: what is asked, what runs after each answer, and that no failure after "Chuyển"
stays silent (no office needed: the question, the copy and the quit are recorded)."""
import os
import tempfile
import unittest
from unittest import mock

import _paths  # noqa: F401
from hst_office import mac_app_location as location
from hst_office import mac_move_script as move
from hst_office.update_texts import TEXTS

VI = TEXTS["vi"]
TRANSLOCATED = "/private/var/folders/xy/T/AppTranslocation/0A1B-2C3D/d/HST Office.app"
DMG = "/Volumes/HST Office/HST Office.app"


class OfferOnce(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.home = self.temp.name
        self.dest = os.path.join(self.home, "Applications", "HST Office.app")
        self.release = {"release": "1.0.0"}
        for patch in (mock.patch.object(location, "DESTINATION", self.dest),
                      mock.patch("hst_office.update_texts.texts", return_value=VI),
                      mock.patch("hst_office.update_fetch.release_info", side_effect=lambda: self.release),
                      mock.patch("hst_office.update_installer.cache_dir", return_value=os.path.join(self.home, "cache")),
                      mock.patch.object(location, "_with_progress", side_effect=lambda ctx, title, message, work: work()),
                      mock.patch("traceback.print_exc")):
            patch.start()
            self.addCleanup(patch.stop)
        self.asked = []

    def offer(self, bundle, answer="go", copy_exit=0, ask_error=None, **failures):
        def ask(ctx, title, text, buttons):
            if ask_error and not self.asked:
                raise ask_error
            self.asked.append((title, text, [label for label, _ in buttons]))
            return answer if len(self.asked) == 1 else "close"
        with mock.patch.object(location, "_running_bundle", return_value=bundle), \
                mock.patch.object(location, "_ask", side_effect=ask), \
                mock.patch.object(location, "_quit_and_reopen", side_effect=failures.get("reopen_error")) as reopen, \
                mock.patch.object(move, "write_script", side_effect=failures.get("write_error"), wraps=move.write_script), \
                mock.patch.object(move, "run_copy", return_value=copy_exit) as run:
            shown = location._offer(mock.Mock(), self.home)
        return shown, run, reopen

    def test_only_from_a_movable_place_and_once_per_version(self):
        for bundle in ("/Applications/HST Office.app", self.home + "/Applications/HST Office.app", self.home + "/Desktop/HST Office.app"):
            self.assertFalse(self.offer(bundle)[0])
        self.assertEqual(self.asked, [])
        shown, run, reopen = self.offer(DMG, answer="later")
        self.assertTrue(shown)
        title, text, buttons = self.asked[0]
        self.assertEqual(title, "Chuyển HST Office vào thư mục Ứng dụng")
        self.assertIn("tệp cài đặt .dmg", text)
        self.assertTrue(text.endswith("Chuyển HST Office vào thư mục Ứng dụng?"))
        self.assertEqual(buttons, ["Chuyển", "Để sau"])
        run.assert_not_called()
        reopen.assert_not_called()
        self.assertFalse(self.offer(DMG)[0])  # same version: asked once
        self.release = {"release": "1.0.1"}
        self.assertTrue(self.offer(TRANSLOCATED, answer="later")[0])
        self.assertIn("vị trí tạm của macOS", self.asked[-1][1])

    def test_a_failure_before_the_question_does_not_use_up_the_version(self):
        with self.assertRaises(RuntimeError):  # offer_move_once turns this into False: no question was shown
            self.offer(DMG, ask_error=RuntimeError("no window yet"))
        self.assertFalse(location.offered("1.0.0", self.home))
        self.assertTrue(self.offer(DMG, answer="later")[0])
        self.assertTrue(location.offered("1.0.0", self.home))

    def test_move_copies_then_quits_and_reopens_from_applications(self):
        bundle = os.path.join(self.home, "Downloads", "HST Office.app")
        shown, run, reopen = self.offer(bundle)
        self.assertTrue(shown)
        self.assertIn("thư mục Tải về", self.asked[0][1])
        argv = run.call_args.args[0]
        self.assertEqual(argv[2:5], ["--copy", bundle, self.dest])
        self.assertEqual(argv[-1], move.script_sha256())
        self.assertTrue(os.access(argv[1], os.X_OK))
        reopen_argv = reopen.call_args.args[1]
        self.assertEqual(reopen_argv[2:5], ["--reopen", str(os.getpid()), self.dest])
        self.assertEqual(reopen_argv[-1], bundle)  # the copy in Downloads is moved, not duplicated

    def test_disk_image_and_translocated_copies_are_never_removed(self):
        for bundle, release in ((DMG, "1.0.0"), (TRANSLOCATED, "1.0.1")):
            self.asked.clear()
            self.release = {"release": release}
            with self.subTest(bundle=bundle):
                self.assertEqual(len(self.offer(bundle)[2].call_args.args[1]), 6)

    def test_existing_copy_in_applications_is_opened_by_its_path_after_this_copy_quits(self):
        os.makedirs(self.dest)
        for bundle, release in ((DMG, "1.0.0"), (TRANSLOCATED, "1.0.1"), (self.home + "/Downloads/HST Office.app", "1.0.2")):
            self.asked.clear()
            self.release = {"release": release}
            with self.subTest(bundle=bundle):
                shown, run, reopen = self.offer(bundle)
                self.assertTrue(shown)
                self.assertEqual(self.asked[0][1:], (VI["move_exists"], ["Mở", "Để sau"]))
                run.assert_not_called()
                argv = reopen.call_args.args[1]
                self.assertEqual((argv[2:5], len(argv)), (["--reopen", str(os.getpid()), self.dest], 6))

    def test_every_failure_after_the_click_is_told_and_the_question_counts_as_shown(self):
        cases = [("copy failed", {"copy_exit": 1}, VI["move_failed"] % os.path.join(self.home, "cache", "move.log")),
                 ("copy still running", {"copy_exit": move.TIMED_OUT}, VI["move_slow"]),
                 ("script not written", {"write_error": OSError("read-only cache")}, VI["move_error"]),
                 ("helper not started", {"reopen_error": OSError("spawn failed")}, VI["move_error"])]
        for index, (label, failure, message) in enumerate(cases):
            self.asked.clear()
            self.release = {"release": "1.0.%d" % index}
            with self.subTest(label):
                self.assertTrue(self.offer(DMG, **failure)[0])
                self.assertEqual(self.asked[1][1:], (message, ["Đóng"]))
        self.asked.clear()
        self.release = {"release": "2.0.0"}
        self.assertTrue(self.offer('/Volumes/HST "Office"/HST Office.app')[0])  # rejected by the path rule after the click
        self.assertEqual(self.asked[1][1], VI["move_error"])

    def test_cancelled_password_shows_nothing_more(self):
        shown, _, reopen = self.offer(DMG, copy_exit=move.CANCELLED)
        self.assertTrue(shown)
        self.assertEqual(len(self.asked), 1)
        reopen.assert_not_called()

    def test_public_hook_is_quiet_off_macos_and_on_errors(self):
        with mock.patch.object(location.platform, "system", return_value="Linux"), mock.patch.object(location, "_offer") as offer:
            self.assertFalse(location.offer_move_once(mock.Mock()))
        offer.assert_not_called()
        with mock.patch.object(location.platform, "system", return_value="Darwin"), \
                mock.patch.object(location, "_offer", side_effect=RuntimeError("no office")):
            self.assertFalse(location.offer_move_once(mock.Mock()))


class QuitAndReopen(unittest.TestCase):
    def test_waiter_starts_first_and_stops_when_the_quit_is_cancelled(self):
        argv = ["/bin/sh", "/c/s.sh", "--reopen", "7", "/Applications/HST Office.app", "/c/l"]
        for closing in (True, False):
            with self.subTest(closing=closing), mock.patch("hst_office.update_launch.spawn") as spawn, \
                    mock.patch("hst_office.update_launch.cancel") as cancel:
                ctx, calls = mock.Mock(), []
                spawn.side_effect = lambda argv, system: calls.append(("spawn", argv, system)) or "proc"
                desktop = ctx.ServiceManager.createInstanceWithContext.return_value
                desktop.setPropertyValue.side_effect = lambda name, value: calls.append(("set", name, value))
                desktop.terminate.side_effect = lambda: calls.append(("terminate",)) or closing
                location._quit_and_reopen(ctx, argv)
                # The quick starter's veto (macOS Dock menu) is lifted, else terminate() only closes the windows.
                self.assertEqual(calls[:3], [("spawn", argv, "Darwin"), ("set", "SuspendQuickstartVeto", True), ("terminate",)])
                self.assertEqual(cancel.call_args_list, [] if closing else [mock.call("proc")])


if __name__ == "__main__":
    unittest.main()
