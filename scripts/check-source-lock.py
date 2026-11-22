#!/usr/bin/env python3
# SPDX-License-Identifier: LicenseRef-HST-Proprietary
# Copyright (C) 2026 HASON TECH
"""Validate the LibreOffice source lock and build-script pins.

Use --tarballs DIR to verify local archives and --remote to verify the peeled tag.
The default check is offline so repository quality checks need no network access.
"""
import argparse
import hashlib
import json
import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE_PINS = (
    "scripts/linux/ci-build.sh", "scripts/macos/trial-build.sh",
    "scripts/windows/trial-build.sh", "scripts/windows/preflight-local.sh",
    "scripts/patches/ribbon_ux_writer_cxx.py",
    "scripts/patches/generate-ribbon-tooltips.py",
    "tests/unit/test_sheets_excel_formula_conventions.py",
)


def check_lock(root, tarballs=None, remote=False):
    lock = json.loads((root / "upstream/libreoffice-lock.json").read_text())
    version = lock["version"]
    if not re.fullmatch(r"\d+\.\d+\.\d+\.\d+", version):
        raise ValueError("invalid source version")
    tag = "libreoffice-" + version
    if lock["gitTag"] != tag or not re.fullmatch(r"[0-9a-f]{40}", lock["gitCommit"]):
        raise ValueError("invalid source tag or commit")
    expected = {f"{prefix}-{version}.tar.xz" for prefix in
                ("libreoffice", "libreoffice-dictionaries", "libreoffice-translations", "libreoffice-help")}
    items = lock["tarballs"]
    if len(items) != len(expected) or {item["name"] for item in items} != expected:
        raise ValueError("expected exactly core, dictionaries, translations and help archives")
    release = version.rsplit(".", 1)[0]
    for item in items:
        name = item["name"]
        url = f"https://download.documentfoundation.org/libreoffice/src/{release}/{name}"
        if item["url"] != url or item["signature"] != name + ".asc":
            raise ValueError(f"source URL or signature mismatch: {name}")
        if not re.fullmatch(r"[0-9a-f]{64}", item["sha256"]):
            raise ValueError(f"invalid SHA-256: {name}")
        if tarballs is not None:
            digest = hashlib.sha256()
            with (tarballs / name).open("rb") as source:
                for chunk in iter(lambda: source.read(1024 * 1024), b""):
                    digest.update(chunk)
            if digest.hexdigest() != item["sha256"]:
                raise ValueError(f"SHA-256 mismatch: {name}")
    # These scripts select archives independently of the download lock.
    for name in SOURCE_PINS:
        pins = re.findall(
            r"(?:libreoffice(?:-translations|-dictionaries|-help)?-|LO_VER(?:SION)?=)"
            r"(\d+\.\d+\.\d+\.\d+)\b", (root / name).read_text())
        if not pins or any(pin != version for pin in pins):
            raise ValueError(f"source version differs from lock: {name}")
    if remote:
        result = subprocess.run(
            ["git", "ls-remote", "--tags", "https://git.libreoffice.org/core", tag + "*"],
            check=True, capture_output=True, text=True, timeout=120)
        refs = dict(line.split()[::-1] for line in result.stdout.splitlines())
        commit = refs.get(f"refs/tags/{tag}^{{}}", refs.get(f"refs/tags/{tag}"))
        if commit != lock["gitCommit"]:
            raise ValueError("remote tag commit differs from lock")
    return version


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--tarballs", type=Path)
    parser.add_argument("--remote", action="store_true")
    args = parser.parse_args()
    try:
        version = check_lock(ROOT, args.tarballs, args.remote)
    except (OSError, ValueError, KeyError, subprocess.SubprocessError) as error:
        print(f"source lock: FAIL: {error}")
        return 1
    print(f"source lock: OK ({version})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
