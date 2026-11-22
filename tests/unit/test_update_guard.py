# SPDX-License-Identifier: AGPL-3.0-only
"""Start-up guard of "Cập nhật ngay" without an office: the update lock, and the macOS check that the app bundle on
disk still holds the version that runs."""
import os
import plistlib
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import _paths  # noqa: F401
import test_update_job  # noqa: F401 - installs the UNO module stubs before hst_office.update_guard is imported
from hst_office import update_guard as guard  # noqa: E402

NOW = 1_800_000_000


class Lock(unittest.TestCase):
    def setUp(self):
        self.cache = tempfile.mkdtemp()
        self.addCleanup(lambda: __import__("shutil").rmtree(self.cache, ignore_errors=True))

    def test_written_then_named_helper_then_removed(self):
        guard.write_lock(self.cache, office=11, now=NOW)
        self.assertEqual(guard.read_lock(self.cache), {"schema": 1, "helper": 0, "office": 11, "time": NOW})
        guard.write_lock(self.cache, helper=22, office=11, now=NOW)
        self.assertEqual(guard.read_lock(self.cache)["helper"], 22)
        guard.remove_lock(self.cache)
        guard.remove_lock(self.cache)  # already gone: no error
        self.assertIsNone(guard.read_lock(self.cache))

    def test_bad_helper_pid_is_refused(self):
        for bad in (-1, True, 1.5, "7", 2 ** 31):
            with self.subTest(bad=bad), self.assertRaises(ValueError):
                guard.write_lock(self.cache, helper=bad)

    def test_running_helper_means_an_update_is_installing(self):
        guard.write_lock(self.cache, helper=22, office=11, now=NOW)
        self.assertTrue(guard.update_in_progress(self.cache, now=NOW + 60, alive=lambda pid: pid == 22))
        self.assertTrue(os.path.exists(os.path.join(self.cache, guard.LOCK_NAME)))

    def test_ended_helper_or_old_lock_is_stale_and_removed(self):
        for helper, now, alive in ((22, NOW + 60, False), (22, NOW + guard.MAX_AGE + 1, True), (22, NOW - 5, True)):
            with self.subTest(helper=helper, now=now, alive=alive):
                guard.write_lock(self.cache, helper=helper, office=11, now=NOW)
                self.assertFalse(guard.update_in_progress(self.cache, now=now, alive=lambda pid: alive))
                self.assertIsNone(guard.read_lock(self.cache))

    def test_lock_without_helper_counts_only_while_it_is_being_started(self):
        guard.write_lock(self.cache, office=11, now=NOW)
        self.assertTrue(guard.update_in_progress(self.cache, now=NOW + 10, alive=lambda pid: False))
        self.assertFalse(guard.update_in_progress(self.cache, now=NOW + guard.SPAWN_GRACE + 1, alive=lambda pid: False))

    def test_own_lock_without_helper_is_not_an_update_of_someone_else(self):
        guard.write_lock(self.cache, office=os.getpid(), now=NOW)
        self.assertFalse(guard.update_in_progress(self.cache, now=NOW + 1))

    def test_broken_lock_is_removed(self):
        for content in (b"", b"{", b"[]", b'{"schema":2,"helper":1,"office":1,"time":1}', b"x" * 2000):
            with self.subTest(content=content):
                Path(self.cache, guard.LOCK_NAME).write_bytes(content)
                self.assertFalse(guard.update_in_progress(self.cache, now=NOW))
                self.assertFalse(os.path.exists(os.path.join(self.cache, guard.LOCK_NAME)))

    def test_pid_alive_of_this_and_of_an_ended_process(self):
        import subprocess
        self.assertTrue(guard.pid_alive(os.getpid(), "Linux"))
        ended = subprocess.Popen(["true"])
        ended.wait()
        self.assertFalse(guard.pid_alive(ended.pid, "Linux"))


