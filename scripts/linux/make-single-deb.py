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

  make-single-deb.py <deb-dir> <out-dir> [--revision N]
Needs only dpkg-deb. Writes <out-dir>/HSTOffice_<version>_Linux_x86-64.deb + SHA256SUMS.
"""
import argparse
import datetime
import gzip
import hashlib
import os
import pathlib
import re
import shutil
import subprocess
import sys
import tempfile

ROOT = pathlib.Path(__file__).resolve().parent.parent.parent
PACKAGE = "hst-office"
MAINTAINER = "HASON TECH <lienhe@hasontech.vn>"
HOMEPAGE = "https://office.hasontech.vn"
SCRIPTS = ("preinst", "postinst", "prerm", "postrm")

DESCRIPTION = """\
Description: Bộ ứng dụng văn phòng HST Office của HASON TECH
 HST Office gồm Writer (văn bản), Sheets (bảng tính), Slides (trình chiếu),
 Draw, Math và Base, giao diện tiếng Việt.
 Đọc và ghi ODF, DOCX, XLSX, PPTX, PDF.
 .
 Gói duy nhất này chứa toàn bộ ứng dụng, từ điển, biểu tượng, lối tắt trong
 menu ứng dụng và liên kết loại tệp. Cài trong /opt/hst-office1.0 và có thể
 cài cùng bản LibreOffice của bản phân phối.
 .
 Xây dựng từ LibreOffice của The Document Foundation. © 2026 HASON TECH."""

COPYRIGHT = """\
Format: https://www.debian.org/doc/packaging-manuals/copyright-format/1.0/
Upstream-Name: HST Office
Upstream-Contact: HASON TECH <lienhe@hasontech.vn>
Source: https://github.com/haduyson/hst-office

Files: *
Copyright: 2000-2026 The Document Foundation and LibreOffice contributors
License: MPL-2.0
 This Source Code Form is subject to the terms of the Mozilla Public License,
 v. 2.0. The full text and the licences of bundled third-party components are in
 /opt/hst-office1.0/LICENSE and /opt/hst-office1.0/LICENSE.html. On Debian systems
 the MPL-2.0 text is also in /usr/share/common-licenses/MPL-2.0.

