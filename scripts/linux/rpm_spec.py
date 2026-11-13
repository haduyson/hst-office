# SPDX-License-Identifier: AGPL-3.0-only
"""Pure parts of scripts/linux/make-rpm.py: RPM version, ELF dependency scan and the spec file text.

Requires are computed here, not by rpmbuild (AutoReqProv: no): every DT_NEEDED soname of the 64-bit ELF files in
the payload that the payload does not ship itself becomes `soname()(64bit)`, each symbol version it needs from that
library `soname(VERSION)(64bit)` (what rpm's own elfdeps writes). The bundled libraries are neither required nor
provided, so the package never claims a library of the distribution and never pulls the distribution's LibreOffice.
"""
import os
import re

PACKAGE = "hst-office"
INSTALL_ROOT = "/opt/hst-office1.0"
LICENSE = "MPL-2.0 AND AGPL-3.0-only"
URL = "https://office.hasontech.vn"
VENDOR = "HASON TECH"
PACKAGER = "HASON TECH <lienhe@hasontech.vn>"
# Same role as the .deb's fonts-urw-base35: metric-compatible Symbol font for equations. A weak dependency, because
# the package name differs between distributions and a missing font must not block the install.
RECOMMENDS = ["urw-base35-fonts", "desktop-file-utils", "shared-mime-info"]
_RELEASE = re.compile(r"(\d+\.\d+\.\d+)(?:-([0-9A-Za-z]+(?:\.[0-9A-Za-z]+)*))?")
_SAFE_PATH = re.compile(r"/[A-Za-z0-9._+/-]+")


def rpm_version(release):
    """(Version, Release) of a release id: 1.0.2 -> ("1.0.2", "1"); 1.0.2-beta.1 -> ("1.0.2~beta.1", "1").

    rpm (>= 4.10, every supported distribution) sorts a tilde before the bare version, so a pre-release upgrades
    to the final release of the same number."""
    match = _RELEASE.fullmatch(release or "")
    if not match:
        raise ValueError("bad release id %r" % (release,))
    core, pre = match.groups()
    return core + ("~" + pre if pre else ""), "1"


def parse_readelf(text):
    """(soname or None, [needed], {library: {version names}}) from `readelf -dVW` output."""
    soname, needed, versions, current = None, [], {}, None
    for line in text.splitlines():
        m = re.search(r"\((NEEDED|SONAME)\)\s+\S+ \S+: \[([^\]]+)\]", line)
        if m:
            if m.group(1) == "NEEDED":
                needed.append(m.group(2))
            else:
                soname = m.group(2)
            continue
        m = re.search(r"\bFile: (\S+)\s+Cnt:", line)
        if m:
            current = m.group(1)
            versions.setdefault(current, set())
            continue
        m = re.search(r"\bName: (\S+)\s+Flags:", line)
        if m and current:
            versions[current].add(m.group(1))
    return soname, needed, versions


def external_requires(scans, bundled_names):
    """Sorted Requires from the per-file scans; `bundled_names` = every file name and SONAME in the payload."""
    internal = set(bundled_names)
    for soname, _, _ in scans:
        if soname:
            internal.add(soname)
    wanted = set()
    for _, needed, versions in scans:
        for lib in needed:
            if lib not in internal:
                wanted.add("%s()(64bit)" % lib)
        for lib, names in versions.items():
            if lib not in internal:
                wanted.update("%s(%s)(64bit)" % (lib, name) for name in names)
    return sorted(wanted)


def baseline(requires, prefix="GLIBC_"):
    """Highest <prefix>x.y[.z] symbol version needed from any library (GLIBC_: the oldest glibc it runs on, from libc,
    libm, ...; GLIBCXX_: the oldest libstdc++), or None."""
    found = [tuple(int(p) for p in m.group(1).split(".")) for r in requires
             for m in [re.search(r"\(" + prefix + r"(\d+(?:\.\d+)+)\)\(64bit\)$", r)] if m]
    return ".".join(map(str, max(found))) if found else None


