#!/usr/bin/env python3
# SPDX-License-Identifier: AGPL-3.0-only
"""Fail when a launcher (.desktop) entry in the HST Office .deb names an upstream product.

  check-desktop-entries.py <package.deb> [...]
The fields a desktop shell shows or searches (Name, GenericName, Comment, Keywords,
X-GNOME-FullName), in every locale (Key[xx]=), must not contain OpenOffice, LibreOffice or
The Document Foundation, nor a third-party product (desktop_keywords.THIRD_PARTY). Exec and MimeType are not read.
The window class a launcher claims (StartupWMClass) must be its own launcher id: a launcher
usr/share/applications/<id>.desktop links to it and StartupWMClass=<id> (vn.hasontech.hstoffice-writer),
the class HST's windows carry. A class or Icon of LibreOffice's (libreoffice-*, openoffice*)
would group HST windows with an installed LibreOffice's, and LibreOffice's windows with HST's.
The menu launchers of the three apps (vn.hasontech.hstoffice-writer, -calc, -impress) are named HST Writer,
HST Sheets and HST Slides, show their own HST icon (Icon=<launcher id>) and are listed under Office.
HST Base is offered nowhere: its launcher (vn.hasontech.hstoffice-base) is NoDisplay=true but still handles
.odb files, and the HST Office launcher has no Base action.
Exit 0 = clean, 1 = a hit or no launcher in a package, 2 = bad arguments. Needs dpkg-deb.
"""
import io
import os
import re
import subprocess
import sys
import tarfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))  # sibling module, also under python3 -I
from desktop_keywords import THIRD_PARTY  # noqa: E402

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


# launcher id -> the name the app menu shows
APP_NAMES = {"vn.hasontech.hstoffice-writer": "HST Writer", "vn.hasontech.hstoffice-calc": "HST Sheets",
             "vn.hasontech.hstoffice-impress": "HST Slides"}


def app_hits(text, launcher_id):
    """Problems of an app launcher of the menu (only for the APP_NAMES ids): its name, icon, Office category and
    visibility, read from the [Desktop Entry] group."""
    if launcher_id not in APP_NAMES:
        return []
    entry = main_group(text)
    found = []
    expected = {"Name": APP_NAMES[launcher_id], "Icon": launcher_id, "Type": "Application"}
    for key, value in expected.items():
        if entry.get(key) != value:
            found.append(f"{key}={entry.get(key)} (expected {value})")
    if "Office" not in entry.get("Categories", "").split(";"):
        found.append(f"Categories={entry.get('Categories')} (expected Office)")
    if entry.get("NoDisplay", "").lower() == "true" or entry.get("Hidden", "").lower() == "true":
        found.append("hidden from the app menu")
    return found


BASE_ID, START_ID = "vn.hasontech.hstoffice-base", "vn.hasontech.hstoffice-startcenter"
ODB = "application/vnd.oasis.opendocument.base"


def main_group(text):
    """{key: value} of the [Desktop Entry] group (first value of a key)."""
    entry, group = {}, None
    for line in text.splitlines():
        line = line.strip()
        if line.startswith("[") and line.endswith("]"):
            group = line[1:-1]
        elif group == "Desktop Entry" and "=" in line:
            key, _, value = line.partition("=")
            entry.setdefault(key.strip(), value.strip())
    return entry


def base_hits(text, launcher_id):
    """HST Base shown somewhere: its own launcher in the app menus (or no longer opening .odb), or a Base action of
    the HST Office launcher."""
    entry = main_group(text)
    if launcher_id == BASE_ID:
        found = [] if entry.get("NoDisplay", "").lower() == "true" else ["HST Base is listed in the app menus"]
        if ODB not in entry.get("MimeType", "").split(";"):
            found.append(f"HST Base no longer opens .odb files (MimeType={entry.get('MimeType')})")
        return found
    if launcher_id == START_ID and ("Base" in entry.get("Actions", "").split(";") or "[Desktop Action Base]" in text):
        return ["the HST Office launcher offers a Base action"]
    return []


def hits(text):
    """Visible/searchable launcher lines that name an upstream product."""
    found = []
    for line in text.splitlines():
        match = FIELDS.match(line.strip())
        if match and (NAMES.search(match.group(3)) or THIRD_PARTY.search(match.group(3))):
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
            for line in hits(text) + identity_hits(text, ids.get(path)) + app_hits(text, ids.get(path)) \
                    + base_hits(text, ids.get(path)):
                print(f"FAIL {path}: {line}")
                failures += 1
        apps = sorted(APP_NAMES[i] for i in ids.values() if i in APP_NAMES)
        print(f"desktop entries: {deb}: {len(entries)} launchers checked" + (f"; apps: {', '.join(apps)}" if apps else ""))
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
