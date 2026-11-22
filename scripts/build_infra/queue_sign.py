# SPDX-License-Identifier: AGPL-3.0-only
"""GPG signing of the integrator's Linux release builds, on the dev server (the only place the packaging key lives).

An integrator Linux job (not a train build, not a train confirmation build) whose output has an .rpm is signed
after its output was copied back, before it is marked done:
  1. the job's commit provides scripts/linux/sign-linux-packages.sh and the public key data/hst/RPM-GPG-KEY-hasontech
     (the key the .rpm ships for the updater); the key's fingerprint is the one signing must use;
  2. the secret key is exported from linux_signing_gnupg (a private copy of the keyring, so the original is never
     touched) and handed to the script in its child environment only, as CI hands over its secret: it is never
     written to disk, printed or logged;
  3. `rpm -K` against the committed key (a scratch rpm database) must report
     "digests signatures OK" for every .rpm, else the job fails.
Needs gpg, rpm, rpmsign and rpmkeys (Ubuntu package rpm, installed for this on the dev server; docs/BUILD_MATRIX.md).
"""
import os
import shutil
import subprocess
import tempfile

from .queue_git import Git

SIGNER = "scripts/linux/sign-linux-packages.sh"
PUBLIC_KEY = "data/hst/RPM-GPG-KEY-hasontech"
OUTPUT_SUFFIXES = (".deb", ".rpm", ".AppImage", ".tar.gz", ".asc", ".SHA256SUMS")


class SignError(RuntimeError):
    pass


def wants_signing(job, cfg):
    return (cfg.get("linux_signing", True) and job["platform"] == "linux" and job.get("integrator")
            and not job.get("train") and not job.get("confirm_for")
            and any(f.endswith(".rpm") for f in job.get("output", [])))


def _run(cmd, timeout=600, **kw):
    try:
        done = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, check=False, **kw)
    except (OSError, subprocess.SubprocessError) as exc:
        raise SignError(f"{os.path.basename(cmd[0])} could not run: {exc}") from exc
    return done


def fingerprint(key_file, gnupg_home):
    done = _run(["gpg", "--homedir", gnupg_home, "--batch", "--with-colons", "--show-keys", key_file])
    for line in done.stdout.splitlines():
        if line.startswith("fpr:"):
            return line.split(":")[9]
    raise SignError(f"no fingerprint in {PUBLIC_KEY}: {done.stderr.strip()[-300:]}")


def export_secret(keyring, home, fpr):
    """ASCII-armoured secret key and its passphrase, read from a private copy of the keyring."""
    shutil.copytree(keyring, home, ignore=shutil.ignore_patterns("S.*", "*.lock", ".#*"))
    os.chmod(home, 0o700)
    passfile = os.path.join(home, "passphrase")
    if not os.path.isfile(passfile):
        raise SignError(f"the keyring {keyring} has no passphrase file")
    try:
        done = _run(["gpg", "--homedir", home, "--batch", "--pinentry-mode", "loopback", "--passphrase-file", passfile,
                     "--armor", "--export-secret-keys", fpr])
    finally:
        _run(["gpgconf", "--homedir", home, "--kill", "gpg-agent"], timeout=30)
    if done.returncode != 0 or "PRIVATE KEY BLOCK" not in done.stdout:
        raise SignError(f"the keyring has no secret key {fpr} (gpg exit {done.returncode})")
    with open(passfile, encoding="utf-8") as f:
        return done.stdout, f.read().strip()


def check_rpms(out, key_file, dbpath):
    """`rpm -K` of every .rpm against the committed key only (a scratch rpm database); [(name, verdict line)]."""
    os.makedirs(dbpath, exist_ok=True)
    for cmd in (["rpm", "--dbpath", dbpath, "--initdb"], ["rpmkeys", "--dbpath", dbpath, "--import", key_file]):
        done = _run(cmd)
        if done.returncode != 0:
            raise SignError(f"{' '.join(cmd[:3])}: {done.stderr.strip()[-300:]}")
    verdicts = []
    for name in sorted(n for n in os.listdir(out) if n.endswith(".rpm")):
        done = _run(["rpm", "--dbpath", dbpath, "-K", os.path.join(out, name)])
        line = done.stdout.strip().splitlines()[-1] if done.stdout.strip() else done.stderr.strip()
        if done.returncode != 0 or not line.endswith("digests signatures OK"):
            raise SignError(f"rpm -K {name}: {line or 'no verdict'}")
        verdicts.append((name, line))
    return verdicts


def sign_job(job, out, cfg, log, git=None, workroot=None):
    """Sign the job's Linux packages in `out`; returns the new output list. SignError when anything fails."""
    git = git or Git()
    keyring = cfg.get("linux_signing_gnupg", "/root/.config/hst-office/linux-signing-gnupg")
    if not os.path.isdir(keyring):
        raise SignError(f"no signing keyring at {keyring}")
    with tempfile.TemporaryDirectory(prefix="hst-sign-", dir=workroot) as tmp:
        os.chmod(tmp, 0o700)
        for rel in (SIGNER, PUBLIC_KEY):
            rc, text, err = git.run("show", f"{job['sha']}:{rel}")
            if rc != 0:
                raise SignError(f"commit {job['sha'][:10]} has no {rel}: {err.strip()[-200:]}")
            os.makedirs(os.path.join(tmp, "tree", os.path.dirname(rel)), exist_ok=True)
            with open(os.path.join(tmp, "tree", rel), "w", encoding="utf-8") as f:
                f.write(text)
        key_file = os.path.join(tmp, "tree", PUBLIC_KEY)
        scratch = os.path.join(tmp, "scratch-gnupg")
        os.makedirs(scratch, mode=0o700)
        fpr = fingerprint(key_file, scratch)
        secret, passphrase = export_secret(keyring, os.path.join(tmp, "gnupg"), fpr)
        env = {"PATH": os.environ.get("PATH", "/usr/bin:/bin"), "HOME": tmp, "LC_ALL": "C",
               "HST_LINUX_GPG_PRIVATE_KEY": secret, "HST_LINUX_GPG_PASSPHRASE": passphrase,
               "HST_LINUX_GPG_FINGERPRINT": fpr}
        done = _run(["bash", os.path.join(tmp, "tree", SIGNER), out], timeout=1800, env=env)
        del secret, passphrase, env
        log(done.stdout + done.stderr)
        if done.returncode != 0:
            raise SignError(f"sign-linux-packages.sh exit {done.returncode}: {(done.stdout + done.stderr).strip()[-400:]}")
        for name, line in check_rpms(out, key_file, os.path.join(tmp, "rpmdb")):
            log(f"rpm -K {name}: {line}\n")
    if subprocess.run(["sha256sum", "-c", "--quiet", "SHA256SUMS"], cwd=out, check=False).returncode != 0:
        raise SignError("SHA256SUMS does not match the signed files")
    return sorted(os.path.join(out, n) for n in os.listdir(out)
                  if n.endswith(OUTPUT_SUFFIXES) or n == os.path.basename(PUBLIC_KEY))
