# SPDX-License-Identifier: AGPL-3.0-only
"""The macOS updater against a user who opens HST Office again while it installs: the checks and the copy run while
the office is still open, the swap waits for (or refuses) an office running from the app, the update lock goes before
the relaunch, and an old office still running is reported instead of being brought to the front."""
import os
from pathlib import Path
import signal
import subprocess
import unittest

import _paths  # noqa: F401
from hst_office import update_helper_cmd as cmd
from hst_office import update_outcome as outcome
from hst_office.update_texts import TEXTS
from update_helper_harness import HAS_SHELL, MacHarness, stub_osascript

STAGED_SUFFIX = ".hst-new"


@unittest.skipUnless(HAS_SHELL and Path("/proc/self/exe").exists(), "POSIX shell tools and /proc required")
class OfficeOpenedDuringTheUpdate(MacHarness):
    def setUp(self):
        super().setUp()
        stub_osascript(self)
        self.staged = Path(str(self.destination) + STAGED_SUFFIX)
        self.lock = self.root / "updating.lock"
        self.lock.write_text('{"schema":1,"helper":1,"office":1,"time":0}', encoding="ascii")
        # Relaunch record: was the lock already gone when the app was opened?
        self.stub("open", 'printf "%s\\n" "$@" > "$RECORDS/open-args"\n'
                  '[ -e "$RECORDS/updating.lock" ] && echo locked > "$RECORDS/open-lock"\nexit 0\n')

    def notifications(self):
        path = self.root / "notifications"
        return path.read_text(encoding="utf-8") if path.exists() else ""

    def test_checks_and_staging_run_while_the_office_is_still_open(self):
        office = subprocess.Popen(["sleep", "30"], env=self.process_vars)  # this office is not run from the app
        self.addCleanup(lambda: (office.kill(), office.wait()))
        helper = self.start(pid=office.pid)
        log = self.wait_for_log("Waiting for process")
        self.assertIn("Staged app is ready", log)
        self.assertEqual((self.staged / "version").read_text(), "new")
        self.assertEqual((self.destination / "version").read_text(), "old")
        self.assertFalse((self.root / "open-args").exists())
        office.kill()
        office.wait()
        self.assertEqual(helper.wait(timeout=15), 0, self.log.read_text())
        log = self.log.read_text()
        self.assertLess(log.index("Staged app is ready"), log.index("Process exited"))
        self.assertLess(log.index("Process exited"), log.index("Moving old app aside"))
        self.assertNotIn("Staging app beside destination", log[log.index("Process exited"):])
        self.assertEqual((self.destination / "version").read_text(), "new")
        self.assertFalse(self.staged.exists())
        self.assertEqual((self.root / "open-args").read_text().splitlines(), [str(self.destination)])
        self.assertFalse((self.root / "open-lock").exists())
        self.assertFalse(self.lock.exists())
        self.assertIn(TEXTS["vi"]["helper_installing"], self.notifications())

    def test_cancel_at_the_save_prompt_removes_the_staged_copy(self):
        office = subprocess.Popen(["sleep", "30"], env=self.process_vars)
        self.addCleanup(lambda: (office.kill(), office.wait()))
        helper = self.start(pid=office.pid)
        self.wait_for_log("Waiting for process")
        os.killpg(helper.pid, signal.SIGTERM)  # update_launch.cancel
        helper.wait(timeout=15)
        log = self.log.read_text()
        self.assertIn("Stopped before installing", log)
        self.assertFalse(self.staged.exists())
        self.assertEqual((self.destination / "version").read_text(), "old")
        self.assertFalse((self.root / "open-args").exists())
        self.assertIn("detach", (self.root / "hdiutil-args").read_text())
        self.assertFalse(self.lock.exists())
        self.assertIsNone(outcome.take(str(self.root), ""))

    def test_swap_refused_while_an_office_runs_from_the_app(self):
        self.start_office_from_app()
        self.fast_sleep()
        log = self.execute("Darwin", expected=75, release_from="1.0.4", release_to="1.0.5")
        self.assertIn("Swap refused: HST Office still runs from the app after 60 seconds", log)
        self.assertNotIn("Moving old app aside", log)
        self.assertEqual((self.destination / "version").read_text(), "old")
        self.assertFalse(self.staged.exists())
        self.assertFalse(Path(str(self.destination) + ".hst-old").exists())
        self.assertTrue(self.installer.exists())
        self.assertIn("Relaunch skipped", log)
        self.assertFalse((self.root / "open-args").exists())  # `open` would only bring the old office forward
        notes = self.notifications()
        self.assertIn(TEXTS["vi"]["helper_busy"], notes)
        self.assertIn(TEXTS["vi"]["helper_busy_failed"], notes)
        self.assertNotIn(TEXTS["vi"]["helper_old_running"], notes)
        self.assertFalse(self.lock.exists())
        self.assertEqual(outcome.take(str(self.root), "1.0.4"),
                         {"schema": 1, "code": "busy", "exit": 75, "from": "1.0.4", "to": "1.0.5"})

    def test_swap_waits_until_the_office_started_meanwhile_has_quit(self):
        office = self.start_office_from_app()
        self.fast_sleep(end_office_after=(3, office))
        log = self.execute("Darwin")
        self.assertIn("waiting for it to quit", log)
        self.assertIn("The app is no longer in use", log)
        self.assertLess(log.index("The app is no longer in use"), log.index("Moving old app aside"))
        self.assertEqual((self.destination / "version").read_text(), "new")
        self.assertEqual((self.root / "open-args").read_text().splitlines(), [str(self.destination)])

    def test_failed_install_does_not_bring_an_old_office_forward(self):
        self.start_office_from_app()
        self.process_vars["VERIFY_FAIL"] = "1"
        log = self.execute("Darwin", expected=1)
        self.assertIn("Relaunch skipped", log)
        self.assertFalse((self.root / "open-args").exists())
        self.assertIn(TEXTS["vi"]["helper_old_running"], self.notifications())

    def test_staging_copy_left_by_a_stopped_update_is_replaced(self):
        self.staged.mkdir()
        (self.staged / "version").write_text("partial", encoding="utf-8")
        log = self.execute("Darwin")
        self.assertIn("Removing a staging copy left by an earlier update", log)
        self.assertEqual((self.destination / "version").read_text(), "new")
        self.assertFalse(self.staged.exists())

    def test_notices_follow_the_language_passed_by_the_office(self):
        english = {name: TEXTS["en"]["helper_" + name] for name in cmd.MAC_NOTICES}
        self.fast_sleep()
        self.start_office_from_app()
        self.execute("Darwin", expected=75, notices=english)
        notes = self.notifications()
        self.assertIn(TEXTS["en"]["helper_busy_failed"], notes)
        self.assertNotIn(TEXTS["vi"]["helper_busy_failed"], notes)


class Notices(unittest.TestCase):
    def test_every_notice_exists_in_both_languages_and_fits_an_applescript_string(self):
        for language in ("vi", "en"):
            notices = {name: TEXTS[language]["helper_" + name] for name in cmd.MAC_NOTICES}
            self.assertEqual(cmd.mac_notices(notices), notices)

    def test_unsafe_or_incomplete_notices_are_refused(self):
        good = {name: "x" for name in cmd.MAC_NOTICES}
        for bad in ({}, dict(good, extra="x"), dict(good, busy='say "hi"'), dict(good, busy="a\\b"),
                    dict(good, busy="two\nlines"), dict(good, busy=""), dict(good, busy=1), "text"):
            with self.subTest(bad=bad):
                with self.assertRaises(ValueError):
                    cmd.mac_notices(bad)


if __name__ == "__main__":
    unittest.main()