Files: opt/hst-office1.0/share/extensions/hst-*
Copyright: 2026 HASON TECH
License: AGPL-3.0-only
 On Debian systems the full text is in /usr/share/common-licenses/AGPL-3
 (or at https://www.gnu.org/licenses/agpl-3.0.html).
"""

# Intentional departures from Debian policy, same as upstream LibreOffice packaging:
# the suite lives under /opt (no distro file collision, coexists with the distro
# LibreOffice) and ships its own libraries and executable-bit shared objects.
LINTIAN_OVERRIDES = """\
hst-office: dir-or-file-in-opt
hst-office: embedded-library
hst-office: shared-library-is-executable
"""

# Appended to the desktop-integration postrm. The install root belongs to this package
# alone; what dpkg cannot know about (runtime caches, a configuration file kept by a
# replaced split package in "config-files" state) would otherwise survive a removal.
POSTRM_CLEANUP = """\
# HST Office: remove the install root's leftovers (see make-single-deb.py).
if [ "$1" = purge ] || { [ "$1" = remove ] && [ -z "${2:-}" ]; }; then
  rm -rf __ROOT__
fi
exit 0
"""

INSTALL_ROOT = "/opt/hst-office1.0"

METAINFO = """\
<?xml version="1.0" encoding="UTF-8"?>
<component type="desktop-application">
  <id>vn.hasontech.hstoffice</id>
  <metadata_license>CC0-1.0</metadata_license>
  <project_license>MPL-2.0 AND AGPL-3.0-only</project_license>
  <name>HST Office</name>
  <developer id="vn.hasontech"><name>HASON TECH</name></developer>
  <summary>Bộ ứng dụng văn phòng: văn bản, bảng tính, trình chiếu</summary>
  <description>
    <p>HST Office là bộ ứng dụng văn phòng miễn phí của HASON TECH với giao diện tiếng Việt: Writer (văn bản), Sheets (bảng tính), Slides (trình chiếu), Draw, Math và Base.</p>
    <p>Đọc và ghi ODF, DOCX, XLSX, PPTX và PDF.</p>
  </description>
  <launchable type="desktop-id">hst-office1.0-startcenter.desktop</launchable>
  <icon type="stock">hst-office1.0-startcenter</icon>
  <url type="homepage">https://office.hasontech.vn</url>
  <content_rating type="oars-1.1"/>
  <categories><category>Office</category></categories>
  <provides><binary>hst-office</binary></provides>
  <releases><release version="{version}" date="{date}"/></releases>
</component>
"""


def die(msg):
    sys.exit(f"make-single-deb: {msg}")


def run(*cmd, **kw):
    try:
        return subprocess.run(cmd, check=True, **kw)
    except (subprocess.CalledProcessError, FileNotFoundError) as exc:
        die(f"{' '.join(map(str, cmd[:3]))} failed: {exc}")


def file_hexdigest(path, algorithm):
    """Chunked digest (hashlib.file_digest needs Python 3.11; the build container has 3.10)."""
    digest = hashlib.new(algorithm)
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def parse_control(text):
    """Control paragraph -> {Field: value}; continuation lines are joined with \\n."""
    fields, key = {}, None
    for line in text.splitlines():
        if line[:1] in " \t" and key:
            fields[key] += "\n" + line
        elif ":" in line:
            key, _, val = line.partition(":")
            fields[key] = val.strip()
    return fields


def clauses(value):
    return [c.strip() for c in (value or "").replace("\n", " ").split(",") if c.strip()]


def clause_name(clause):
    return re.split(r"[\s(:|]", clause, maxsplit=1)[0]


# Libraries whose package name never changed in the 64-bit time_t transition.
NO_T64 = {"libc6", "libgcc-s1", "libstdc++6", "libm6"}


def with_t64_alternative(clause):
    """`libfoo (>= 1)` <-> `libfoot64 (>= 1)`: name both spellings of a library package.

    One .deb must resolve on Ubuntu 22.04 (pre-transition names) and on Ubuntu 24.04+ /
    Debian 13, which renamed the libraries whose ABI changed with 64-bit time_t
    (libglib2.0-0t64, libcups2t64, ...). The input names come from either side; an
    alternative that does not exist on a distribution is ignored by apt.
    """
    out = []
    for alt in (a.strip() for a in clause.split("|")):
        out.append(alt)
        m = re.fullmatch(r"(lib[^\s(:]*)(.*)", alt)
        if not m or m.group(1) in NO_T64:
            continue
        name, rest = m.groups()
        other = name[:-3] if name.endswith("t64") else name + "t64"
        out.append(other + rest)
    return " | ".join(dict.fromkeys(out))


def merge_packages(debs, work):
    """Extract every deb into one staging tree; return (control info per package, staging)."""
    stage = work / "stage"
    stage.mkdir()
    seen, infos = {}, []
    for deb in debs:
        ctl = work / "ctl" / deb.stem
        ctl.parent.mkdir(exist_ok=True)
        run("dpkg-deb", "-e", deb, ctl)
        info = parse_control((ctl / "control").read_text(encoding="utf-8"))
        info["_ctl"] = ctl
        pkg_tree = work / "tree" / deb.stem
        pkg_tree.mkdir(parents=True)
        run("dpkg-deb", "-x", deb, pkg_tree)
        for path in sorted(pkg_tree.rglob("*")):
            if path.is_dir() and not path.is_symlink():
                continue
            rel = path.relative_to(pkg_tree).as_posix()
            if rel in seen:
                die(f"{rel} is in both {seen[rel]} and {info['Package']}")
            seen[rel] = info["Package"]
        # Same tree layout: copy with symlinks/modes preserved (cp -a keeps both).
        run("cp", "-a", "--no-preserve=ownership", f"{pkg_tree}/.", stage)
        infos.append(info)
    shutil.rmtree(stage / "usr/lib/menu", ignore_errors=True)
    if (stage / "usr/lib").is_dir() and not any((stage / "usr/lib").iterdir()):
        (stage / "usr/lib").rmdir()
    # Directories: dpkg owns them as root 0755 regardless of what packages said.
    for d in [stage, *[p for p in stage.rglob("*") if p.is_dir() and not p.is_symlink()]]:
        d.chmod(0o755)
    return infos, stage


def build_control(infos, stage, version):
    names = {i["Package"] for i in infos}
    depends, replaces = [], list(sorted(names))
    for info in infos:
        for clause in clauses(info.get("Depends")):
            if clause_name(clause) not in names and clause not in depends:
                depends.append(clause)
        for field in ("Replaces", "Conflicts"):
            for clause in clauses(info.get(field)):
                if clause_name(clause) not in names and clause_name(clause) not in replaces:
                    replaces.append(clause_name(clause))
    # Version-bounded clauses on the same library are redundant with the unbounded one.
    unbounded = {clause_name(c) for c in depends if "(" not in c and "|" not in c}
    depends = [c for c in depends if "(" not in c or clause_name(c) not in unbounded]
    if list((stage / "opt/hst-office1.0/program").glob("python-core-*")):
        # Bundled Python (--enable-python=internal): the distribution's one is not needed.
        depends = [c for c in depends if not re.match(r"(libpython|python3)", c)]
    depends = [with_t64_alternative(c) for c in depends]
    archs = {i.get("Architecture") for i in infos} - {"all"}
    if archs != {"amd64"}:
        die(f"expected only amd64/all packages, got {sorted(archs)}")
    size = int(subprocess.run(["du", "-sk", str(stage)], capture_output=True, text=True, check=True).stdout.split()[0])
    return "\n".join([
        f"Package: {PACKAGE}",
        f"Version: {version}",
        "Architecture: amd64",
        f"Maintainer: {MAINTAINER}",
        "Section: editors",
        "Priority: optional",
        f"Homepage: {HOMEPAGE}",
        "Depends: " + ", ".join(depends),
        "Recommends: desktop-file-utils, shared-mime-info",
        "Conflicts: " + ", ".join(replaces),
        "Replaces: " + ", ".join(replaces),
        f"Installed-Size: {size}",
        DESCRIPTION,
    ]) + "\n"


def script_is_empty(path):
    """True when a maintainer script has no command besides `exit 0`."""
    body = [ln.strip() for ln in path.read_text(encoding="utf-8").splitlines()]
    return all(not ln or ln.startswith("#") or ln == "exit 0" for ln in body)


def collect_scripts(infos, ctl_out, stage):
    for name in (*SCRIPTS, "triggers"):
        owners = [i for i in infos if (i["_ctl"] / name).is_file() and not script_is_empty(i["_ctl"] / name)]
        if len(owners) > 1:
            die(f"{name} shipped by several packages ({', '.join(i['Package'] for i in owners)}); merge by hand")
        if owners:
            shutil.copy2(owners[0]["_ctl"] / name, ctl_out / name)
            (ctl_out / name).chmod(0o755 if name in SCRIPTS else 0o644)
    if not (stage / INSTALL_ROOT.lstrip("/")).is_dir():
        die(f"{INSTALL_ROOT} is not in the package")
    postrm = ctl_out / "postrm"
    if not postrm.is_file():
        die("no postrm to extend: the desktop-integration package is missing")
    body = postrm.read_text(encoding="utf-8").rstrip()
    body = body.removesuffix("exit 0").rstrip()
    postrm.write_text(body + "\n\n" + POSTRM_CLEANUP.replace("__ROOT__", INSTALL_ROOT), encoding="utf-8")
    conf = []
    for info in infos:
        f = info["_ctl"] / "conffiles"
        for line in f.read_text(encoding="utf-8").splitlines() if f.is_file() else []:
            path = os.path.normpath(line.strip())  # drops the "/./" the installer writes
            if path.startswith("/etc/") and path not in conf:
                conf.append(path)
    for path in conf:
        if not (stage / path.lstrip("/")).is_file():
            die(f"conffile {path} is not in the package")
    if conf:
        (ctl_out / "conffiles").write_text("\n".join(conf) + "\n", encoding="utf-8")


def add_docs(stage, version):
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
    (meta / "vn.hasontech.hstoffice.metainfo.xml").write_text(METAINFO.format(version=version.split("-")[0], date=datetime.date.today().isoformat()), encoding="utf-8")
    for d in (doc.parent, doc, meta):
        d.chmod(0o755)
    for f in (doc / "copyright", doc / "changelog.Debian.gz", meta / "vn.hasontech.hstoffice.metainfo.xml"):
        f.chmod(0o644)


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("deb_dir", type=pathlib.Path)
    ap.add_argument("out_dir", type=pathlib.Path)
    ap.add_argument("--revision", default=os.environ.get("HST_DEB_REVISION", "2"), help="Debian revision (default 2: above the 1.0.0-1 of the first single-package release)")
    ap.add_argument("--compression", default=os.environ.get("HST_DEB_COMPRESSION", "xz"), help="dpkg-deb -Z type (default xz)")
    args = ap.parse_args()
    if not re.fullmatch(r"[0-9][0-9A-Za-z.+~]*", args.revision):
        die(f"bad revision {args.revision!r}")
    debs = sorted(args.deb_dir.resolve().glob("*.deb"))
    if not debs:
        die(f"no .deb files in {args.deb_dir}")
    upstream = (ROOT / "VERSION").read_text(encoding="utf-8").strip()
    version = f"{upstream}-{args.revision}"
    args.out_dir.mkdir(parents=True, exist_ok=True)
    out = args.out_dir / f"HSTOffice_{upstream}_Linux_x86-64.deb"
    with tempfile.TemporaryDirectory(prefix="hst-single-deb-") as tmp:
        work = pathlib.Path(tmp)
        infos, stage = merge_packages(debs, work)
        control = build_control(infos, stage, version)
        (stage / "DEBIAN").mkdir()
        (stage / "DEBIAN/control").write_text(control, encoding="utf-8")
        collect_scripts(infos, stage / "DEBIAN", stage)
        add_docs(stage, version)
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
