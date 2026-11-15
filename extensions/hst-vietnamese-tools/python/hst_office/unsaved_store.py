# SPDX-License-Identifier: AGPL-3.0-only
"""Tài liệu chưa lưu: the documents the user closed without saving, as the office keeps them (pure file logic).

When a document with a recovery copy is closed without saving, the office (framework hstunsavedstore.cxx) moves that
copy into <profile>/user/hst-unsaved:
  <yyyymmdd-hhmmss>-<id>.<ext>       the document as of its last recovery copy (ODF)
  <yyyymmdd-hhmmss>-<id>.<ext>.txt   "HST-UNSAVED 1", then key<TAB>value lines: title, url (original file, empty when
                                     never saved), module, saved and closed (seconds since the epoch)
and prunes the folder to 7 days and 500 MB (oldest first) at every close and start. This module lists what is still
kept (expired ones are hidden even before the office prunes them) and deletes on request. Nothing leaves the computer.
"""
import os
import time
from collections import namedtuple

HEADER = "HST-UNSAVED 1"
KEEP_SECONDS = 7 * 24 * 3600
FOLDER = "hst-unsaved"

Kept = namedtuple("Kept", "path info title url module saved closed size")


def store_dir(user_dir):
    return os.path.join(user_dir, FOLDER)


def parse_info(text):
    """{key: value} of a description file; {} when it is not one (pure)."""
    lines = (text or "").splitlines()
    if not lines or lines[0].strip() != HEADER:
        return {}
    fields = {}
    for line in lines[1:]:
        key, sep, value = line.partition("\t")
        if sep:
            fields[key.strip()] = value.strip()
    return fields


def _number(value, default):
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _read(path):
    try:
        with open(path, encoding="utf-8") as handle:
            return handle.read(64 * 1024)
    except (OSError, UnicodeDecodeError):
        return ""


def list_kept(folder, now=None):
    """Kept documents of the folder, newest first, without the expired ones. A copy without its description (the office
    stopped between the two files) is listed with the copy's own time."""
    now = time.time() if now is None else now
    try:
        names = os.listdir(folder)
    except OSError:
        return []
    out = []
    for name in names:
        path = os.path.join(folder, name)
        if name.startswith(".") or name.endswith(".txt") or not os.path.isfile(path):
            continue
        stat = os.stat(path)
        info = parse_info(_read(path + ".txt"))
        saved = _number(info.get("saved"), stat.st_mtime)
        closed = _number(info.get("closed"), stat.st_mtime)
        if now - closed > KEEP_SECONDS:
            continue
        out.append(Kept(path, path + ".txt", info.get("title", ""), info.get("url", ""), info.get("module", ""),
                        saved, closed, stat.st_size))
    out.sort(key=lambda kept: kept.closed, reverse=True)
    return out


def delete(kept):
    """Remove one kept document; True when its copy is gone."""
    for path in (kept.path, kept.info):
        try:
            os.remove(path)
        except FileNotFoundError:
            pass
        except OSError:
            if path == kept.path:
                return False
    return True


def delete_all(folder):
    """Remove every kept document; returns how many were removed."""
    return sum(1 for kept in list_kept(folder, now=0) if delete(kept))


def file_path(url):
    """Local path of a file: URL, "" for anything else (pure)."""
    if not url.startswith("file://"):
        return ""
    from urllib.parse import unquote, urlparse
    parsed = urlparse(url)
    path = unquote(parsed.path)
    if os.name == "nt" and len(path) > 2 and path[0] == "/" and path[2] == ":":
        path = path[1:].replace("/", "\\")
    elif parsed.netloc:
        path = "//" + parsed.netloc + path
    return path
