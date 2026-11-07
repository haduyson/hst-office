# SPDX-License-Identifier: AGPL-3.0-only
"""Where the macOS app runs, where the updater installs, and the copy running behind a progress message (no office)."""
import os
import tempfile
import threading
import unittest
from unittest import mock

import _paths  # noqa: F401
import test_update_job  # noqa: F401 - installs the UNO module stubs before hst_office.dialogs / update_ui are imported
from hst_office import mac_app_location as location  # noqa: E402

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
    def test_only_a_read_only_volume_or_a_translocated_bundle_goes_to_applications(self):
        cases = [("/Volumes/HST Office/HST Office.app", False, location.DESTINATION),
                 ("/Volumes/Data/HST Office.app", True, "/Volumes/Data/HST Office.app"),
                 (TRANSLOCATED, False, location.DESTINATION), (TRANSLOCATED, True, location.DESTINATION),
                 # Everything else is replaced where it is (administrator password when it cannot be written).
                 ("/Applications/HST Office.app", False, "/Applications/HST Office.app"),
                 ("/Applications/HST Office.app", True, "/Applications/HST Office.app"),
                 (HOME + "/Applications/HST Office.app", False, HOME + "/Applications/HST Office.app"),
                 (HOME + "/Applications/HST Office.app", True, HOME + "/Applications/HST Office.app"),
                 ("/Users/Shared/Apps/HST Office.app", False, "/Users/Shared/Apps/HST Office.app"),
                 (HOME + "/Downloads/HST Office.app", False, HOME + "/Downloads/HST Office.app"),
                 (HOME + "/Downloads/HST Office.app", True, HOME + "/Downloads/HST Office.app")]
        for bundle, writable, expected in cases:
            with self.subTest(bundle=bundle, writable=writable):
                self.assertEqual(location.update_target(bundle, HOME, lambda path, w=writable: w), expected)

    def test_writable_needs_the_bundle_and_its_folder(self):
        with tempfile.TemporaryDirectory() as temp:
            bundle = os.path.join(temp, "HST Office.app")
            os.mkdir(bundle)
            self.assertTrue(location._writable(bundle))
            self.assertFalse(location._writable(os.path.join(temp, "missing", "HST Office.app")))


class FakeDialog:
    """Modal until end() is called, like dialogs.Dialog; records what it showed."""
    shown = []

    def __init__(self, ctx, title, width, height):
        self.ended = threading.Event()
        FakeDialog.shown.append(title)

    def label(self, name, text, *geometry, **options):
        FakeDialog.shown.append(text)

    def end(self, code=1):
        self.ended.set()

    def execute(self, peer=None):
        return 1 if self.ended.wait(5) else 0


class Progress(unittest.TestCase):
    def setUp(self):
        FakeDialog.shown = []
        for patch in (mock.patch("hst_office.dialogs.Dialog", FakeDialog), mock.patch.object(location, "_peer", return_value=None),
                      mock.patch("hst_office.update_ui.on_main_thread", side_effect=lambda ctx, fn: fn())):
            patch.start()
            self.addCleanup(patch.stop)

    def test_the_copy_runs_off_the_main_thread_while_the_message_shows(self):
        threads = []

        def work():
            threads.append(threading.current_thread())
            return 0
        self.assertEqual(location._with_progress(mock.Mock(), "Chuyển", "Đang chuyển HST Office vào thư mục Ứng dụng…", work), 0)
        self.assertNotEqual(threads, [threading.current_thread()])
        self.assertEqual(FakeDialog.shown, ["Chuyển", "Đang chuyển HST Office vào thư mục Ứng dụng…"])

    def test_a_failing_copy_counts_as_a_failed_move(self):
        def work():
            raise OSError("spawn failed")
        with mock.patch("traceback.print_exc"):
            self.assertEqual(location._with_progress(mock.Mock(), "t", "m", work), 1)


if __name__ == "__main__":
    unittest.main()
