# SPDX-License-Identifier: AGPL-3.0-only
"""Where the macOS app runs, where the updater installs, and the once-per-version move offer (no office needed)."""
import os
import tempfile
import unittest
from unittest import mock

import _paths  # noqa: F401
from hst_office import mac_app_location as location
from hst_office.update_texts import TEXTS

HOME = "/Users/an"
TRANSLOCATED = "/private/var/folders/xy/T/AppTranslocation/0A1B-2C3D/d/HST Office.app"


class Locate(unittest.TestCase):
    def test_kinds(self):
        cases = {"/Volumes/HST Office/HST Office.app": "volume", HOME + "/Downloads/HST Office.app": "downloads",
                 HOME + "/Downloads/new/HST Office.app": "downloads", "/Applications/HST Office.app": "applications",
                 HOME + "/Applications/HST Office.app": "user-applications", HOME + "/Desktop/HST Office.app": "other",
                 "/Applications-old/HST Office.app": "other", HOME + "/Downloads.app": "other", TRANSLOCATED: "translocated"}
        for bundle, kind in cases.items():
            with self.subTest(bundle=bundle):
                place = location.locate(bundle, HOME)
                self.assertEqual(place["kind"], kind)
                self.assertEqual(place["translocated"], kind == "translocated")
                self.assertEqual(place["source"], bundle)
                self.assertEqual(place["remove"], bundle if kind == "downloads" else None)

    def test_paths_are_normalised(self):
        self.assertEqual(location.locate(HOME + "/Downloads/../Desktop/HST Office.app", HOME)["kind"], "other")
        self.assertEqual(location.locate("/Volumes/HST Office/HST Office.app/", HOME)["source"], "/Volumes/HST Office/HST Office.app")


class UpdateTarget(unittest.TestCase):
    def test_targets(self):
        cases = [("/Volumes/HST Office/HST Office.app", False, location.DESTINATION),
                 ("/Volumes/Data/HST Office.app", True, "/Volumes/Data/HST Office.app"),
                 ("/Applications/HST Office.app", False, "/Applications/HST Office.app"),  # administrator swap in place
                 ("/Applications/HST Office.app", True, "/Applications/HST Office.app"),
                 (HOME + "/Downloads/HST Office.app", True, HOME + "/Downloads/HST Office.app"),
                 (HOME + "/Applications/HST Office.app", False, location.DESTINATION),
                 (HOME + "/Applications/HST Office.app", True, HOME + "/Applications/HST Office.app"),
                 (TRANSLOCATED, False, location.DESTINATION), (TRANSLOCATED, True, location.DESTINATION)]
        for bundle, writable, expected in cases:
            with self.subTest(bundle=bundle, writable=writable):
                self.assertEqual(location.update_target(bundle, HOME, lambda path, w=writable: w), expected)

    def test_writable_needs_the_bundle_and_its_folder(self):
        with tempfile.TemporaryDirectory() as temp:
            bundle = os.path.join(temp, "HST Office.app")
            os.mkdir(bundle)
            self.assertTrue(location._writable(bundle))
            self.assertFalse(location._writable(os.path.join(temp, "missing", "HST Office.app")))


class Arguments(unittest.TestCase):
    def test_argv_and_validation(self):
        self.assertEqual(location.copy_argv("/c/hst-move.sh", "/Volumes/H/HST Office.app", "/Applications/HST Office.app", "/c/move.log"),
                         ["/bin/sh", "/c/hst-move.sh", "--copy", "/Volumes/H/HST Office.app", "/Applications/HST Office.app", "/c/move.log"])
        self.assertEqual(location.reopen_argv("/c/s.sh", 42, "/Applications/HST Office.app", "/c/l", "/Users/a/Downloads/HST Office.app"),
                         ["/bin/sh", "/c/s.sh", "--reopen", "42", "/Applications/HST Office.app", "/c/l", "/Users/a/Downloads/HST Office.app"])
        self.assertEqual(len(location.reopen_argv("/c/s.sh", 42, "/A/H.app", "/c/l")), 6)
        for bad in ('/a/"x.app', "/a/x\\y.app", "relative.app", "/a/x\ny.app", "/a/not-a-bundle"):
            with self.subTest(bad=bad), self.assertRaises(ValueError):
                location.copy_argv("/c/s.sh", bad, "/Applications/HST Office.app", "/c/l")
        for pid in (0, -3, True, "4"):
            with self.subTest(pid=pid), self.assertRaises(ValueError):
                location.reopen_argv("/c/s.sh", pid, "/A/H.app", "/c/l")

    def test_copy_timeout_stops_the_step_and_fails(self):
        proc = mock.Mock()
        proc.wait.side_effect = TimeoutError("too slow")
        with mock.patch("hst_office.update_launch.spawn", return_value=proc) as spawn, \
                mock.patch("hst_office.update_launch.cancel") as cancel, mock.patch("traceback.print_exc"):
            self.assertEqual(location.copy(["/bin/sh", "/c/s.sh", "--copy"]), 1)
        spawn.assert_called_once_with(["/bin/sh", "/c/s.sh", "--copy"], "Darwin")
        cancel.assert_called_once_with(proc)


