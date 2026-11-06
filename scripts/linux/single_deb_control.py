# SPDX-License-Identifier: AGPL-3.0-only
"""Control file and maintainer scripts of the single HST Office .deb (scripts/linux/make-single-deb.py):
merge the split packages' data trees, Depends/Conflicts/Replaces, scripts and conffiles."""
import os
import re
import shutil
import subprocess
import sys

from single_deb_texts import DESCRIPTION, POSTRM_CLEANUP

PACKAGE = "hst-office"
MAINTAINER = "HASON TECH <lienhe@hasontech.vn>"
HOMEPAGE = "https://office.hasontech.vn"
# Distribution packages the merged package needs beyond the split packages' own Depends.
EXTRA_DEPENDS = ["fonts-urw-base35"]
SCRIPTS = ("preinst", "postinst", "prerm", "postrm")
INSTALL_ROOT = "/opt/hst-office1.0"


def die(msg):
    sys.exit(f"make-single-deb: {msg}")


def run(*cmd, **kw):
    try:
        return subprocess.run(cmd, check=True, **kw)
    except (subprocess.CalledProcessError, FileNotFoundError) as exc:
        die(f"{' '.join(map(str, cmd[:3]))} failed: {exc}")



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
    # Metric-compatible Symbol font: MathType/Word equations without the Windows Symbol font
    # (Linux) draw long arrows from its pieces; OpenSymbol's pieces leave gaps.
    for extra in EXTRA_DEPENDS:
        if extra not in depends:
            depends.append(extra)
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
