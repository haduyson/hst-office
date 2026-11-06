#!/usr/bin/env python3
# SPDX-License-Identifier: AGPL-3.0-only
"""Fail when a launcher (.desktop) entry in the HST Office .deb names an upstream product.

  check-desktop-entries.py <package.deb> [...]
The fields a desktop shell shows or searches (Name, GenericName, Comment, Keywords,
X-GNOME-FullName), in every locale (Key[xx]=), must not contain OpenOffice, LibreOffice or
The Document Foundation. Technical keys (Exec, Icon, StartupWMClass, MimeType) are not read.
Exit 0 = clean, 1 = a hit or no launcher in a package, 2 = bad arguments. Needs dpkg-deb.
"""
import io
import re
import subprocess
import sys
import tarfile

FIELDS = re.compile(r"^(Name|GenericName|Comment|Keywords|X-GNOME-FullName)(\[[^\]]+\])?\s*=(.*)$")
NAMES = re.compile(r"open\s*office|libre\s*office|document\s*foundation", re.IGNORECASE)


def desktop_entries(deb):
    """(path, text) of every .desktop file under usr/share/applications or /opt in the package."""
    data = subprocess.run(["dpkg-deb", "--fsys-tarfile", deb], check=True, capture_output=True).stdout
    with tarfile.open(fileobj=io.BytesIO(data)) as tar:
        for member in tar:
            if member.isfile() and member.name.endswith(".desktop"):
                yield member.name.lstrip("./"), tar.extractfile(member).read().decode("utf-8", "replace")


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
        entries = list(desktop_entries(deb))
        if not entries:
            print(f"FAIL {deb}: no .desktop launcher in the package")
            failures += 1
        for path, text in entries:
            for line in hits(text):
                print(f"FAIL {path}: {line}")
                failures += 1
        print(f"desktop entries: {deb}: {len(entries)} launchers checked")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