def file_list(payload_paths):
    """%files entries: the whole install root, then each file outside it (shared system directories stay unowned)."""
    entries = [INSTALL_ROOT]
    for path in sorted(payload_paths):
        if path == INSTALL_ROOT or path.startswith(INSTALL_ROOT + "/"):
            continue
        if not _SAFE_PATH.fullmatch(path):
            raise ValueError("path not representable in %%files: %r" % path)
        if path.startswith("/usr/share/doc/" + PACKAGE + "/"):
            continue
        entries.append(path)
    entries.append("%doc /usr/share/doc/" + PACKAGE)
    return entries


SCRIPT_REFRESH = """\
if [ -x /usr/bin/update-mime-database ]; then update-mime-database /usr/share/mime >/dev/null 2>&1 || :; fi
if [ -x /usr/bin/update-desktop-database ]; then update-desktop-database -q /usr/share/applications >/dev/null 2>&1 || :; fi
if [ -e /usr/share/icons/hicolor/icon-theme.cache ]; then
  touch --no-create /usr/share/icons/hicolor >/dev/null 2>&1 || :
  if command -v gtk-update-icon-cache >/dev/null 2>&1; then gtk-update-icon-cache -q /usr/share/icons/hicolor >/dev/null 2>&1 || :; fi
fi
"""

DESCRIPTION = """\
HST Office gồm Writer (văn bản), Sheets (bảng tính), Slides (trình chiếu),
Draw, Math và Base, giao diện tiếng Việt. Đọc và ghi ODF, DOCX, XLSX, PPTX, PDF.

Gói duy nhất này chứa toàn bộ ứng dụng, từ điển, biểu tượng, lối tắt trong
menu ứng dụng và liên kết loại tệp. Cài trong /opt/hst-office1.0 và có thể
cài cùng bản LibreOffice của bản phân phối.

Xây dựng từ LibreOffice của The Document Foundation. © 2026 HASON TECH."""


def spec_text(version, release, requires, files, payload_dir):
    """The complete spec: no build, %install hard-links the prepared payload, scriptlets refresh the caches."""
    if any(c in str(payload_dir) for c in " \t\n%\"'\\"):
        raise ValueError("payload directory must not contain spaces, quotes or %")
    lines = [
        "%global debug_package %{nil}",
        "%global __os_install_post %{nil}",
        "%global __arch_install_post %{nil}",
        "%global _build_id_links none",
        "%global _binary_payload w6T0.xzdio",
        "Name: " + PACKAGE,
        "Version: " + version,
        "Release: " + release,
        "Summary: Bộ ứng dụng văn phòng HST Office của HASON TECH",
        "License: " + LICENSE,
        "URL: " + URL,
        "Vendor: " + VENDOR,
        "Packager: " + PACKAGER,
        "Group: Productivity/Office/Suite",
        "ExclusiveArch: x86_64",
        "AutoReqProv: no",
    ]
    lines += ["Requires: " + r for r in requires]
    lines += ["Recommends: " + r for r in RECOMMENDS]
    lines += ["", "%description", DESCRIPTION, "", "%install",
              "mkdir -p %{buildroot}", "cp -al " + str(payload_dir) + "/. %{buildroot}/", "",
              "%post", SCRIPT_REFRESH, "%postun", SCRIPT_REFRESH,
              "# Erase (not upgrade): remove what rpm cannot know about under the install root (runtime caches).",
              'if [ "$1" -eq 0 ]; then rm -rf ' + INSTALL_ROOT + "; fi", "",
              "%files", "%defattr(-,root,root,-)"] + files
    return "\n".join(lines) + "\n"


def walk_payload(root):
    """Absolute package paths of every file and symlink (not real directories) under the extracted payload `root`."""
    out = []
    for base, dirs, names in os.walk(root):
        for name in names + [d for d in dirs if os.path.islink(os.path.join(base, d))]:
            out.append("/" + os.path.relpath(os.path.join(base, name), root).replace(os.sep, "/"))
    return out
