# SPDX-License-Identifier: AGPL-3.0-only
"""macOS configuration profiles (managed preferences) of HST Office's domain vn.hasontech.hstoffice.

Administrators push them with an MDM or a .mobileconfig; macOS writes /Library/Managed Preferences/<domain>.plist
(computer-wide) and /Library/Managed Preferences/<user>/<domain>.plist (per user). Everything there is forced. Read
for the update check ("HSTUpdate", update_config) and "Phiên bản trước" ("PreviousVersions", version_config).
"""
import os
import plistlib

MACOS_DOMAIN = "vn.hasontech.hstoffice"
MANAGED_DIR = "/Library/Managed Preferences"


def section(name, user=None, base=MANAGED_DIR, log=print):
    """The dictionary `name` of the profiles: the computer-wide one, with the per-user profile's keys over it."""
    if not os.path.isdir(base):
        return {}
    if user is None:
        try:
            import pwd
            user = pwd.getpwuid(os.getuid()).pw_name
        except Exception:  # noqa: BLE001 - no user name: only the computer-wide profile
            user = None
    out = {}
    paths = [os.path.join(base, MACOS_DOMAIN + ".plist")]
    if user:
        paths.insert(0, os.path.join(base, user, MACOS_DOMAIN + ".plist"))
    for path in reversed(paths):  # computer-wide first, the per-user profile overrides it
        try:
            with open(path, "rb") as fh:
                doc = plistlib.load(fh)
        except FileNotFoundError:
            continue
        except Exception as exc:  # noqa: BLE001 - a broken profile must not break the office
            log("ignoring %s: %s" % (path, exc))
            continue
        found = doc.get(name) if isinstance(doc, dict) else None
        if isinstance(found, dict):
            out.update(found)
    return out
