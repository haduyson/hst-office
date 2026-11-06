#!/usr/bin/env python3
# SPDX-License-Identifier: AGPL-3.0-only
"""Repack the split HST Office .deb set into ONE installable package.

Upstream's installer writes ~38 inter-dependent .deb files; a graphical installer
(App Center, GNOME Software, gdebi, PackageKit) can only open one file at a time and
cannot resolve its siblings. This merges them into `hst-office`:

  * data trees are extracted over each other (paths never overlap; checked);
  * Depends = union of the external clauses, inter-package clauses dropped;
  * Conflicts/Replaces = every split package name, so installing it over a split
    install removes the old packages cleanly (the user's profile is untouched);
  * maintainer scripts: the single set shipped by the desktop-integration package
    (mime/desktop/icon-cache refresh); two sets would be ambiguous -> error;
  * postrm also deletes /opt/hst-office1.0 on remove/purge (leftovers dpkg cannot know);
  * conffiles kept only under /etc (the installer marks one file in /opt, which would
    survive `apt remove`); Installed-Size recomputed;
  * the obsolete Debian-menu file (usr/lib/menu) is dropped: .desktop entries are
    the menu, and that file named distro libreoffice-* packages;
  * adds a DEP-5 copyright file, a changelog and an AppStream metainfo file.

  make-single-deb.py <deb-dir> <out-dir> [--revision N] [--release ID]
Needs only dpkg-deb. Writes <out-dir>/HSTOffice_<release>_Linux_x86-64.deb + SHA256SUMS, where
<release> is the full release id of data/hst/release.json (e.g. 1.0.0-beta.4.1).

Package version (deb_version): epoch 1, a pre-release goes after a tilde, so apt orders
  1.0.0-2 (first single-package betas) < 1:1.0.0~beta.4.1-1 < 1:1.0.0~beta.5-1 < 1:1.0.0~rc.1-1 < 1:1.0.0-1.
Without the epoch a tilde version would sort BELOW the already published 1.0.0-2, so a user
could never upgrade to it; the epoch is the only way to have both, and stays from now on.
"""
import argparse
import datetime
import gzip
import hashlib
import json
import os
import pathlib
import re
import subprocess
import sys
import tempfile

ROOT = pathlib.Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))  # sibling modules (also under python3 -I)
from single_deb_control import (PACKAGE, MAINTAINER, INSTALL_ROOT, clause_name, clauses,  # noqa: E402,F401 (tests)
                                with_t64_alternative, die, run, merge_packages, build_control, collect_scripts)
from single_deb_texts import COPYRIGHT, LINTIAN_OVERRIDES, METAINFO  # noqa: E402

EPOCH = 1
_RELEASE = re.compile(r"(\d+\.\d+\.\d+)(?:-([0-9A-Za-z]+(?:\.[0-9A-Za-z]+)*))?")


def deb_version(release, revision="1"):
    """Debian version of a release id: 1.0.0-beta.4.1 -> 1:1.0.0~beta.4.1-1 (final 1.0.0 -> 1:1.0.0-1)."""
    match = _RELEASE.fullmatch(release)
    if not match:
        raise ValueError(f"bad release id {release!r}")
    core, pre = match.groups()
    return f"{EPOCH}:{core}" + (f"~{pre}" if pre else "") + f"-{revision}"


def read_release():
    """Release id from data/hst/release.json; its MAJOR.MINOR.MICRO must equal /VERSION."""
    try:
        release = json.loads((ROOT / "data/hst/release.json").read_text(encoding="utf-8"))["release"]
        core = (ROOT / "VERSION").read_text(encoding="utf-8").strip()
    except (OSError, ValueError, KeyError, TypeError) as exc:
        die(f"cannot read the release id: {exc}")
    if not isinstance(release, str) or not _RELEASE.fullmatch(release) or _RELEASE.fullmatch(release).group(1) != core:
        die(f"release {release!r} does not match /VERSION {core!r}")
    return release


def file_hexdigest(path, algorithm):
    """Chunked digest (hashlib.file_digest needs Python 3.11; the build container has 3.10)."""
    digest = hashlib.new(algorithm)
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()



