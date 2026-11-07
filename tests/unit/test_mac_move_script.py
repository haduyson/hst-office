# SPDX-License-Identifier: AGPL-3.0-only
"""The start-up move script (mac_move_script) run with stubbed macOS tools: verified copy, administrator path, reopen."""
import hashlib
import os
import shutil
import subprocess
import tempfile
import time
import unittest
from unittest import mock

import _paths  # noqa: F401
from hst_office import mac_move_script as move
from hst_office import update_helper_cmd as cmd
from update_helper_harness import HAS_SHELL, ShellHarness


class Script(unittest.TestCase):
    @unittest.skipUnless(HAS_SHELL, "POSIX shell tools required")
    def test_syntax_and_safety_checks(self):
        text = move.script_text()
        self.assertEqual(subprocess.run(["/bin/sh", "-n"], input=text, text=True, capture_output=True).returncode, 0)
        for part in ("safe_path()", "TeamIdentifier=" + cmd.TEAM_ID, 'spctl --assess --type execute "$source"',
                     'verify "$source"', "with administrator privileges", '"$HOME"/Downloads/*.app'):
            self.assertIn(part, text)
        if shutil.which("shellcheck"):
            result = subprocess.run(["shellcheck", "-s", "sh", "--severity=warning", "-"], input=text, text=True, capture_output=True)
            self.assertEqual(result.returncode, 0, result.stdout)

    def test_argv_and_validation(self):
        digest = move.script_sha256()
        self.assertEqual(move.copy_argv("/c/hst-move.sh", "/Volumes/H/HST Office.app", "/Applications/HST Office.app", "/c/move.log"),
                         ["/bin/sh", "/c/hst-move.sh", "--copy", "/Volumes/H/HST Office.app", "/Applications/HST Office.app", "/c/move.log", digest])
        self.assertEqual(len(digest), 64)
        self.assertEqual(move.reopen_argv("/c/s.sh", 42, "/Applications/HST Office.app", "/c/l", "/Users/a/Downloads/HST Office.app"),
                         ["/bin/sh", "/c/s.sh", "--reopen", "42", "/Applications/HST Office.app", "/c/l", "/Users/a/Downloads/HST Office.app"])
        for bad in ('/a/"x.app', "/a/x\\y.app", "relative.app", "/a/x\ny.app", "/a/not-a-bundle"):
            with self.subTest(bad=bad), self.assertRaises(ValueError):
                move.copy_argv("/c/s.sh", bad, "/Applications/HST Office.app", "/c/l")
        for pid in (0, -3, True, "4"):
            with self.subTest(pid=pid), self.assertRaises(ValueError):
                move.reopen_argv("/c/s.sh", pid, "/A/H.app", "/c/l")

    def test_copy_wait_reports_a_timeout_without_stopping_and_stops_on_other_errors(self):
        from hst_office import update_launch as launch
        proc = mock.Mock()
        for error, expected, cancelled in ((launch.subprocess.TimeoutExpired("sh", 1), move.TIMED_OUT, False), (OSError("x"), 1, True)):
            proc.wait.side_effect = error
            with self.subTest(expected=expected), mock.patch.object(launch, "spawn", return_value=proc) as spawn, \
                    mock.patch.object(launch, "cancel") as cancel, mock.patch("traceback.print_exc"):
                self.assertEqual(move.run_copy(["/bin/sh", "/c/s.sh", "--copy"], timeout=1), expected)
            spawn.assert_called_once_with(["/bin/sh", "/c/s.sh", "--copy"], "Darwin")
            self.assertEqual(cancel.called, cancelled)
        proc.wait.side_effect, proc.wait.return_value = None, 0
        with mock.patch.object(launch, "spawn", return_value=proc):
            self.assertEqual(move.run_copy(["/bin/sh"]), 0)

    def test_script_folder_is_private_and_the_log_is_capped(self):
        with tempfile.TemporaryDirectory() as temp:
            folder = os.path.join(temp, "cache")
            os.makedirs(folder)
            os.chmod(folder, 0o777)
            path = move.write_script(folder)
            self.assertEqual(oct(os.stat(folder).st_mode & 0o777), "0o700")
            self.assertEqual(oct(os.stat(path).st_mode & 0o777), "0o700")
            with open(path, "rb") as handle:
                self.assertEqual(hashlib.sha256(handle.read()).hexdigest(), move.script_sha256())
            link = os.path.join(temp, "link")
            os.symlink(folder, link)
            with self.assertRaises(OSError):
                move.write_script(link)
            log = os.path.join(folder, move.LOG_NAME)
            with open(log, "wb") as handle:
                handle.write(b"x" * (move.LOG_LIMIT + 1))
            move.cap_log(log)
            self.assertFalse(os.path.exists(log))
            self.assertEqual(os.path.getsize(log + ".1"), move.LOG_LIMIT + 1)
            move.cap_log(log)  # missing log: nothing to do


