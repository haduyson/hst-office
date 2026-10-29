# SPDX-License-Identifier: AGPL-3.0-only
"""Minimal gettext .po reader/writer helpers for the LibreOffice translations tree.

LibreOffice UI .po files key entries by msgctxt + msgid and carry "#." extracted
comments describing the context. A few entries are plural (msgid_plural +
msgstr[N]); Vietnamese has nplurals=1, so msgstr[0] is their only translation. Strings are kept in
their escaped .po form (e.g. "\\n", '\\"') so they round-trip byte-exactly.
"""
import re

_STRING = re.compile(r'"((?:[^"\\]|\\.)*)"')
_FIELD = ("msgctxt ", "msgid ", "msgid_plural ", "msgstr ", "msgstr[0] ")


def _unquote(lines):
    return "".join(m.group(1) for line in lines for m in [_STRING.search(line)] if m)


def parse_block(block):
    """Return {msgctxt, msgid, msgstr, comments} for one blank-line separated block, or None."""
    comments, field, values = [], None, {"msgctxt": [], "msgid": [], "msgstr": []}
    for line in block.strip("\n").split("\n"):
        if line.startswith("#."):
            comments.append(line[2:].strip())
        elif line.startswith(_FIELD):
            field = line.split(" ", 1)[0].replace("[0]", "")
            values.setdefault(field, []).append(line)
        elif line.startswith('"') and field:
            values[field].append(line)
    if not values["msgid"]:
        return None
    return {"msgctxt": _unquote(values["msgctxt"]), "msgid": _unquote(values["msgid"]),
            "msgstr": _unquote(values["msgstr"]), "comments": " ".join(comments)}


def read_blocks(path):
    with open(path, encoding="utf-8") as handle:
        return handle.read().split("\n\n")


def parse_po(path):
    """Yield parsed entries of a .po file."""
    for block in read_blocks(path):
        entry = parse_block(block)
        if entry:
            yield entry


def fill_po(path, translations, overwrite=False):
    """Set msgstr for (msgctxt, msgid) keys in `translations` (escaped text); return count.

    Only empty msgstr values are filled unless `overwrite` is True, so upstream
    translations are never replaced by accident.
    """
    blocks = read_blocks(path)
    filled = 0
    for index, block in enumerate(blocks):
        entry = parse_block(block)
        if not entry:
            continue
        key = (entry["msgctxt"], entry["msgid"])
        if key not in translations or (entry["msgstr"] and not overwrite):
            continue
        tail = "\n" if block.endswith("\n") else ""
        if "\nmsgid_plural " in block:
            # vi has nplurals=1: msgstr[0] is the only form, so drop the
            # template's extra empty msgstr[1..] that msgfmt would reject.
            head = re.split(r"\nmsgstr\[0\] ", block, maxsplit=1)[0]
            blocks[index] = head + '\nmsgstr[0] "' + translations[key] + '"' + tail
        else:
            head = re.split(r"\nmsgstr ", block, maxsplit=1)[0]
            blocks[index] = head + '\nmsgstr "' + translations[key] + '"' + tail
        filled += 1
    plural = any("\nmsgid_plural " in block for block in blocks)
    if filled and plural and "Plural-Forms:" not in blocks[0]:
        # Untranslated upstream templates ship without Plural-Forms; msgfmt then
        # rejects msgstr[0]. Declare the single Vietnamese form.
        blocks[0] = blocks[0].rstrip("\n") + '\n"Plural-Forms: nplurals=1; plural=0;\\n"' + (
            "\n" if blocks[0].endswith("\n") else "")
    with open(path, "w", encoding="utf-8") as handle:
        handle.write("\n\n".join(blocks))
    return filled