def add_docs(stage, version, release):
    doc = stage / "usr/share/doc" / PACKAGE
    doc.mkdir(parents=True, exist_ok=True)
    (doc / "copyright").write_text(COPYRIGHT, encoding="utf-8")
    log = (f"{PACKAGE} ({version}) stable; urgency=medium\n\n  * Gói duy nhất cài được bằng trình cài đặt đồ họa.\n\n"
           " -- " + MAINTAINER + "  Thu, 01 Jan 2026 00:00:00 +0000\n")
    with open(doc / "changelog.Debian.gz", "wb") as raw, gzip.GzipFile(fileobj=raw, mode="wb", filename="", mtime=0, compresslevel=9) as gz:
        gz.write(log.encode("utf-8"))
    lint = stage / "usr/share/lintian/overrides"
    lint.mkdir(parents=True, exist_ok=True)
    (lint / PACKAGE).write_text(LINTIAN_OVERRIDES, encoding="utf-8")
    for d in (lint.parent.parent, lint.parent, lint):
        d.chmod(0o755)
    (lint / PACKAGE).chmod(0o644)
    meta = stage / "usr/share/metainfo"
    meta.mkdir(parents=True, exist_ok=True)
    kind = ' type="development"' if "-" in release else ""  # AppStream: a pre-release is a development release
    metainfo = METAINFO.format(version=release, date=datetime.date.today().isoformat(), kind=kind)
    (meta / "vn.hasontech.hstoffice.metainfo.xml").write_text(metainfo, encoding="utf-8")
    for d in (doc.parent, doc, meta):
        d.chmod(0o755)
    for f in (doc / "copyright", doc / "changelog.Debian.gz", meta / "vn.hasontech.hstoffice.metainfo.xml"):
        f.chmod(0o644)


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("deb_dir", type=pathlib.Path)
    ap.add_argument("out_dir", type=pathlib.Path)
    ap.add_argument("--revision", default=os.environ.get("HST_DEB_REVISION", "1"), help="Debian revision (default 1; the epoch already sorts above every 1.0.0-N published before)")
    ap.add_argument("--release", default=None, help="release id (default: data/hst/release.json)")
    ap.add_argument("--compression", default=os.environ.get("HST_DEB_COMPRESSION", "xz"), help="dpkg-deb -Z type (default xz)")
    args = ap.parse_args()
    if not re.fullmatch(r"[0-9][0-9A-Za-z.+~]*", args.revision):
        die(f"bad revision {args.revision!r}")
    debs = sorted(args.deb_dir.resolve().glob("*.deb"))
    if not debs:
        die(f"no .deb files in {args.deb_dir}")
    release = args.release or read_release()
    try:
        version = deb_version(release, args.revision)
    except ValueError as exc:
        die(str(exc))
    args.out_dir.mkdir(parents=True, exist_ok=True)
    out = args.out_dir / f"HSTOffice_{release}_Linux_x86-64.deb"
    with tempfile.TemporaryDirectory(prefix="hst-single-deb-") as tmp:
        work = pathlib.Path(tmp)
        infos, stage = merge_packages(debs, work)
        control = build_control(infos, stage, version)
        (stage / "DEBIAN").mkdir()
        (stage / "DEBIAN/control").write_text(control, encoding="utf-8")
        collect_scripts(infos, stage / "DEBIAN", stage)
        add_docs(stage, version, release)
        # md5sums let `dpkg --verify` and debsums work; conffiles are tracked separately.
        sums = []
        for p in sorted(stage.rglob("*")):
            if p.is_file() and not p.is_symlink() and "DEBIAN" not in p.relative_to(stage).parts[:1]:
                sums.append(f"{file_hexdigest(p, 'md5')}  {p.relative_to(stage).as_posix()}")
        (stage / "DEBIAN/md5sums").write_text("\n".join(sums) + "\n", encoding="utf-8")
        out.unlink(missing_ok=True)
        run("dpkg-deb", "--root-owner-group", f"-Z{args.compression}", "-b", stage, out, stdout=subprocess.DEVNULL)
    digest = file_hexdigest(out, "sha256")
    (args.out_dir / "SHA256SUMS").write_text(f"{digest}  {out.name}\n", encoding="utf-8")
    print(f"single deb: {len(debs)} packages -> {out} ({out.stat().st_size // 2**20} MiB, {version})")
    print(f"{digest}  {out.name}")


if __name__ == "__main__":
    main()
