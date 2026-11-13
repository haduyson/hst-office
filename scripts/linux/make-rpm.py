#!/usr/bin/env python3
# SPDX-License-Identifier: AGPL-3.0-only
"""Repack the single HST Office .deb as ONE .rpm (Fedora, openSUSE, RHEL and derivatives).

No second build: the payload of the .deb that scripts/linux/make-single-deb.py wrote (install root /opt/hst-office1.0,
launchers, icons, MIME types, AppStream metainfo) is packaged again with rpmbuild, so both packages carry the same
bits. Debian-only files (lintian overrides, changelog.Debian.gz) are left out.

  make-rpm.py <HSTOffice_<release>_Linux_x86-64.deb> <out-dir>
Writes <out-dir>/HSTOffice_<release>_Linux_x86-64.rpm and adds its line to <out-dir>/SHA256SUMS.
Package: Name hst-office, Version <release core>[~<pre-release>], Release 1, Vendor HASON TECH; Requires = the
system libraries the ELF files need (scripts/linux/rpm_spec.py). Needs dpkg-deb, readelf and rpmbuild.
The package is unsigned: signing is a release step (docs/LINUX_PACKAGES.md).
"""
import argparse
import hashlib
import os
import pathlib
import re
import shutil
import subprocess
import sys
import tempfile

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))  # sibling modules (also under python3 -I)
import rpm_spec  # noqa: E402

DEB_NAME = re.compile(r"HSTOffice_(?P<release>[0-9A-Za-z.-]+)_Linux_x86-64\.deb")
DEBIAN_ONLY = ("usr/share/lintian", "usr/share/doc/hst-office/changelog.Debian.gz")


def die(msg):
    sys.exit("make-rpm: %s" % msg)


def run(*cmd, **kw):
    try:
        return subprocess.run([str(c) for c in cmd], check=True, **kw)
    except (subprocess.CalledProcessError, FileNotFoundError) as exc:
        die("%s failed: %s" % (" ".join(map(str, cmd[:3])), exc))


def is_elf64(path):
    try:
        with open(path, "rb") as fh:
            head = fh.read(5)
    except OSError:
        return False
    return head[:4] == b"\x7fELF" and head[4:5] == b"\x02"


def scan_elf(root):
    """(per-file readelf scans, every file name in the payload) for the 64-bit ELF files under `root`."""
    scans, names = [], set()
    for base, _, files in os.walk(root):
        for name in files:
            path = os.path.join(base, name)
            names.add(name)
            if os.path.islink(path) or not is_elf64(path):
                continue
            out = run("readelf", "-dVW", path, capture_output=True, text=True, env=dict(os.environ, LC_ALL="C")).stdout
            scans.append(rpm_spec.parse_readelf(out))
    return scans, names


def sha256(path):
    digest = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def add_sum(out_dir, name, digest):
    """Replace or add `name` in out_dir/SHA256SUMS (the .deb line written by make-single-deb.py stays)."""
    sums = out_dir / "SHA256SUMS"
    lines = [ln for ln in (sums.read_text(encoding="utf-8").splitlines() if sums.exists() else [])
             if ln.strip() and not ln.endswith("  " + name)]
    sums.write_text("\n".join(lines + ["%s  %s" % (digest, name)]) + "\n", encoding="utf-8")


def build(deb, out_dir, work):
    match = DEB_NAME.fullmatch(deb.name)
    if not match:
        die("not a single HST Office .deb name: %s" % deb.name)
    release = match.group("release")
    try:
        version, rel = rpm_spec.rpm_version(release)
    except ValueError as exc:
        die(str(exc))
    payload = work / "payload"
    run("dpkg-deb", "-x", deb, payload)
    for rel_path in DEBIAN_ONLY:
        target = payload / rel_path
        if target.is_dir():
            shutil.rmtree(target)
        elif target.exists():
            target.unlink()
    if not (payload / rpm_spec.INSTALL_ROOT.lstrip("/") / "program/soffice").exists():
        die("%s/program/soffice is not in the package" % rpm_spec.INSTALL_ROOT)
    scans, names = scan_elf(payload)
    requires = rpm_spec.external_requires(scans, names)
    if not requires:
        die("no library requirement found: the ELF scan failed")
    files = rpm_spec.file_list(rpm_spec.walk_payload(payload))
    spec = work / "hst-office.spec"
    spec.write_text(rpm_spec.spec_text(version, rel, requires, files, payload), encoding="utf-8")
    top = work / "rpmbuild"
    run("rpmbuild", "-bb", "--quiet", "--define", "_topdir %s" % top, "--define", "_tmppath %s" % work, spec,
        stdout=subprocess.DEVNULL)
    built = sorted((top / "RPMS").rglob("*.rpm"))
    if len(built) != 1:
        die("expected one rpm, got %s" % [p.name for p in built])
    out = out_dir / ("HSTOffice_%s_Linux_x86-64.rpm" % release)
    shutil.move(str(built[0]), out)
    return out, version, rel, requires


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("deb", type=pathlib.Path)
    ap.add_argument("out_dir", type=pathlib.Path)
    args = ap.parse_args()
    if not args.deb.is_file():
        die("no such file: %s" % args.deb)
    args.out_dir.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="hst-rpm-") as tmp:
        out, version, rel, requires = build(args.deb.resolve(), args.out_dir.resolve(), pathlib.Path(tmp))
    digest = sha256(out)
    add_sum(args.out_dir, out.name, digest)
    print("rpm: %s (%d MiB, %s-%s, %d requires, glibc >= %s)" % (out, out.stat().st_size // 2**20, version, rel,
                                                                   len(requires), rpm_spec.glibc_baseline(requires)))
    print("%s  %s" % (digest, out.name))


if __name__ == "__main__":
    main()
