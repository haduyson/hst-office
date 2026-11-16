# SPDX-License-Identifier: AGPL-3.0-only
"""Once the Linux packaging key is configured, packages must not ship unsigned by accident.

sign-linux-packages.sh --enabled fails when HST_LINUX_GPG_FINGERPRINT is set without the secret; test runs without the
variable still skip cleanly. check-linux-signed-set.sh (used by collect-release-assets.sh) requires the full signed set
with the committed public key and `rpm -K` of every .rpm against it (signed with a throwaway key in a copy of the
script's tree), and the CI rules require the gate to see the fingerprint variable.
"""
import copy
import importlib.util
import os
import shutil
import subprocess
import tempfile
import unittest

import _paths  # noqa: F401
from _paths import ROOT
import yaml

_spec = importlib.util.spec_from_file_location("workflow_build_rules", os.path.join(ROOT, "scripts", "workflow_build_rules.py"))
rules = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(rules)

SIGN = os.path.join(ROOT, "scripts", "linux", "sign-linux-packages.sh")
CHECK_SET = os.path.join(ROOT, "scripts", "release", "check-linux-signed-set.sh")
KEY = os.path.join(ROOT, "data", "hst", "RPM-GPG-KEY-hasontech")
FINGERPRINT = "8FA2DAFC493AD9D02430F8D89A9FF0C36A2E3617"


def run(args, **env):
    clean = {k: v for k, v in os.environ.items() if not k.startswith("HST_LINUX_GPG_")}
    return subprocess.run(["bash", *args], capture_output=True, text=True, env={**clean, **env})


class Gate(unittest.TestCase):
    def test_without_key_or_variable_the_packages_stay_unsigned(self):
        done = run([SIGN, "--enabled"])
        self.assertEqual((done.returncode, done.stdout.strip()), (0, "enabled=false"))

    def test_a_configured_key_without_its_secret_fails(self):
        done = run([SIGN, "--enabled"], HST_LINUX_GPG_FINGERPRINT=FINGERPRINT)
        self.assertEqual(done.returncode, 1)
        self.assertNotIn("enabled=", done.stdout)
        self.assertIn("secret is empty", done.stderr)

    def test_the_secret_enables_signing(self):
        done = run([SIGN, "--enabled"], HST_LINUX_GPG_PRIVATE_KEY="x", HST_LINUX_GPG_FINGERPRINT=FINGERPRINT)
        self.assertEqual((done.returncode, done.stdout.strip()), (0, "enabled=true"))

    def test_the_committed_public_key_is_the_owner_key(self):
        with open(KEY, encoding="ascii") as handle:
            text = handle.read()
        self.assertTrue(text.startswith("-----BEGIN PGP PUBLIC KEY BLOCK-----"))
        self.assertNotIn("PRIVATE", text)
        if shutil.which("gpg"):
            out = subprocess.run(["gpg", "--batch", "--with-colons", "--show-keys", KEY], capture_output=True, text=True)
            self.assertIn("fpr:::::::::%s:" % FINGERPRINT, out.stdout)


