#!/usr/bin/env python3
# SPDX-License-Identifier: AGPL-3.0-only
"""Server side of the Windows signing step: the token's key never leaves the signing PC, so the MSI travels.

  sign-msi-remote.py --host USER@PC push HSTOffice_<release>_Win_x86-64_en-US_vi.msi
      copies the unsigned MSI and the signing scripts to C:\\hst-test\\sign and writes sign-<name>.cmd there;
      the owner double-clicks that file in the desktop session (token connected, PIN typed into the token's
      own dialog). The signed MSI keeps the same name under C:\\hst-test\\sign\\signed.
  sign-msi-remote.py --host USER@PC verify NAME      re-checks every signature over SSH (no token needed)
  sign-msi-remote.py --host USER@PC pull NAME DIR    copies the signed MSI and its log back, writes NAME.sha256

Docs: docs/WINDOWS_SIGNING.md
"""
import argparse
import hashlib
import os
from pathlib import Path, PureWindowsPath
import re
import subprocess
import sys

HERE = Path(__file__).resolve().parent
SCRIPTS = ("sign-msi.ps1", "sign-msi-steps.ps1", "msi-authenticode-native.cs")
ROOTS = ("C:\\hst-test", "D:\\hst-test")
DEFAULT_DIR = "C:\\hst-test\\sign"
MSI_NAME = re.compile(r"HSTOffice_[0-9A-Za-z.+-]+_Win_x86-64_en-US_vi\.msi")
HOST = re.compile(r"[A-Za-z0-9._-]+@[A-Za-z0-9.-]+|[A-Za-z0-9.-]+")
THUMBPRINT = re.compile(r"[0-9A-Fa-f]{40}")
URL = re.compile(r"https?://[A-Za-z0-9.-]+(?::[0-9]+)?(?:/[A-Za-z0-9._~/-]*)?")


def inside_root(remote):
    """Writes on the signing PC are confined to the test folders."""
    path = PureWindowsPath(remote)
    if ".." in path.parts or not path.is_absolute():
        return False
    lowered = str(path).lower()
    return any(lowered == root.lower() or lowered.startswith(root.lower() + "\\") for root in ROOTS)


def checked_name(name):
    name = PureWindowsPath(name).name if "\\" in name else Path(name).name
    if not MSI_NAME.fullmatch(name):
        raise ValueError(f"not an HST Office Windows installer name: {name}")
    return name


def ssh_options(key):
    options = ["-o", "BatchMode=yes", "-o", "ConnectTimeout=15", "-o", "ServerAliveInterval=30"]
    return (["-i", key] if key else []) + options


def scp_path(remote):
    return remote.replace("\\", "/")


def sign_command(remote_dir, name, thumbprint=None, timestamp_url=None):
    """The command line the owner runs on the desktop, as a .cmd file next to the scripts."""
    args = [f'-Msi "{remote_dir}\\{name}"', f'-OutMsi "{remote_dir}\\signed\\{name}"']
    if thumbprint:
        args.append(f"-Thumbprint {thumbprint}")
    if timestamp_url:
        args.append(f"-TimestampUrl {timestamp_url}")
    return (f'powershell -NoProfile -ExecutionPolicy Bypass -File "{remote_dir}\\sign-msi.ps1" ' + " ".join(args))


def cmd_file(remote_dir, name, thumbprint=None, timestamp_url=None):
    return "\r\n".join(["@echo off", "rem Sign the HST Office installer with the USB token (type the PIN into the token's dialog).",
                        sign_command(remote_dir, name, thumbprint, timestamp_url),
                        "echo Exit code %ERRORLEVEL% - 0 means every signature is valid.", "pause", ""])


def verify_command(remote_dir, name):
    return (f'powershell -NoProfile -ExecutionPolicy Bypass -File "{remote_dir}\\sign-msi.ps1" '
            f'-Msi "{remote_dir}\\signed\\{name}" -VerifyOnly')


