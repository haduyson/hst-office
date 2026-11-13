# SPDX-License-Identifier: AGPL-3.0-only
"""Read the per-file sections of a patch in patches/libreoffice (added lines, lines after the patch)."""
import os
import re

from _paths import ROOT


def sections(name):
    result, current = {}, None
    with open(os.path.join(ROOT, "patches", "libreoffice", name), encoding="utf-8") as handle:
        for line in handle.read().splitlines():
            match = re.match(r"^\+\+\+ b/(\S+)", line)
            if match:
                current = result.setdefault(match.group(1), [])
            elif current is not None and not line.startswith("--- "):
                current.append(line)
    return result


def added(name, path):
    return "\n".join(line[1:] for line in sections(name)[path] if line.startswith("+"))


def removed(name, path):
    return "\n".join(line[1:] for line in sections(name)[path] if line.startswith("-"))


def po_entries(text):
    """{msgctxt: (msgid, msgstr)} of the single-line entries in a .po text."""
    return {m.group(1): (m.group(2), m.group(3)) for m in
            re.finditer(r'msgctxt "([^"]*)"\nmsgid "([^"]*)"\nmsgstr "([^"]*)"', text)}


def after(name, path):
    """The hunks of one file as they read after the patch (context and added lines)."""
    return "\n".join(line[1:] for line in sections(name)[path] if line[:1] in (" ", "+"))
