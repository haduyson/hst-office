# SPDX-License-Identifier: AGPL-3.0-only
"""The macOS updater script run with stubbed tools: verified swap, administrator path, read-only bundles, relaunch."""
from pathlib import Path
import shlex
import shutil
import unittest

import _paths  # noqa: F401
from hst_office import update_helper_cmd as cmd
from update_helper_harness import HAS_SHELL, MacHarness


@unittest.skipUnless(HAS_SHELL, "POSIX shell tools required")
class MacExecution(MacHarness):
    def test_success_swaps_verifies_detaches_and_opens(self):
        self.process_vars["DETACH_RETRY"] = "1"
        self.execute("Darwin")
        self.assertEqual((self.destination / "version").read_text(), "new")
        self.assertFalse(self.installer.exists())
        self.assertEqual((self.root / "open-args").read_text().splitlines(), [str(self.destination)])
        calls = (self.root / "codesign-args").read_text()
        self.assertEqual(calls.count("--verify\n"), 2)
        self.assertIn(str(self.destination) + ".hst-new", calls)
        self.assertIn("-force", (self.root / "hdiutil-args").read_text())
        self.assertFalse(Path(str(self.destination) + ".hst-old").exists())
        self.assertEqual(list(self.root.glob(".hst-update.*")), [])

    def test_wrong_sha256_never_attaches_and_reopens_old_app(self):
        log = self.execute("Darwin", expected=1, sha256="0" * 64)
        self.assertIn("SHA256 mismatch", log)
        self.assertFalse((self.root / "hdiutil-args").exists())
        self.assertFalse((self.root / "ditto-args").exists())
        self.assertEqual(self.installer.read_bytes(), b"installer")
        self.assertEqual((self.destination / "version").read_text(), "old")
        self.assertEqual((self.root / "open-args").read_text().splitlines(), [str(self.destination)])
        self.assertEqual(list(self.root.glob(".hst-update.*")), [])

    def test_dry_run_rejects_wrong_sha256_before_attaching(self):
        log = self.execute("Darwin", dry_run=True, expected=1, sha256="0" * 64)
        self.assertIn("SHA256 mismatch", log)
        self.assertNotIn("DRYRUN install:", log)
        self.assertFalse((self.root / "hdiutil-args").exists())
        self.assertFalse((self.root / "open-args").exists())
        self.assertEqual(self.installer.read_bytes(), b"installer")
        self.assertEqual((self.destination / "version").read_text(), "old")

    def test_missing_shasum_never_attaches_and_reopens_old_app(self):
        if (self.bin / "shasum").exists():
            (self.bin / "shasum").unlink()
        log = self.execute("Darwin", expected=1)
        self.assertIn("SHA256 verification failed: no hash tool", log)
        self.assertFalse((self.root / "hdiutil-args").exists())
        self.assertEqual(self.installer.read_bytes(), b"installer")
        self.assertEqual((self.destination / "version").read_text(), "old")
        self.assertEqual((self.root / "open-args").read_text().splitlines(), [str(self.destination)])

    def test_team_mismatch_keeps_old_app(self):
        self.process_vars["TEAM_ID"] = cmd.TEAM_ID + "INVALID"
        self.execute("Darwin", expected=1)
        self.assert_old_reopened()
        self.assertFalse((self.root / "ditto-args").exists())

    def test_signature_assessment_and_details_failures(self):
        for failure in ("VERIFY_FAIL", "SPCTL_FAIL", "DETAILS_FAIL", "ATTACH_FAIL", "TWO_APPS"):
            with self.subTest(failure=failure):
                self.process_vars[failure] = "1"
                self.execute("Darwin", expected=1)
                self.assert_old_reopened()
                del self.process_vars[failure]

    def test_staged_team_mismatch_keeps_old_app(self):
        self.process_vars["STAGED_TEAM"] = "WRONG"
        self.execute("Darwin", expected=1)
        self.assert_old_reopened()

    def test_swap_failure_restores_old_app(self):
        self.process_vars["FAIL_SWAP"] = "1"
        log = self.execute("Darwin", expected=1)
        self.assertIn("restoring old app", log)
        self.assert_old_reopened()

    def test_interrupted_swap_restores_old_app(self):
        self.stub("mv", 'case "$1" in *.hst-new) kill -TERM "$PPID"; exit 1 ;; esac\n'
                  'exec ' + shlex.quote(shutil.which("mv")) + ' "$@"\n')
        self.execute("Darwin", expected=1)
        self.assert_old_reopened()

    def test_dry_run_quotes_exact_swap_without_changes(self):
        log = self.execute("Darwin", dry_run=True)
        command = next(line.split("DRYRUN install: ", 1)[1] for line in log.splitlines() if "DRYRUN install:" in line)
        args = shlex.split(command)
        self.assertEqual(args[:3], ["/bin/sh", str(self.root / "helper's directory" / "hst-update.sh"), "--swap"])
        self.assertEqual(Path(args[3]).name, self.process_vars["APP_NAME"])
        self.assertEqual(args[4], str(self.destination))
        self.assertIn("DRYRUN relaunch: open " + shlex.quote(str(self.destination)), log)
        self.assertEqual((self.destination / "version").read_text(), "old")
        self.assertTrue(self.installer.exists())
        self.assertFalse((self.root / "ditto-args").exists())
        self.assertFalse((self.root / "open-args").exists())
        self.assertEqual(list(self.root.glob(".hst-update.*")), [])

    def test_read_only_bundle_records_a_failure_even_in_dry_run(self):
        """A bundle on the mounted .dmg or an App Translocation path cannot be replaced, not even as administrator."""
        from hst_office import update_outcome as outcome
        for destination in ("/Volumes/HST Office/HST Office.app", str(self.root / "AppTranslocation" / "A1B2" / "d" / "HST Office.app")):
            with self.subTest(destination=destination):
                log = self.execute("Darwin", dry_run=True, expected=1, app_dest=destination,
                                   release_from="1.0.0-beta.5", release_to="1.0.0")
                self.assertNotIn("DRYRUN install:", log)
                self.assertNotIn("osascript", log)
                self.assertFalse((self.root / "hdiutil-args").exists())
                self.assertEqual(outcome.take(str(self.root), "1.0.0-beta.5"),
                                 {"schema": 1, "code": "readonly", "exit": 1, "from": "1.0.0-beta.5", "to": "1.0.0"})

    def test_missing_destination_in_a_writable_folder_is_installed_fresh(self):
        destination = self.root / "Applications" / "Fresh HST Office.app"
        log = self.execute("Darwin", app_dest=str(destination))
        self.assertEqual((destination / "version").read_text(), "new")
        self.assertNotIn("Moving old app aside", log)
        self.assertEqual((self.root / "open-args").read_text().splitlines(), [str(destination)])
        self.assertFalse(Path(str(destination) + ".hst-new").exists())
        self.assertEqual((self.root / "codesign-args").read_text().count("--verify\n"), 2)

    def test_failed_install_elsewhere_reopens_the_app_that_was_running(self):
        destination = str(self.root / "Locked Applications" / "HST Office.app")
        self.stub("osascript", "printf 'execution error: Read-only (1)\\n' >&2\nexit 1\n")
        log = self.execute("Darwin", expected=1, app_dest=destination, app_origin=str(self.destination))
        self.assertIn("Relaunching the app that was running", log)
        self.assertEqual((self.root / "open-args").read_text().splitlines(), [str(self.destination)])
        self.assertEqual((self.destination / "version").read_text(), "old")

    def test_administrator_command_quoting_and_denial(self):
        # A bundle in a missing folder is never writable, even when tests run as root.
        destination = str(self.root / "Locked Applications" / "Absent HST Office's.app")
        log = self.execute("Darwin", dry_run=True, app_dest=destination)
        line = next(line.split("DRYRUN install: ", 1)[1] for line in log.splitlines() if "DRYRUN install:" in line)
        args = shlex.split(line)
        self.assertEqual(args[:2], ["osascript", "-e"])
        self.assertEqual(len(args), 3)
        script = str(self.root / "helper's directory" / "hst-update.sh")
        self.assertIn('quoted form of "' + script + '"', args[2])
        self.assertIn('quoted form of "' + destination + '"', args[2])
        self.assertTrue(args[2].endswith('with administrator privileges'))
        self.stub("osascript", 'case "$2" in "display notification"*) exit 0 ;; esac\n'
                  'printf "%s\\n" "$@" > "$RECORDS/osascript-args"\nexit 1\n')
        self.execute("Darwin", expected=1, app_dest=destination)
        request = (self.root / "osascript-args").read_text().splitlines()
        self.assertEqual(request[0], "-e")
        self.assertIn('quoted form of "' + destination + '"', request[1])
        self.assertTrue(self.installer.exists())
        self.assertEqual((self.destination / "version").read_text(), "old")

    def test_failed_restore_retains_and_reopens_backup(self):
        self.stub("mv", 'case "$1" in *.hst-new|*.hst-old) exit 1 ;; esac\n'
                  'exec ' + shlex.quote(shutil.which("mv")) + ' "$@"\n')
        self.execute("Darwin", expected=1)
        backup = Path(str(self.destination) + ".hst-old")
        self.assertEqual((backup / "version").read_text(), "old")
        self.assertEqual((self.root / "open-args").read_text().splitlines(), ["-a", str(backup)])
        self.assertTrue(self.installer.exists())

    def test_unsafe_discovered_app_is_rejected(self):
        for name in ('X"bad.app', "X\\bad.app", "X\nbad.app", "X\x85bad.app", "X\u2028bad.app"):
            with self.subTest(name=name):
                self.process_vars["APP_NAME"] = name
                self.execute("Darwin", expected=1)
                self.assert_old_reopened()


if __name__ == "__main__":
    unittest.main()
