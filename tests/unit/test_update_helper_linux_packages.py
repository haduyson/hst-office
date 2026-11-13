# SPDX-License-Identifier: AGPL-3.0-only
"""The Linux updater for .rpm installs (dnf / zypper / rpm / pkcon through pkexec) and AppImage installs (atomic
replacement beside the old file, no root), run with isolated tool stubs like test_update_helper_linux.py."""
import hashlib
import os
import shlex
import shutil
import unittest

import _paths  # noqa: F401
from hst_office import update_helper_cmd as cmd
from update_helper_harness import HAS_SHELL, ShellHarness, build


class Preflight(unittest.TestCase):
    def test_tools_per_install_kind(self):
        def which(*present):
            return lambda tool: "/usr/bin/" + tool if tool in present else None
        self.assertIsNone(cmd.preflight("Linux", which("pkexec", "apt-get")))
        self.assertEqual(cmd.preflight("Linux", which("pkexec", "dnf")), "no-installer-tool")
        for manager in ("dnf", "zypper", "rpm"):
            self.assertIsNone(cmd.preflight("Linux", which("pkexec", manager), linux_kind="rpm"))
        self.assertEqual(cmd.preflight("Linux", which("pkexec", "apt-get"), linux_kind="rpm"), "no-installer-tool")
        self.assertIsNone(cmd.preflight("Linux", which("pkcon"), linux_kind="rpm"))
        self.assertIsNone(cmd.preflight("Linux", which(), linux_kind="appimage"))

    def test_unknown_kind_and_dry_run_text(self):
        with self.assertRaises(ValueError):
            build(linux_kind="snap")
        self.assertIn("dnf install -y", build(linux_kind="rpm")["text"])
        self.assertNotIn("APT_COMMAND", build(linux_kind="appimage")["text"])
        self.assertIn("apt-get install -y", build()["text"])  # default stays the .deb path


@unittest.skipUnless(HAS_SHELL, "POSIX shell tools required")
class RpmExecution(ShellHarness):
    def setUp(self):
        super().setUp()
        self.installer = self.root / "HSTOffice_9.9.9_Linux_x86-64.rpm"
        self.installer.write_text("installer", encoding="utf-8")
        self.stub("pkexec", 'printf "%s\\n" "$@" > "$RECORDS/pkexec-args"\nexit "${PKEXEC_EXIT:-0}"\n')

    def args(self):
        return (self.root / "pkexec-args").read_text().splitlines()

    def test_dnf_then_zypper_then_rpm(self):
        expected = {"dnf": ["dnf", "install", "-y", str(self.installer)],
                    "zypper": ["zypper", "--non-interactive", "install", "--allow-unsigned-rpm", str(self.installer)],
                    "rpm": ["rpm", "-U", str(self.installer)]}
        for tool in ("dnf", "zypper", "rpm"):
            self.stub(tool, "exit 0\n")
        for tool in ("dnf", "zypper", "rpm"):
            with self.subTest(tool=tool):
                self.installer.write_text("installer", encoding="utf-8")
                log = self.execute(linux_kind="rpm")
                self.assertEqual(self.args(), expected[tool])
                self.assertIn("Installing with " + tool, log)
                self.assertFalse(self.installer.exists())
                self.wait_for_file("relaunch").unlink()
                (self.bin / tool).unlink()

    def test_password_dialog_dismissed_is_not_recorded(self):
        self.stub("dnf", "exit 0\n")
        self.process_vars["PKEXEC_EXIT"] = "126"
        self.execute(linux_kind="rpm", expected=126)
        self.assertFalse((self.log.parent / "update-result.json").exists())
        self.process_vars["PKEXEC_EXIT"] = "127"
        self.execute(linux_kind="rpm", expected=127)
        self.assertIn('"code":"auth"', (self.log.parent / "update-result.json").read_text())

    def test_pkcon_and_no_tool(self):
        (self.bin / "pkexec").unlink()
        self.stub("pkcon", 'printf "%s\\n" "$@" > "$RECORDS/pkcon-args"\n')
        self.execute(linux_kind="rpm")
        self.assertEqual((self.root / "pkcon-args").read_text().splitlines(), ["install-local", str(self.installer)])
        (self.bin / "pkcon").unlink()
        self.installer.write_text("installer", encoding="utf-8")
        log = self.execute(linux_kind="rpm", expected=1)
        self.assertIn("no installer tool", log)
        self.assertIn('"code":"tool"', (self.log.parent / "update-result.json").read_text())

    def test_signed_package_imports_the_shipped_key_and_drops_the_unsigned_flag(self):
        key = self.soffice.parent.parent / "RPM-GPG-KEY-hasontech"
        key.write_text("public key", encoding="utf-8")
        self.stub("zypper", "exit 0\n")
        self.stub("rpm", 'case "$1" in -qp) printf "%s\\n" "${RPM_SIG:-RSA/SHA512, Fri, Key ID 579a0f1232743f35}" ;; esac\n')
        self.execute(linux_kind="rpm")
        args = self.args()
        self.assertEqual(args[:2], ["sh", "-c"])
        self.assertEqual(args[3:], ["sh", str(key), "zypper", "--non-interactive", "install", str(self.installer)])
        self.assertIn('rpm --import "$1"', args[2])
        self.process_vars["RPM_SIG"] = "(none) (none)"  # unsigned file: no import, zypper needs the flag
        self.installer.write_text("installer", encoding="utf-8")
        self.execute(linux_kind="rpm")
        self.assertEqual(self.args(), ["zypper", "--non-interactive", "install", "--allow-unsigned-rpm", str(self.installer)])
        key.unlink()  # signed file but no shipped key (older install): unsigned path
        del self.process_vars["RPM_SIG"]
        self.installer.write_text("installer", encoding="utf-8")
        self.execute(linux_kind="rpm")
        self.assertIn("--allow-unsigned-rpm", self.args())

    def test_dry_run(self):
        self.stub("dnf", "exit 0\n")
        log = self.execute(linux_kind="rpm", dry_run=True)
        line = next(x for x in log.splitlines() if "DRYRUN install:" in x)
        self.assertEqual(shlex.split(line.split("DRYRUN install: ", 1)[1]), ["pkexec", "dnf", "install", "-y", str(self.installer)])
        self.assertFalse((self.root / "pkexec-args").exists())


