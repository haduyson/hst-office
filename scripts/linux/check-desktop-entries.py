#!/usr/bin/env python3
# SPDX-License-Identifier: AGPL-3.0-only
"""Fail when a launcher (.desktop) entry in the HST Office .deb names an upstream product.

  check-desktop-entries.py <package.deb> [...]
The fields a desktop shell shows or searches (Name, GenericName, Comment, Keywords,
X-GNOME-FullName), in every locale (Key[xx]=), must not contain OpenOffice, LibreOffice or
The Document Foundation. Exec and MimeType are not read.
The window class a launcher claims (StartupWMClass) must be its own launcher id: a launcher
usr/share/applications/<id>.desktop links to it and StartupWMClass=<id> (vn.hasontech.hstoffice-writer),
the class HST's windows carry. A class or Icon of LibreOffice's (libreoffice-*, openoffice*)
would group HST windows with an installed LibreOffice's, and LibreOffice's windows with HST's.
Exit 0 = clean, 1 = a hit or no launcher in a package, 2 = bad arguments. Needs dpkg-deb.
"""
import io
import re
import subprocess
import sys
import tarfile

FIELDS = re.compile(r"^(Name|GenericName|Comment|Keywords|X-GNOME-FullName)(\[[^\]]+\])?\s*=(.*)$")
NAMES = re.compile(r"open\s*office|libre\s*office|document\s*foundation", re.IGNORECASE)


UPSTREAM_ID = re.compile(r"^(libre\s*office|open\s*office)", re.IGNORECASE)


def package_launchers(deb):
    """([(path, text)] of every .desktop file, {file path: launcher id} from usr/share/applications links)."""
    data = subprocess.run(["dpkg-deb", "--fsys-tarfile", deb], check=True, capture_output=True).stdout
    entries, ids = [], {}
    with tarfile.open(fileobj=io.BytesIO(data)) as tar:
        for member in tar:
            name = member.name.lstrip("./")
            if not name.endswith(".desktop"):
                continue
            if member.isfile():
                entries.append((name, tar.extractfile(member).read().decode("utf-8", "replace")))
                if name.startswith("usr/share/applications/"):
                    ids[name] = name.rsplit("/", 1)[1][: -len(".desktop")]
            elif member.issym() and name.startswith("usr/share/applications/"):
                ids[member.linkname.lstrip("/")] = name.rsplit("/", 1)[1][: -len(".desktop")]
    return entries, ids


def desktop_entries(deb):
    """(path, text) of every .desktop file under usr/share/applications or /opt in the package."""
    return package_launchers(deb)[0]


def identity_hits(text, launcher_id):
    """StartupWMClass and Icon lines that claim another product's window class or icon, or a
    StartupWMClass that is not the id of the launcher (`launcher_id`, None when no link)."""
    found = []
    for line in text.splitlines():
        key, _, value = line.strip().partition("=")
        if key == "StartupWMClass":
            if UPSTREAM_ID.match(value) or (launcher_id and value != launcher_id):
                found.append(f"{line.strip()} (launcher id {launcher_id})")
        elif key == "Icon" and UPSTREAM_ID.match(value):
            found.append(line.strip())
    return found


def hits(text):
    """Visible/searchable launcher lines that name an upstream product."""
    found = []
    for line in text.splitlines():
        match = FIELDS.match(line.strip())
        if match and NAMES.search(match.group(3)):
            found.append(line.strip())
    return found


def main(argv):
    if not argv:
        print(__doc__.strip(), file=sys.stderr)
        return 2
    failures = 0
    for deb in argv:
        entries, ids = package_launchers(deb)
        if not entries:
            print(f"FAIL {deb}: no .desktop launcher in the package")
            failures += 1
        for path, text in entries:
            for line in hits(text) + identity_hits(text, ids.get(path)):
                print(f"FAIL {path}: {line}")
                failures += 1
        print(f"desktop entries: {deb}: {len(entries)} launchers checked")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
