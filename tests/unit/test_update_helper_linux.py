# SPDX-License-Identifier: AGPL-3.0-only
"""The Linux updater script run with isolated local tool stubs: hash check, apt-get / pkcon, waiting and relaunch."""
import os
import shlex
import shutil
import subprocess
import time
import unittest

import _paths  # noqa: F401
from update_helper_harness import HASH_TOOLS, HAS_SHELL, SHA256, ShellHarness


@unittest.skipUnless(HAS_SHELL, "POSIX shell tools required")
class LinuxExecution(ShellHarness):
    def setUp(self):
        super().setUp()
        self.stub("pkexec", 'exec "$@"\n')
        self.stub("apt-get", 'printf "%s\\n" "$@" > "$RECORDS/apt-args"\n'
                  'printf "%s\\n" "$DEBIAN_FRONTEND" > "$RECORDS/frontend"\nexit "${APT_EXIT:-0}"\n')

    def test_success_quotes_logging_and_deletion(self):
        self.installer = self.root / 'installer "double" \'single\' $(touch INJECTED);.deb'
        self.installer.write_bytes(b"installer")
        self.soffice = self.root / 'soffice "double" \'single\' $(touch INJECTED);'
        self.stub(self.soffice, 'printf "relaunched\\n" > "$RECORDS/relaunch"\n')
        self.log.write_text("previous log\n", encoding="utf-8")
        log = self.execute()
        self.assertTrue(log.startswith("previous log\n"))
        self.assertRegex(log, r"\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d.*Waiting for process")
        self.assertEqual((self.root / "apt-args").read_text().splitlines(), ["install", "-y", str(self.installer)])
        self.assertEqual((self.root / "frontend").read_text().strip(), "noninteractive")
        self.assertIn("Installer exited with code 0", log)
        self.assertFalse(self.installer.exists())
        self.wait_for_file("relaunch")
        self.assertFalse((self.root / "INJECTED").exists())

    def test_dry_run(self):
        log = self.execute(dry_run=True)
        command = next(line.split("DRYRUN install: ", 1)[1] for line in log.splitlines() if "DRYRUN install:" in line)
        self.assertEqual(shlex.split(command), ["pkexec", "env", "DEBIAN_FRONTEND=noninteractive", "apt-get", "install", "-y", str(self.installer)])
        self.assertIn("DRYRUN relaunch:", log)
        self.assertTrue(self.installer.exists())
        self.assertFalse((self.root / "apt-args").exists())
        self.assertFalse((self.root / "relaunch").exists())

    def test_wrong_sha256_skips_both_installers_and_relaunches(self):
        self.stub("pkcon", 'printf "%s\\n" "$@" > "$RECORDS/pkcon-args"\n')
        for package_manager in ("apt-get", "pkcon"):
            with self.subTest(package_manager=package_manager):
                if package_manager == "pkcon":
                    (self.bin / "pkexec").unlink()
                log = self.execute(expected=1, sha256="0" * 64)
                self.assertIn("SHA256 mismatch", log)
                self.assertFalse((self.root / "apt-args").exists())
                self.assertFalse((self.root / "pkcon-args").exists())
                self.assertEqual(self.installer.read_bytes(), b"installer")
                self.wait_for_file("relaunch").unlink()

    def test_dry_run_rejects_wrong_sha256(self):
        log = self.execute(dry_run=True, expected=1, sha256="0" * 64)
        self.assertIn("SHA256 mismatch", log)
        self.assertNotIn("DRYRUN install:", log)
        self.assertFalse((self.root / "apt-args").exists())
        self.assertFalse((self.root / "relaunch").exists())
        self.assertEqual(self.installer.read_bytes(), b"installer")

    def test_missing_installer_relaunches_without_install(self):
        self.installer.unlink()
        log = self.execute(expected=1)
        self.assertIn("SHA256 verification failed: installer missing", log)
        self.assertFalse((self.root / "apt-args").exists())
        self.wait_for_file("relaunch")

    def test_missing_hash_tool_keeps_installer_and_relaunches(self):
        for tool in HASH_TOOLS:
            if (self.bin / tool).exists():
                (self.bin / tool).unlink()
        log = self.execute(expected=1)
        self.assertIn("SHA256 verification failed: no hash tool", log)
        self.assertFalse((self.root / "apt-args").exists())
        self.assertEqual(self.installer.read_bytes(), b"installer")
        self.wait_for_file("relaunch")

    def test_hash_tool_failure_keeps_installer_and_relaunches(self):
        # Even output matching the expected hash cannot hide a hashing error.
        self.stub("sha256sum", 'printf "%s  -\\n" ' + SHA256 + '\nexit 1\n')
        log = self.execute(expected=1)
        self.assertIn("SHA256 verification failed: hash tool failed", log)
        self.assertFalse((self.root / "apt-args").exists())
        self.assertEqual(self.installer.read_bytes(), b"installer")
        self.wait_for_file("relaunch")

    def test_hash_tool_fallbacks(self):
        for tool in HASH_TOOLS:
            with self.subTest(tool=tool):
                if not shutil.which(tool):
                    continue
                for name in HASH_TOOLS:
                    if (self.bin / name).exists():
                        (self.bin / name).unlink()
                (self.bin / tool).symlink_to(shutil.which(tool))
                self.installer.write_bytes(b"installer")
                self.execute()
                self.assertEqual((self.root / "apt-args").read_text().splitlines(), ["install", "-y", str(self.installer)])
                self.assertFalse(self.installer.exists())
                self.wait_for_file("relaunch").unlink()

    def test_installer_changed_while_waiting_is_rejected(self):
        self.stub("sleep", 'printf waiting > "$RECORDS/waiting"\n'
                  'exec ' + shlex.quote(shutil.which("sleep")) + ' "$@"\n')
        child = subprocess.Popen([shutil.which("sleep"), "30"])
        helper = subprocess.Popen(self.prepare(pid=child.pid), env=self.process_vars)
        try:
            self.wait_for_file("waiting")
            self.assertIsNone(helper.poll())
            self.assertFalse((self.root / "apt-args").exists())
            self.installer.write_bytes(b"changed while waiting")
            child.terminate()
            child.wait(timeout=5)
            self.assertEqual(helper.wait(timeout=5), 1)
            self.assertIn("SHA256 mismatch", self.log.read_text())
            self.assertFalse((self.root / "apt-args").exists())
            self.assertEqual(self.installer.read_bytes(), b"changed while waiting")
            self.wait_for_file("relaunch")
        finally:
            for proc in (child, helper):
                if proc.poll() is None:
                    proc.terminate()
                proc.wait(timeout=5)

    def test_install_failure_keeps_installer_and_relaunches(self):
        self.process_vars["APT_EXIT"] = "1"
        log = self.execute(expected=1)
        self.assertIn("Installer exited with code 1", log)
        self.assertTrue(self.installer.exists())
        self.wait_for_file("relaunch")

    def test_waits_for_process_before_install(self):
        child = subprocess.Popen([shutil.which("sleep"), "2"])
        helper = subprocess.Popen(self.prepare(pid=child.pid), env=self.process_vars)
        start = time.monotonic()
        try:
            time.sleep(0.3)
            self.assertFalse((self.root / "apt-args").exists())
            self.assertIsNone(helper.poll())
            child.wait(timeout=4)
            self.assertEqual(helper.wait(timeout=5), 0)
            self.assertGreaterEqual(time.monotonic() - start, 1.7)
            self.assertTrue((self.root / "apt-args").exists())
            self.wait_for_file("relaunch")
        finally:
            for proc in (child, helper):
                if proc.poll() is None:
                    proc.terminate()
                proc.wait(timeout=5)

    def test_wait_timeout_skips_install_and_keeps_installer(self):
        self.stub("sleep", 'exit 0\n')
        log = self.execute(pid=os.getpid(), expected=1)
        self.assertIn("Timed out after 30 minutes; installation skipped", log)
        self.assertFalse((self.root / "apt-args").exists())
        self.assertTrue(self.installer.exists())
        self.wait_for_file("relaunch")

    def test_pkcon_fallback(self):
        (self.bin / "pkexec").unlink()
        self.stub("pkcon", 'printf "%s\\n" "$@" > "$RECORDS/pkcon-args"\n')
        self.execute()
        self.assertEqual((self.root / "pkcon-args").read_text().splitlines(), ["install-local", str(self.installer)])
        self.wait_for_file("relaunch")

    def test_missing_installer_tool(self):
        (self.bin / "pkexec").unlink()
        self.stub("zenity", 'printf "%s\\n" "$@" > "$RECORDS/message"\nexit 1\n')
        log = self.execute(expected=1)
        self.assertIn("install the downloaded package manually", log)
        self.assertTrue((self.root / "message").exists())
        self.assertTrue(self.installer.exists())
        self.wait_for_file("relaunch")


if __name__ == "__main__":
    unittest.main()
