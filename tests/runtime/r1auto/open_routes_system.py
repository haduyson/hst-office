# SPDX-License-Identifier: AGPL-3.0-only
"""What W16 reads from and resets in Windows: the default profile of the installed office, its recovery list after a
forced stop, and Explorer's registration of each file type."""
import os
from pathlib import Path
import re
import shutil


def scrub_recovery(profile):
    """After a forced stop: drop the recovery list, so the next start is not a recovery start (that dialog would
    hide every later route's own result)."""
    xcu = Path(profile) / "user" / "registrymodifications.xcu"
    if xcu.is_file():
        lines = xcu.read_text(encoding="utf-8").splitlines(keepends=True)
        xcu.write_text("".join(l for l in lines if "org.openoffice.Office.Recovery" not in l), encoding="utf-8")
    shutil.rmtree(Path(profile) / "user" / "backup", ignore_errors=True)


def default_profile(install):
    """bootstrap.ini UserInstallation of the installed office ($SYSUSERCONFIG = %APPDATA%)."""
    import urllib.parse
    text = (Path(install) / "program" / "bootstrap.ini").read_text(encoding="utf-8", errors="replace")
    raw = re.search(r"^UserInstallation=(.*)$", text, re.M).group(1).strip()
    raw = raw.replace("$SYSUSERCONFIG", Path(os.environ["APPDATA"]).as_uri().removeprefix("file:///"))
    return Path(urllib.parse.unquote(raw.removeprefix("file:///")))


def registration():
    """What Explorer reads for each type: the default ProgID, Open-with ProgIDs, the user's choice and every verb."""
    import winreg
    def value(hive, key, name=""):
        try:
            with winreg.OpenKey(hive, key) as handle:
                return winreg.QueryValueEx(handle, name)[0]
        except OSError:
            return None
    def names(hive, key, values=False):
        try:
            with winreg.OpenKey(hive, key) as handle:
                enum = winreg.EnumValue if values else winreg.EnumKey
                found, i = [], 0
                while True:
                    try:
                        item = enum(handle, i)
                    except OSError:
                        return found
                    found.append(item[0] if values else item)
                    i += 1
        except OSError:
            return []
    out = {}
    for ext in ("xlsx", "ods", "docx", "odt", "pptx", "odp"):
        progids = names(winreg.HKEY_CLASSES_ROOT, "." + ext + r"\OpenWithProgids", values=True)
        default = value(winreg.HKEY_CLASSES_ROOT, "." + ext)
        verbs = {}
        for progid in {p for p in progids + [default] if p and p.lower().startswith("hst")}:
            for verb in names(winreg.HKEY_CLASSES_ROOT, progid + r"\shell"):
                verbs[progid + " " + verb] = value(winreg.HKEY_CLASSES_ROOT, progid + r"\shell\%s\command" % verb)
        out[ext] = dict(default=default, open_with=progids, verbs=verbs, user_choice=value(
            winreg.HKEY_CURRENT_USER, r"Software\Microsoft\Windows\CurrentVersion\Explorer\FileExts\.%s\UserChoice"
            % ext, "ProgId"))
    return out