class OfferOnce(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.home = self.temp.name
        self.dest = os.path.join(self.home, "Applications", "HST Office.app")
        for patch in (mock.patch.object(location, "DESTINATION", self.dest),
                      mock.patch("hst_office.update_texts.texts", return_value=TEXTS["vi"]),
                      mock.patch("hst_office.update_fetch.release_info", return_value={"release": "1.0.0"}),
                      mock.patch("hst_office.update_installer.cache_dir", return_value=os.path.join(self.home, "cache"))):
            patch.start()
            self.addCleanup(patch.stop)
        self.asked = []

    def offer(self, bundle, answer="go", copy_exit=0):
        def ask(ctx, title, text, buttons):
            self.asked.append((title, text, [label for label, _ in buttons]))
            return answer if len(self.asked) == 1 else "close"
        with mock.patch.object(location, "_running_bundle", return_value=bundle), \
                mock.patch.object(location, "_ask", side_effect=ask), \
                mock.patch.object(location, "_quit_and_reopen") as reopen, \
                mock.patch.object(location, "copy", return_value=copy_exit) as run:
            shown = location._offer(mock.Mock(), self.home)
        return shown, run, reopen

    def test_only_from_a_movable_place_and_once_per_version(self):
        for bundle in ("/Applications/HST Office.app", self.home + "/Applications/HST Office.app", self.home + "/Desktop/HST Office.app"):
            self.assertFalse(self.offer(bundle)[0])
        self.assertEqual(self.asked, [])
        shown, run, reopen = self.offer("/Volumes/HST Office/HST Office.app", answer="later")
        self.assertTrue(shown)
        title, text, buttons = self.asked[0]
        self.assertEqual(title, "Chuyển HST Office vào thư mục Ứng dụng")
        self.assertIn("tệp cài đặt .dmg", text)
        self.assertTrue(text.endswith("Chuyển HST Office vào thư mục Ứng dụng?"))
        self.assertEqual(buttons, ["Chuyển", "Để sau"])
        run.assert_not_called()
        reopen.assert_not_called()
        self.assertFalse(self.offer("/Volumes/HST Office/HST Office.app")[0])  # same version: asked once
        with mock.patch("hst_office.update_fetch.release_info", return_value={"release": "1.0.1"}):
            self.assertTrue(self.offer(TRANSLOCATED, answer="later")[0])
        self.assertIn("vị trí tạm của macOS", self.asked[-1][1])

    def test_move_copies_then_quits_and_reopens_from_applications(self):
        bundle = os.path.join(self.home, "Downloads", "HST Office.app")
        shown, run, reopen = self.offer(bundle)
        self.assertTrue(shown)
        self.assertIn("thư mục Tải về", self.asked[0][1])
        argv = run.call_args.args[0]
        self.assertEqual(argv[2:5], ["--copy", bundle, self.dest])
        self.assertTrue(os.access(argv[1], os.X_OK))
        reopen_argv = reopen.call_args.args[1]
        self.assertEqual(reopen_argv[2:5], ["--reopen", str(os.getpid()), self.dest])
        self.assertEqual(reopen_argv[-1], bundle)  # the copy in Downloads is moved, not duplicated

    def test_disk_image_and_translocated_copies_are_never_removed(self):
        for bundle, release in (("/Volumes/HST Office/HST Office.app", "1.0.0"), (TRANSLOCATED, "1.0.1")):
            self.asked.clear()
            with self.subTest(bundle=bundle), mock.patch("hst_office.update_fetch.release_info", return_value={"release": release}):
                self.assertEqual(len(self.offer(bundle)[2].call_args.args[1]), 6)

    def test_existing_copy_in_applications_is_opened_instead(self):
        os.makedirs(self.dest)
        shown, run, reopen = self.offer("/Volumes/HST Office/HST Office.app")
        self.assertTrue(shown)
        self.assertEqual(self.asked[0][1], TEXTS["vi"]["move_exists"])
        self.assertEqual(self.asked[0][2], ["Mở", "Để sau"])
        run.assert_not_called()
        self.assertEqual(len(reopen.call_args.args[1]), 6)

    def test_failed_move_says_so_and_cancelled_password_does_not(self):
        shown, _, reopen = self.offer("/Volumes/HST Office/HST Office.app", copy_exit=1)
        self.assertTrue(shown)
        reopen.assert_not_called()
        self.assertIn("Không chuyển được HST Office", self.asked[1][1])
        self.assertIn("move.log", self.asked[1][1])
        self.asked.clear()
        with mock.patch("hst_office.update_fetch.release_info", return_value={"release": "1.0.2"}):
            _, _, reopen = self.offer("/Volumes/HST Office/HST Office.app", copy_exit=location.CANCELLED)
        self.assertEqual(len(self.asked), 1)
        reopen.assert_not_called()

    def test_public_hook_is_quiet_off_macos_and_on_errors(self):
        with mock.patch.object(location.platform, "system", return_value="Linux"), mock.patch.object(location, "_offer") as offer:
            self.assertFalse(location.offer_move_once(mock.Mock()))
        offer.assert_not_called()
        with mock.patch.object(location.platform, "system", return_value="Darwin"), \
                mock.patch.object(location, "_offer", side_effect=RuntimeError("no office")), mock.patch("traceback.print_exc"):
            self.assertFalse(location.offer_move_once(mock.Mock()))


if __name__ == "__main__":
    unittest.main()
