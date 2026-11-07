# SPDX-License-Identifier: AGPL-3.0-only
"""macOS swap safety: every check of the staged copy runs before its quarantine flag is cleared, the administrator step
runs only an unchanged copy of the script, and a failure that reopens nothing still tells the user."""
import hashlib
from pathlib import Path
import subprocess
import tempfile
import unittest

import _paths  # noqa: F401
from hst_office import update_helper_cmd as cmd
from hst_office import update_helper_scripts as scripts
from update_helper_harness import HAS_SHELL, MacHarness, stub_osascript

PYTHON_AND_SHASUM = Path("/usr/bin/shasum").exists() and Path("/usr/bin/mktemp").exists()


@unittest.skipUnless(HAS_SHELL, "POSIX shell tools required")
class StagedChecks(MacHarness):
    def test_success_assesses_the_staged_copy_before_clearing_its_quarantine(self):
        self.execute("Darwin")
        staged = str(self.destination) + ".hst-new"
        self.assertIn(staged, (self.root / "spctl-args").read_text().splitlines())
        self.assertEqual((self.root / "xattr-args").read_text().splitlines(), ["-dr", "com.apple.quarantine", staged])
        self.assertEqual((self.destination / "version").read_text(), "new")

    def test_a_failed_staged_check_skips_xattr_and_installs_nothing(self):
        for name, value in (("STAGED_VERIFY_FAIL", "1"), ("STAGED_TEAM", "WRONG"), ("STAGED_SPCTL_FAIL", "1")):
            with self.subTest(check=name):
                self.process_vars[name] = value
                log = self.execute("Darwin", expected=1)
                del self.process_vars[name]
                self.assertFalse((self.root / "xattr-args").exists())
                self.assert_old_reopened()
                self.assertIn("Gatekeeper" if name == "STAGED_SPCTL_FAIL" else "Staging verification failed", log)
                (self.root / "open-args").unlink()

    def test_a_fresh_install_that_fails_its_staged_check_leaves_no_app(self):
        destination = self.root / "Applications" / "Fresh HST Office.app"
        self.process_vars["STAGED_SPCTL_FAIL"] = "1"
        self.execute("Darwin", expected=1, app_dest=str(destination))
        self.assertFalse(destination.exists())
        self.assertFalse(Path(str(destination) + ".hst-new").exists())
        self.assertFalse((self.root / "xattr-args").exists())

    def test_nothing_to_reopen_shows_a_notification(self):
        stub_osascript(self)
        destination = str(self.root / "Locked Applications" / "HST Office.app")  # missing folder: the swap fails
        log = self.execute("Darwin", expected=1, app_dest=destination, app_origin=str(self.root / "Gone" / "HST Office.app"))
        self.assertIn("Relaunch unavailable", log)
        self.assertIn("Chưa cài được bản cập nhật HST Office", (self.root / "notifications").read_text(encoding="utf-8"))
        self.assertFalse((self.root / "open-args").exists())


@unittest.skipUnless(HAS_SHELL and PYTHON_AND_SHASUM, "POSIX shell tools and /usr/bin/shasum required")
class AdministratorStep(MacHarness):
    """admin_command evaluated for real by the osascript stand-in (as this user, standing in for root)."""

    def setUp(self):
        super().setUp()
        stub_osascript(self)
        self.text = scripts.HEADER + cmd.mac_swap()
        self.script = self.root / "cache" / "swap.sh"
        self.script.parent.mkdir()
        self.script.write_text(self.text, encoding="utf-8")
        self.source = self.root / "New" / "HST Office.app"
        self.source.mkdir(parents=True)
        (self.source / "version").write_text("new", encoding="utf-8")
        self.target = self.root / "Applications" / "Fresh HST Office.app"
        self.before = set(Path(tempfile.gettempdir()).glob("hst-swap.*"))

    def run_admin(self, digest):
        driver = 'SCRIPT_SHA256=$3; . "$0"; command=$(admin_command "$1" "$2") || exit 9; osascript -e "$command"'
        return subprocess.run(["/bin/sh", "-c", driver, str(self.script), str(self.source), str(self.target), digest],
                              env=self.process_vars, capture_output=True, text=True, timeout=15)

    def test_unchanged_script_runs_the_swap_from_a_private_copy(self):
        result = self.run_admin(hashlib.sha256(self.text.encode("utf-8")).hexdigest())
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual((self.target / "version").read_text(), "new")
        self.assertIn("/usr/bin/mktemp -d /tmp/hst-swap.XXXXXX", (self.root / "osascript-args").read_text())
        self.assertEqual(set(Path(tempfile.gettempdir()).glob("hst-swap.*")), self.before)  # the copy is removed

    def test_script_changed_after_it_was_written_is_never_run(self):
        digest = hashlib.sha256(self.text.encode("utf-8")).hexdigest()
        with self.script.open("a", encoding="utf-8") as handle:
            handle.write('touch "$RECORDS/PWNED"\n')
        result = self.run_admin(digest)
        self.assertEqual(result.returncode, 1)
        self.assertFalse((self.root / "PWNED").exists())
        self.assertFalse(self.target.exists())
        self.assertEqual(set(Path(tempfile.gettempdir()).glob("hst-swap.*")), self.before)

    def test_digest_must_be_64_lowercase_hex(self):
        for bad in ("", "0" * 63, "0" * 65, "G" * 64, "0" * 63 + "'", "x; touch /tmp/PWNED"):
            with self.subTest(bad=bad):
                self.assertEqual(self.run_admin(bad).returncode, 9)
        self.assertFalse((self.root / "osascript-args").exists())


if __name__ == "__main__":
    unittest.main()