@unittest.skipUnless(HAS_SHELL, "POSIX shell tools required")
class MoveScript(ShellHarness):
    def setUp(self):
        super().setUp()
        self.source = self.root / "Downloads" / "HST Office.app"
        self.source.mkdir(parents=True)
        (self.source / "version").write_text("moved", encoding="utf-8")
        self.apps = self.root / "Applications"
        self.apps.mkdir()
        self.dest = self.apps / "HST Office.app"
        self.process_vars["HOME"] = str(self.root)
        self.stub("codesign", 'case "$1" in --verify) exit "${VERIFY_FAIL:-0}" ;; -dv) printf "TeamIdentifier=%s\\n" "$TEAM_ID" >&2 ;; esac\n')
        self.stub("spctl", 'exit "${SPCTL_FAIL:-0}"\n')
        self.stub("ditto", 'cp -R "$1" "$2"\n')
        self.stub("xattr", 'printf "%s\\n" "$@" > "$RECORDS/xattr-args"\n')
        self.stub("open", 'printf "%s\\n" "$@" > "$RECORDS/open-args"\n')
        self.script = move.write_script(self.root / "cache")
        self.move_log = self.root / "move.log"

    def run_script(self, *args):
        return subprocess.run(["/bin/sh", self.script, *map(str, args)], env=self.process_vars, timeout=15).returncode

    def copy(self, dest=None):
        return self.run_script("--copy", self.source, dest or self.dest, self.move_log, move.script_sha256())

    def test_copy_verifies_installs_and_clears_quarantine_on_the_copy(self):
        self.assertEqual(self.copy(), 0)
        self.assertEqual((self.dest / "version").read_text(), "moved")
        self.assertTrue(self.source.exists())  # removed only after the office quit, by --reopen
        self.assertEqual((self.root / "xattr-args").read_text().splitlines(), ["-dr", "com.apple.quarantine", str(self.dest) + ".hst-new"])
        self.assertEqual(oct(os.stat(self.script).st_mode & 0o777), "0o700")

    def test_copy_refuses_an_existing_destination_and_an_unverified_source(self):
        self.dest.mkdir()
        self.assertEqual(self.copy(), 1)
        self.assertIn("destination exists", self.move_log.read_text())
        self.dest.rmdir()
        for failure in ("VERIFY_FAIL", "SPCTL_FAIL"):
            with self.subTest(failure=failure):
                self.process_vars[failure] = "1"
                self.assertEqual(self.copy(), 1)
                self.assertFalse(self.dest.exists())
                del self.process_vars[failure]

    def test_locked_applications_asks_for_the_administrator_and_reports_a_cancel(self):
        dest = self.root / "Locked" / "HST Office.app"  # a missing folder is never writable, even for root
        self.stub("osascript", 'printf "%s\\n" "$@" > "$RECORDS/osascript-args"\nprintf "User canceled. (-128)\\n"\nexit 1\n')
        self.assertEqual(self.copy(dest), move.CANCELLED)
        request = (self.root / "osascript-args").read_text()
        self.assertIn('quoted form of "' + str(dest) + '"', request)
        self.assertIn("with administrator privileges", request)
        self.stub("osascript", 'printf "execution error (1)\\n"\nexit 1\n')
        self.assertEqual(self.copy(dest), 1)

    def test_reopen_waits_removes_only_the_downloaded_copy_and_opens(self):
        self.dest.mkdir()
        keeper = subprocess.Popen([shutil.which("sleep"), "2"])
        waiter = subprocess.Popen(["/bin/sh", self.script, "--reopen", str(keeper.pid), str(self.dest), str(self.move_log), str(self.source)],
                                  env=self.process_vars)
        try:
            time.sleep(0.3)
            self.assertIsNone(waiter.poll())  # still waiting for the office to quit
            self.assertTrue(self.source.exists())
            keeper.wait(timeout=4)
            self.assertEqual(waiter.wait(timeout=5), 0)
        finally:
            for proc in (keeper, waiter):
                if proc.poll() is None:
                    proc.terminate()
                proc.wait(timeout=5)
        self.assertFalse(self.source.exists())
        self.assertEqual((self.root / "open-args").read_text().splitlines(), [str(self.dest)])
        elsewhere = self.root / "Desktop" / "HST Office.app"
        elsewhere.mkdir(parents=True)
        for kept in (elsewhere, self.root / "Downloads" / ".." / "Desktop" / "HST Office.app"):
            with self.subTest(kept=kept):
                self.assertEqual(self.run_script("--reopen", self.exited_pid, self.dest, self.move_log, kept), 0)
                self.assertTrue(elsewhere.exists())

    def test_reopen_without_a_copy_to_remove_opens_the_destination_by_path(self):
        self.dest.mkdir()
        self.assertEqual(self.run_script("--reopen", self.exited_pid, self.dest, self.move_log), 0)
        self.assertEqual((self.root / "open-args").read_text().splitlines(), [str(self.dest)])
        self.assertTrue(self.source.exists())
        self.assertFalse((self.root / "xattr-args").exists())  # the existing copy's attributes are left alone

    def test_unknown_mode_is_refused(self):
        self.assertEqual(self.run_script("--other"), 64)


if __name__ == "__main__":
    unittest.main()
