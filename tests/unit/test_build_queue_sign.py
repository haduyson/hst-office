# SPDX-License-Identifier: AGPL-3.0-only
"""Signing of integrator Linux release builds (scripts/build_infra/queue_sign.py) with a throwaway packaging key:
the commit's own sign-linux-packages.sh signs a real .rpm, `rpm -K` must then report digests signatures OK, the
secret never reaches the job log, and a commit whose public key is not the keyring's key fails the job."""
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

from build_queue_fixtures import ROOT
from build_infra import queue_sign as qs
from build_infra.queue_git import Git

TOOLS = all(shutil.which(t) for t in ("gpg", "gpgconf", "rpmsign", "rpmkeys", "rpmbuild"))
RELEASE_REF = "origin/rc/1.0.2-batch5"


def sh(*cmd, **kw):
    return subprocess.run(cmd, check=True, capture_output=True, text=True, **kw).stdout


class WantsSigningTest(unittest.TestCase):
    def test_only_integrator_release_builds_with_an_rpm(self):
        job = {"platform": "linux", "integrator": True, "output": ["/o/HSTOffice_1.0.2_Linux_x86-64.rpm"]}
        self.assertTrue(qs.wants_signing(job, {}))
        for change in ({"integrator": False}, {"train": "train/1.0.2-040"}, {"confirm_for": "train/1.0.2-040"},
                       {"platform": "windows"}, {"output": ["/o/x.deb"]}):
            self.assertFalse(qs.wants_signing(dict(job, **change), {}), change)
        self.assertFalse(qs.wants_signing(job, {"linux_signing": False}))


@unittest.skipUnless(TOOLS, "needs gpg, rpmsign, rpmkeys and rpmbuild (Ubuntu package rpm)")
class SignJobTest(unittest.TestCase):
    def setUp(self):
        signer = subprocess.run(["git", "-C", str(ROOT), "show", f"{RELEASE_REF}:{qs.SIGNER}"],
                                capture_output=True, text=True, check=False)
        if signer.returncode != 0:
            self.skipTest(f"{qs.SIGNER} not in {RELEASE_REF}")
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.tmp = Path(tmp.name)
        self.keyring = self.tmp / "keyring"
        self.keyring.mkdir(mode=0o700)
        (self.keyring / "passphrase").write_text("test-passphrase-1\n")
        gpg = ["gpg", "--homedir", str(self.keyring), "--batch", "--pinentry-mode", "loopback", "--passphrase-file",
               str(self.keyring / "passphrase")]
        self.addCleanup(subprocess.run, ["gpgconf", "--homedir", str(self.keyring), "--kill", "gpg-agent"])
        sh(*gpg, "--quick-gen-key", "HST test packages", "rsa2048", "sign", "never")
        public = sh("gpg", "--homedir", str(self.keyring), "--batch", "--armor", "--export")
        self.repo = self.tmp / "repo"
        self.commit = self.commit_tree(signer.stdout, public)
        self.out = self.tmp / "out"
        self.out.mkdir()
        self.make_rpm()
        self.cfg = {"linux_signing_gnupg": str(self.keyring)}
        self.job = {"sha": self.commit, "platform": "linux", "integrator": True}
        self.logged = []

    def commit_tree(self, signer, public):
        env = dict(os.environ, GIT_AUTHOR_NAME="t", GIT_AUTHOR_EMAIL="t@t", GIT_COMMITTER_NAME="t",
                   GIT_COMMITTER_EMAIL="t@t")
        sh("git", "init", "-q", str(self.repo))
        for rel, text in ((qs.SIGNER, signer), (qs.PUBLIC_KEY, public)):
            (self.repo / rel).parent.mkdir(parents=True, exist_ok=True)
            (self.repo / rel).write_text(text)
        sh("git", "-C", str(self.repo), "add", "-A")
        sh("git", "-C", str(self.repo), "commit", "-qm", "release", env=env)
        return sh("git", "-C", str(self.repo), "rev-parse", "HEAD").strip()

    def make_rpm(self):
        top = self.tmp / "rpmbuild"
        spec = self.tmp / "t.spec"
        spec.write_text("Name: hst-office-test\nVersion: 1.0.2\nRelease: 1\nSummary: t\nLicense: MPL-2.0\n"
                        "BuildArch: noarch\n%description\nt\n%files\n")
        sh("rpmbuild", "-bb", "--quiet", "--define", f"_topdir {top}", str(spec))
        built = next(top.rglob("*.rpm"))
        shutil.copy(built, self.out / "HSTOffice_1.0.2_Linux_x86-64.rpm")
        sh("bash", "-c", "sha256sum HSTOffice_1.0.2_Linux_x86-64.rpm > SHA256SUMS", cwd=self.out)

    def sign(self):
        return qs.sign_job(self.job, str(self.out), self.cfg, self.logged.append, git=Git(str(self.repo)),
                           workroot=str(self.tmp))

    def test_release_rpm_is_signed_and_rpm_k_passes(self):
        unsigned = qs.check_rpms
        with self.assertRaisesRegex(qs.SignError, "rpm -K HSTOffice_1.0.2_Linux_x86-64.rpm"):
            unsigned(str(self.out), str(self.repo / qs.PUBLIC_KEY), str(self.tmp / "db0"))
        output = self.sign()
        names = sorted(os.path.basename(p) for p in output)
        self.assertIn("HSTOffice_1.0.2_Linux_x86-64.rpm", names)
        self.assertIn("HSTOffice_1.0.2_Linux_x86-64.SHA256SUMS.asc", names)
        self.assertIn("RPM-GPG-KEY-hasontech", names)
        log = "".join(self.logged)
        self.assertIn("digests signatures OK", log)
        self.assertNotIn("PRIVATE KEY", log)
        self.assertNotIn("test-passphrase-1", log)
        self.assertEqual(sorted(os.listdir(self.tmp)), ["db0", "keyring", "out", "repo", "rpmbuild", "t.spec"])  # no key copy left

    def test_a_commit_with_another_public_key_fails(self):
        other = self.tmp / "other"
        other.mkdir(mode=0o700)
        self.addCleanup(subprocess.run, ["gpgconf", "--homedir", str(other), "--kill", "gpg-agent"])
        sh("gpg", "--homedir", str(other), "--batch", "--passphrase", "", "--quick-gen-key", "other", "rsa2048",
           "sign", "never")
        self.job["sha"] = self.commit_tree(sh("git", "-C", str(self.repo), "show", f"HEAD:{qs.SIGNER}"),
                                           sh("gpg", "--homedir", str(other), "--batch", "--armor", "--export"))
        with self.assertRaisesRegex(qs.SignError, "no secret key"):
            self.sign()

    def test_no_keyring_fails(self):
        self.cfg["linux_signing_gnupg"] = str(self.tmp / "missing")
        with self.assertRaisesRegex(qs.SignError, "no signing keyring"):
            self.sign()


if __name__ == "__main__":
    unittest.main()