@unittest.skipUnless(HAS_SHELL, "POSIX shell tools required")
class AppImageExecution(ShellHarness):
    def setUp(self):
        super().setUp()
        (self.bin / "chmod").symlink_to(shutil.which("chmod"))
        self.apps = self.root / "My Apps"
        self.appimage = self.apps / "HST Office.AppImage"
        self.stub(self.appimage, 'printf "old\\n" > "$RECORDS/relaunch"\n')
        hidden = self.apps / ".hst-office-update"
        hidden.mkdir()
        self.installer = hidden / "HSTOffice_9.9.9_Linux_x86-64.AppImage"
        self.installer.write_text("installer", encoding="utf-8")
        self.process_vars.update(APPIMAGE="/stale/old.AppImage", APPDIR="/tmp/.mount_old", PYTHONHOME="/tmp/.mount_old/py")

    def test_replaces_in_place_and_starts_the_new_file_with_a_clean_environment(self):
        inode = os.stat(self.appimage).st_ino
        log = self.execute(linux_kind="appimage", soffice=str(self.appimage))
        self.assertIn("AppImage replaced", log)
        self.assertEqual(self.appimage.read_text(), "installer")
        self.assertNotEqual(os.stat(self.appimage).st_ino, inode)  # a rename, not a copy into the old file
        self.assertTrue(os.access(self.appimage, os.X_OK))
        self.assertFalse(self.installer.parent.exists())

    def test_relaunch_environment_is_clean(self):
        # The new AppImage is a stub that records the environment it was started with.
        self.stub(self.installer, 'env > "$RECORDS/relaunch-env.tmp" && mv "$RECORDS/relaunch-env.tmp" "$RECORDS/relaunch-env"\n')
        digest = hashlib.sha256(self.installer.read_bytes()).hexdigest()
        self.execute(linux_kind="appimage", soffice=str(self.appimage), sha256=digest)
        env = self.wait_for_file("relaunch-env")
        names = {line.split("=", 1)[0] for line in env.read_text().splitlines()}
        self.assertFalse(names & {"APPIMAGE", "APPDIR", "PYTHONHOME"}, names)

    def test_wrong_sha256_keeps_the_old_appimage(self):
        log = self.execute(linux_kind="appimage", soffice=str(self.appimage), expected=1, sha256="0" * 64)
        self.assertIn("SHA256 mismatch", log)
        self.assertIn("printf", self.appimage.read_text())
        self.wait_for_file("relaunch")
        self.assertIn('"code":"verify"', (self.log.parent / "update-result.json").read_text())


if __name__ == "__main__":
    unittest.main()