class ReplacedBundle(unittest.TestCase):
    def setUp(self):
        self.bundle = Path(tempfile.mkdtemp()) / "HST Office.app"
        (self.bundle / "Contents").mkdir(parents=True)
        self.addCleanup(lambda: __import__("shutil").rmtree(self.bundle.parent, ignore_errors=True))

    def version(self, value):
        with open(self.bundle / "Contents" / "Info.plist", "wb") as handle:
            plistlib.dump({"CFBundleShortVersionString": value}, handle)

    def test_same_version_is_not_replaced(self):
        self.version("1.0.4")
        for release in ("1.0.4", "1.0.4-rc.2", "1.0.4-beta.1.1"):
            with self.subTest(release=release):
                self.assertIsNone(guard.replaced_bundle(str(self.bundle), release, "/Applications/HST Office.app/Contents/MacOS/soffice"))

    def test_other_version_on_disk_is_reported(self):
        self.version("1.0.5")
        self.assertEqual(guard.replaced_bundle(str(self.bundle), "1.0.4"), "1.0.5")

    def test_executable_moved_aside_by_the_swap_is_reported(self):
        self.version("1.0.4")  # Python loaded after the swap: release.json is already the new one
        self.assertEqual(guard.replaced_bundle(str(self.bundle), "1.0.4", "/Applications/HST Office.app.hst-old/Contents/MacOS/soffice"), "1.0.4")

    def test_unreadable_plist_or_release_changes_nothing(self):
        self.assertIsNone(guard.replaced_bundle(str(self.bundle), "1.0.4"))
        (self.bundle / "Contents" / "Info.plist").write_bytes(b"not a plist")
        self.assertIsNone(guard.replaced_bundle(str(self.bundle), "1.0.4"))
        self.version("1.0.5")
        self.assertIsNone(guard.replaced_bundle(str(self.bundle), "dev"))

    def test_reopen_is_not_repeated_for_the_same_versions(self):
        cache = str(self.bundle.parent / "cache")
        self.assertTrue(guard.reopen_due(cache, "1.0.4", "1.0.5", now=NOW))
        self.assertFalse(guard.reopen_due(cache, "1.0.4", "1.0.5", now=NOW + 60))
        self.assertTrue(guard.reopen_due(cache, "1.0.4", "1.0.6", now=NOW + 61))
        self.assertTrue(guard.reopen_due(cache, "1.0.4", "1.0.6", now=NOW + 61 + guard.REOPEN_PAUSE))


class StartUpCheck(unittest.TestCase):
    def setUp(self):
        self.cache = tempfile.mkdtemp()
        self.addCleanup(lambda: __import__("shutil").rmtree(self.cache, ignore_errors=True))
        self.later = []
        patches = (mock.patch("hst_office.update_installer.cache_dir", return_value=self.cache),
                   mock.patch("hst_office.update_ui.on_main_thread", side_effect=lambda ctx, fn: self.later.append(fn)))
        for patch in patches:
            patch.start()
            self.addCleanup(patch.stop)

    def test_copy_started_during_an_update_says_so_and_quits(self):
        guard.write_lock(self.cache, helper=os.getpid() + 0, office=1)
        with mock.patch.object(guard, "pid_alive", return_value=True):
            self.assertEqual(guard.check(mock.Mock(), "Linux"), "updating")
        with mock.patch.object(guard, "_tell") as tell, mock.patch("hst_office.update_launch.quit_office", return_value=True) as quit_, \
                mock.patch("hst_office.update_texts.texts", return_value={"guard_updating": "busy"}):
            self.later[0]()
        tell.assert_called_once_with(mock.ANY, "busy")
        quit_.assert_called_once()

    def test_nothing_pending_does_nothing_off_macos(self):
        self.assertIsNone(guard.check(mock.Mock(), "Windows"))
        self.assertEqual(self.later, [])

    def test_macos_bundle_replaced_reopens_after_quitting(self):
        bundle = Path(self.cache) / "HST Office.app"
        (bundle / "Contents").mkdir(parents=True)
        with open(bundle / "Contents" / "Info.plist", "wb") as handle:
            plistlib.dump({"CFBundleShortVersionString": "1.0.5"}, handle)
        with mock.patch("hst_office.update_install.office_paths", return_value=("x", str(bundle))), \
                mock.patch("hst_office.update_fetch.release_info", return_value={"release": "1.0.4"}), \
                mock.patch.object(guard, "own_executable", return_value=None):
            self.assertEqual(guard.check(mock.Mock(), "Darwin"), "replaced")
            self.assertIsNone(guard.check(mock.Mock(), "Darwin"))  # not twice within REOPEN_PAUSE
        with mock.patch("hst_office.update_launch.spawn") as spawn, mock.patch.object(guard, "_tell") as tell, \
                mock.patch("hst_office.update_launch.quit_office", return_value=True) as quit_, \
                mock.patch("hst_office.update_texts.texts", return_value={"guard_replaced": "%s / %s"}):
            self.later[0]()
        argv = spawn.call_args.args[0]
        self.assertEqual(argv[2:5], ["--reopen", str(os.getpid()), str(bundle)])
        tell.assert_called_once_with(mock.ANY, "1.0.5 / 1.0.4")
        quit_.assert_called_once()


class Registration(unittest.TestCase):
    def test_job_runs_at_start_up(self):
        root = Path(_paths.ROOT) / "extensions" / "hst-vietnamese-tools"
        jobs = (root / "Jobs.xcu").read_text(encoding="utf-8")
        start = jobs.index('<node oor:name="OnStartApp"')
        self.assertIn(guard.JOB_NAME, jobs[start:jobs.index("</node>\n    </node>", start)])
        self.assertIn('"update_guard", "UpdateGuardJob", "%s"' % guard.JOB_NAME,
                      (root / "python" / "hst_office_component.py").read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