class SignedSet(unittest.TestCase):
    NAMES = ("HSTOffice_1.0.2_Linux_x86-64.rpm", "HSTOffice_1.0.2_Linux_x86-64.AppImage",
             "HSTOffice_1.0.2_Linux_x86-64.AppImage.asc", "HSTOffice_1.0.2_Linux_x86-64.SHA256SUMS",
             "HSTOffice_1.0.2_Linux_x86-64.SHA256SUMS.asc")

    def make(self, drop=(), key=True):
        work = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, work)
        for name in self.NAMES:
            if name not in drop:
                open(os.path.join(work, name), "w").close()
        if key:
            shutil.copy(KEY, os.path.join(work, "RPM-GPG-KEY-hasontech"))
        return work

    @unittest.skipUnless(all(shutil.which(t) for t in ("gpg", "rpm", "rpmbuild", "rpmsign")), "needs gpg and rpm")
    def test_the_complete_set_passes_only_with_a_signed_rpm(self):
        tree = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, tree)
        home = os.path.join(tree, "gnupg")
        os.makedirs(home, mode=0o700)
        self.addCleanup(subprocess.run, ["gpgconf", "--homedir", home, "--kill", "gpg-agent"])
        gpg = ["gpg", "--homedir", home, "--batch", "--passphrase", "", "--pinentry-mode", "loopback"]
        subprocess.run([*gpg, "--quick-gen-key", "HST test", "rsa2048", "sign", "never"], check=True,
                       capture_output=True)
        for rel in ("scripts/release", "data/hst"):
            os.makedirs(os.path.join(tree, rel))
        check = os.path.join(tree, "scripts", "release", "check-linux-signed-set.sh")
        shutil.copy(CHECK_SET, check)
        key = os.path.join(tree, "data", "hst", "RPM-GPG-KEY-hasontech")
        with open(key, "w", encoding="ascii") as handle:
            handle.write(subprocess.run(["gpg", "--homedir", home, "--armor", "--export"], check=True,
                                        capture_output=True, text=True).stdout)
        work = self.make(drop=self.NAMES[:1], key=False)
        shutil.copy(key, os.path.join(work, "RPM-GPG-KEY-hasontech"))
        spec = os.path.join(tree, "t.spec")
        with open(spec, "w", encoding="ascii") as handle:
            handle.write("Name: t\nVersion: 1\nRelease: 1\nSummary: t\nLicense: MPL-2.0\nBuildArch: noarch\n"
                         "%description\nt\n%files\n")
        subprocess.run(["rpmbuild", "-bb", "--quiet", "--define", "_topdir " + os.path.join(tree, "rb"), spec],
                       check=True, capture_output=True)
        rpm = os.path.join(work, self.NAMES[0])
        shutil.copy(os.path.join(tree, "rb", "RPMS", "noarch", "t-1-1.noarch.rpm"), rpm)
        unsigned = run([check, work])
        self.assertEqual(unsigned.returncode, 1)
        self.assertIn("rpm -K " + self.NAMES[0], unsigned.stderr)
        sign = subprocess.run(["rpmsign", "--define", "__gpg " + shutil.which("gpg"), "--define", "_gpg_name HST test",
                               "--define", "_gpg_path " + home,
                               "--define", "_gpg_sign_cmd_extra_args --batch --pinentry-mode loopback --passphrase ''",
                               "--addsign", rpm], capture_output=True, text=True)
        self.assertEqual(sign.returncode, 0, sign.stderr)
        signed = run([check, work])
        self.assertEqual(signed.returncode, 0, signed.stderr)
        self.assertIn("digests signatures OK", signed.stdout)

    def test_every_missing_part_fails(self):
        for name in self.NAMES:
            with self.subTest(name=name):
                done = run([CHECK_SET, self.make(drop=(name,))])
                self.assertEqual(done.returncode, 1)
                self.assertIn("signed set lacks", done.stderr)
        self.assertEqual(run([CHECK_SET, self.make(key=False)]).returncode, 1)

    def test_collect_refuses_unsigned_linux_packages_while_the_key_is_committed(self):
        with open(os.path.join(ROOT, "scripts", "release", "collect-release-assets.sh"), encoding="utf-8") as handle:
            text = handle.read()
        self.assertIn("check-linux-signed-set.sh", text)
        self.assertIn("although the packaging key is configured", text)


class WorkflowRule(unittest.TestCase):
    def test_the_gate_must_see_the_fingerprint_variable(self):
        with open(os.path.join(ROOT, ".github", "workflows", "desktop-linux.yml"), encoding="utf-8") as handle:
            job = yaml.safe_load(handle)["jobs"]["sign"]
        errors = []
        rules.check_linux_signing_job(job, lambda ok, message: ok or errors.append(message))
        self.assertEqual(errors, [])
        broken = copy.deepcopy(job)
        next(step for step in broken["steps"] if step.get("id") == "gate")["env"].pop("HST_LINUX_GPG_FINGERPRINT")
        rules.check_linux_signing_job(broken, lambda ok, message: ok or errors.append(message))
        self.assertTrue(any("HST_LINUX_GPG_FINGERPRINT" in error for error in errors))


if __name__ == "__main__":
    unittest.main()
