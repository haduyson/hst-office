# SPDX-License-Identifier: AGPL-3.0-only
"""Linux default apps: `xdg-mime default vn.hasontech.hstoffice-<app>.desktop <types>` for the office document types
the HST launchers declare, then a query to prove it was recorded (xdg-mime exits 0 when it cannot write)."""
import configparser
import os
import shutil
import subprocess

DESKTOP_IDS = {"writer": "vn.hasontech.hstoffice-writer.desktop", "calc": "vn.hasontech.hstoffice-calc.desktop",
               "impress": "vn.hasontech.hstoffice-impress.desktop"}
# The office types the prompt is about: ODF, OOXML and the older binary formats (.doc, .xls, .ppt and templates).
_OFFICE_PREFIXES = ("application/vnd.oasis.opendocument.", "application/vnd.openxmlformats-officedocument.",
                    "application/msword", "application/vnd.ms-word", "application/vnd.ms-excel",
                    "application/vnd.ms-powerpoint")
FALLBACK_MIME = {
    "writer": ("application/vnd.oasis.opendocument.text", "application/msword",
               "application/vnd.openxmlformats-officedocument.wordprocessingml.document"),
    "calc": ("application/vnd.oasis.opendocument.spreadsheet", "application/vnd.ms-excel",
             "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"),
    "impress": ("application/vnd.oasis.opendocument.presentation", "application/vnd.ms-powerpoint",
                "application/vnd.openxmlformats-officedocument.presentationml.presentation"),
}
# One type per app decides "registered": the formats users open every day.
PROBE_MIME = ("application/vnd.openxmlformats-officedocument.wordprocessingml.document",
              "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
              "application/vnd.openxmlformats-officedocument.presentationml.presentation")
TIMEOUT = 10


def office_types(declared):
    """The office document types among a launcher's MimeType list, in their order, without duplicates (pure)."""
    seen = []
    for item in declared:
        item = item.strip()
        if item and item.startswith(_OFFICE_PREFIXES) and item not in seen:
            seen.append(item)
    return seen


def linux_commands(declared_by_module):
    """xdg-mime argv per module (pure). `declared_by_module`: {module: [MimeType entries of its launcher]}."""
    commands = []
    for module, desktop in DESKTOP_IDS.items():
        types = office_types(declared_by_module.get(module) or FALLBACK_MIME[module])
        if types:
            commands.append(["xdg-mime", "default", desktop] + types)
    return commands


def _data_dirs():
    home = os.environ.get("XDG_DATA_HOME") or os.path.join(os.path.expanduser("~"), ".local", "share")
    return [home] + (os.environ.get("XDG_DATA_DIRS") or "/usr/local/share:/usr/share").split(":")


def declared_types(desktop):
    """MimeType entries of an installed launcher, [] when it is not found."""
    for directory in _data_dirs():
        path = os.path.join(directory, "applications", desktop)
        if os.path.isfile(path):
            parser = configparser.RawConfigParser(interpolation=None, strict=False)
            parser.read(path, encoding="utf-8")
            return parser.get("Desktop Entry", "MimeType", fallback="").split(";")
    return []


def _run(argv):
    return subprocess.run(argv, capture_output=True, text=True, timeout=TIMEOUT, check=False)


def linux_make_default():
    if shutil.which("xdg-mime") is None:
        raise RuntimeError("không tìm thấy xdg-mime")
    for argv in linux_commands({m: declared_types(d) for m, d in DESKTOP_IDS.items()}):
        done = _run(argv)
        if done.returncode != 0:
            raise RuntimeError((done.stderr or done.stdout or "xdg-mime %d" % done.returncode).strip())
    if not linux_is_registered():  # xdg-mime exits 0 without writing when $HOME/.config cannot be created
        raise RuntimeError("không ghi được lựa chọn vào %s" % os.path.join(
            os.environ.get("XDG_CONFIG_HOME") or os.path.join(os.path.expanduser("~"), ".config"), "mimeapps.list"))
    return True, ""


def linux_is_registered():
    if shutil.which("xdg-mime") is None:
        return False
    return all(_run(["xdg-mime", "query", "default", t]).stdout.strip().startswith("vn.hasontech.hstoffice-")
               for t in PROBE_MIME)