def sha256_line(path):
    digest = hashlib.sha256()
    with open(path, "rb") as stream:
        for block in iter(lambda: stream.read(1 << 20), b""):
            digest.update(block)
    return f"{digest.hexdigest()}  {Path(path).name}\n"


class Remote:
    def __init__(self, host, key, remote_dir, run=subprocess.run):
        if not HOST.fullmatch(host):
            raise ValueError(f"bad host: {host}")
        if not inside_root(remote_dir):
            raise ValueError(f"refusing to write outside {' / '.join(ROOTS)}: {remote_dir}")
        self.host, self.key, self.dir, self.run = host, key, str(PureWindowsPath(remote_dir)), run

    def ssh(self, command, timeout=7200):
        return self.run(["ssh", *ssh_options(self.key), self.host, command], timeout=timeout)

    def scp(self, sources, target, timeout=3600):
        return self.run(["scp", "-q", *ssh_options(self.key), *map(str, sources), target], timeout=timeout, check=True)

    def push(self, msi, thumbprint=None, timestamp_url=None, scripts_dir=HERE, temp_dir=None):
        name = checked_name(Path(msi).name)
        if not Path(msi).is_file():
            raise FileNotFoundError(msi)
        cmd = Path(temp_dir or os.environ.get("TMPDIR", "/tmp")) / f"sign-{Path(name).stem}.cmd"
        cmd.write_bytes(cmd_file(self.dir, name, thumbprint, timestamp_url).encode("ascii"))
        try:
            self.ssh(f'if not exist "{self.dir}\\signed" mkdir "{self.dir}\\signed"', timeout=120)
            self.scp([Path(msi), *(Path(scripts_dir) / script for script in SCRIPTS), cmd],
                     f"{self.host}:{scp_path(self.dir)}/")
        finally:
            cmd.unlink(missing_ok=True)
        print(f"local {sha256_line(msi)}", end="")
        print(f"On the signing PC, as the user whose session sees the token, open {self.dir} and run {cmd.name}")
        return 0

    def verify(self, name):
        return self.ssh(verify_command(self.dir, checked_name(name))).returncode

    def pull(self, name, local_dir):
        name = checked_name(name)
        local = Path(local_dir)
        local.mkdir(parents=True, exist_ok=True)
        stem = Path(name).stem
        for remote in (f"{self.dir}\\signed\\{name}", f"{self.dir}\\signed\\{stem}.sign.log"):
            self.scp([f"{self.host}:{scp_path(remote)}"], str(local))
        line = sha256_line(local / name)
        (local / f"{name}.sha256").write_text(line, encoding="ascii")
        print(line, end="")
        return 0


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--host", required=True, help="ssh destination of the signing PC, USER@ADDRESS")
    parser.add_argument("--key", default=os.environ.get("HST_WINTEST_KEY"), help="ssh identity file")
    parser.add_argument("--remote-dir", default=DEFAULT_DIR)
    commands = parser.add_subparsers(dest="command", required=True)
    push = commands.add_parser("push")
    push.add_argument("msi", type=Path)
    push.add_argument("--thumbprint", help="certificate to use when the store holds several")
    push.add_argument("--timestamp-url", help="RFC 3161 timestamp server (default: sign-msi.ps1's)")
    commands.add_parser("verify").add_argument("name")
    pull = commands.add_parser("pull")
    pull.add_argument("name")
    pull.add_argument("dir", type=Path)
    args = parser.parse_args(argv)
    if getattr(args, "thumbprint", None) and not THUMBPRINT.fullmatch(args.thumbprint):
        parser.error("--thumbprint must be 40 hex digits")
    if getattr(args, "timestamp_url", None) and not URL.fullmatch(args.timestamp_url):
        parser.error("--timestamp-url must be a plain http(s) URL")
    try:
        remote = Remote(args.host, args.key, args.remote_dir)
        if args.command == "push":
            return remote.push(args.msi, args.thumbprint, args.timestamp_url)
        if args.command == "verify":
            return remote.verify(args.name)
        return remote.pull(args.name, args.dir)
    except (ValueError, OSError, subprocess.SubprocessError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
