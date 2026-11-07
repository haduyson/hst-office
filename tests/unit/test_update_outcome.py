# SPDX-License-Identifier: AGPL-3.0-only
"""A failed "Cập nhật ngay" leaves one local record for the next start; a user's cancel leaves none."""
import json
import os
from pathlib import Path
import signal
import subprocess
import tempfile
import time
import unittest

import _paths  # noqa: F401
from hst_office import update_helper_cmd as cmd
from hst_office import update_outcome as outcome
from hst_office.update_texts import TEXTS
from update_helper_harness import HAS_SHELL, SHA256, ShellHarness


def record(**values):
    return dict({"schema": 1, "code": "install", "exit": 100, "from": "1.0.0-beta.5", "to": "1.0.0"}, **values)


class Reader(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / outcome.STATE_NAME

    def write(self, value):
        self.path.write_text(value if isinstance(value, str) else json.dumps(value), encoding="ascii")

    def test_read_once(self):
        self.write(record())
        self.assertEqual(outcome.take(self.temp.name, "1.0.0-beta.5"), record())
        self.assertFalse(self.path.exists())
        self.assertIsNone(outcome.take(self.temp.name, "1.0.0-beta.5"))

    def test_another_version_running_drops_the_record(self):
        self.write(record())
        self.assertIsNone(outcome.take(self.temp.name, "1.0.0"))
        self.assertFalse(self.path.exists())

    def test_malformed_records_are_dropped(self):
        for bad in ("", "{", "[]", record(schema=2), record(code="cancel"), record(exit="100"), record(to=None), "x" * 2000):
            with self.subTest(bad=str(bad)[:40]):
                self.write(bad)
                self.assertIsNone(outcome.take(self.temp.name, "1.0.0-beta.5"))
                self.assertFalse(self.path.exists())

    def test_symlink_is_not_followed(self):
        target = Path(self.temp.name) / "target"
        target.write_text(json.dumps(record()), encoding="ascii")
        self.path.symlink_to(target)
        self.assertIsNone(outcome.take(self.temp.name, "1.0.0-beta.5"))

    def test_every_code_has_a_message_in_both_languages(self):
        for language in ("vi", "en"):
            for code in outcome.CODES:
                text = outcome.message(TEXTS[language], record(code=code), "/x/update.log")
                self.assertIn("HST Office 1.0.0", text)
                self.assertIn("/x/update.log", text)
                self.assertNotIn("%", text)
        self.assertIn("mã 100", outcome.message(TEXTS["vi"], record(), "/x"))
        self.assertIn("Tải về", outcome.message(TEXTS["vi"], record(to=""), "/x"))


@unittest.skipUnless(HAS_SHELL, "POSIX shell tools required")
class HelperRecords(ShellHarness):
    def setUp(self):
        super().setUp()
        self.state = self.root / outcome.STATE_NAME
        self.stub("apt-get", 'printf "apt says no\\n"\nexit "${APT_EXIT:-0}"\n')

    def run_helper(self, pkexec_exit=None, expected=1, **kwargs):
        self.stub("pkexec", 'exec "$@"\n' if pkexec_exit is None else "exit %d\n" % pkexec_exit)
        self.execute(expected=expected, release_from="1.0.0-beta.5", release_to="1.0.0", **kwargs)
        self.wait_for_file("relaunch")
        return outcome.take(str(self.root), "1.0.0-beta.5")

    def test_apt_error_is_recorded_and_logged(self):
        self.process_vars["APT_EXIT"] = "100"
        self.assertEqual(self.run_helper(expected=100), record())
        self.assertIn("apt says no", self.log.read_text(encoding="utf-8"))
        self.assertEqual(oct((self.root / "update.log").stat().st_mode & 0o77), "0o0")

    def test_polkit_denial_is_recorded(self):
        self.assertEqual(self.run_helper(pkexec_exit=127, expected=127), record(code="auth", exit=127))

    def test_dismissed_password_dialog_shows_nothing(self):
        self.assertIsNone(self.run_helper(pkexec_exit=126, expected=126))
        self.assertFalse(self.state.exists())

    def test_wrong_sha256_is_recorded(self):
        self.assertEqual(self.run_helper(sha256="0" * 64), record(code="verify", exit=1))

    def test_no_tool_is_recorded(self):
        self.execute(expected=1, release_from="1.0.0-beta.5", release_to="1.0.0")
        self.assertEqual(outcome.take(str(self.root), "1.0.0-beta.5")["code"], "tool")

    def test_wait_timeout_is_recorded(self):
        self.stub("sleep", "exit 0\n")
        self.assertEqual(self.run_helper(pid=os.getpid()), record(code="wait", exit=1))

    def test_success_clears_an_old_record(self):
        self.state.write_text(json.dumps(record()), encoding="ascii")
        self.assertIsNone(self.run_helper(expected=0))
        self.assertFalse(self.state.exists())

    def test_stopped_at_the_save_prompt_writes_nothing_and_does_not_relaunch(self):
        """launch.cancel: SIGTERM to the helper's session while the office, still open, is being waited for."""
        keeper = subprocess.Popen(["sleep", "60"])
        self.addCleanup(keeper.wait)
        self.addCleanup(keeper.kill)
        self.stub("pkexec", 'exec "$@"\n')
        helper = subprocess.Popen(self.prepare(pid=keeper.pid, release_from="1.0.0-beta.5", release_to="1.0.0"),
                                  env=self.process_vars, start_new_session=True)
        self.addCleanup(helper.wait)
        deadline = time.monotonic() + 5
        while time.monotonic() < deadline and "Waiting" not in (self.log.read_text() if self.log.exists() else ""):
            time.sleep(0.02)
        os.killpg(helper.pid, signal.SIGTERM)
        self.assertEqual(helper.wait(timeout=5), 1)
        time.sleep(0.5)
        self.assertFalse((self.root / "relaunch").exists())
        self.assertFalse(self.state.exists())
        self.assertIn("Stopped before installing", self.log.read_text())
        self.assertNotIn("Relaunching", self.log.read_text())


class HelperTemplates(unittest.TestCase):
    def build(self, system, **kwargs):
        paths = {"installer": "/c/p.deb", "soffice": "/o/soffice", "log": "/c/update.log", "app_dest": "/A/H.app"}
        if system == "Windows":
            paths = {"installer": r"C:\p.msi", "soffice": r"C:\o\soffice.exe", "log": r"C:\c\update.log"}
        return cmd.build_helper(system, pid=7, sha256=SHA256, **paths, **kwargs)

    def test_windows_records_failures_and_not_cancels(self):
        text = self.build("Windows", release_from="1.0.0-beta.5", release_to="1.0.0")["text"]
        for part in ("'update-result.json'", "from='1.0.0-beta.5'", "to='1.0.0'", "$fail = 'verify'", "$fail = 'wait'",
                     "$code -eq 1602", "$fail = 'cancel'", "Move-Item -LiteralPath \"$state.tmp\"", "Write-Failure $fail $code"):
            self.assertIn(part, text)
        self.assertLess(text.index("Write-Failure $fail $code"), text.index("Start-Process $Soffice"))
        self.assertNotIn("@FROM_RELEASE@", text)

    def test_mac_treats_the_cancelled_password_dialog_as_a_cancel(self):
        text = self.build("Darwin")["text"]
        self.assertIn("*'(-128)'*) FAIL=cancel", text)
        self.assertIn("FAIL=verify\n    verify \"$app\"", text)

    def test_release_text_is_validated(self):
        for system in ("Linux", "Darwin", "Windows"):
            for bad in ("1.0'; rm -rf /", "a b", '"', "x" * 65, None):
                with self.subTest(system=system, bad=bad), self.assertRaisesRegex(ValueError, "release"):
                    self.build(system, release_to=bad)


if __name__ == "__main__":
    unittest.main()
