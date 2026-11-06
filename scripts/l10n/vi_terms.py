# SPDX-License-Identifier: AGPL-3.0-only
"""Glossary-wide term replacements in the Vietnamese UI translations (File is "tệp tin").

The pairs come from data/l10n/vi-glossary.json "replacements" (owner decisions that apply to
every string, not one key). A match keeps the case of each letter (title case and all caps
stay so) and any access-key marker (_ ~) inside it ("Tệ_p tin" keeps "p"), so the mnemonic
letter does not move. Both sides of a pair must have the same length. Only whole words match:
the old term inside a longer word is left alone. tests/unit/test_vi_terms.py has examples.
"""
import collections
import json
import os
import re
import subprocess

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
GLOSSARY = os.path.join(ROOT, "data", "l10n", "vi-glossary.json")
LETTER = r"A-Za-zÀ-ɏḀ-ỿ"


def load_pairs(path=GLOSSARY):
    with open(path, encoding="utf-8") as handle:
        pairs = json.load(handle).get("replacements", {})
    for old, new in pairs.items():
        if len(old) != len(new) or old != old.lower():
            raise ValueError(f"replacement {old!r} -> {new!r}: lowercase, same length required")
    return pairs


def _pattern(old):
    # Each letter may be followed by one access-key marker; whole words only.
    body = "[_~]?".join(re.escape(c) for c in old)
    # A .po escape such as \n before the word ends the previous word.
    start = r"(?:(?<=\\[nrt])|(?<![" + LETTER + r"_~]))"
    return re.compile(start + r"[_~]?" + body + r"(?![" + LETTER + r"])", re.IGNORECASE)


def _recase(found, new):
    out, letters = [], iter(new)
    for char in found:
        if char in "_~":
            out.append(char)
            continue
        target = next(letters)
        out.append(target.upper() if char.isupper() else target)
    return "".join(out)


_COMPILED = {}


def fix(text, pairs=None):
    """Text with every glossary replacement applied, case and access keys kept."""
    for old, new in (pairs if pairs is not None else load_pairs()).items():
        pattern = _COMPILED.setdefault(old, _pattern(old))
        text = pattern.sub(lambda m: _recase(m.group(0), new), text)
    return text


def normalize_po(path, pairs, keep=frozenset()):
    """Apply fix() to every msgstr line of a .po file in place; lines in `keep` (lines that an
    HST patch adds or uses as context, which must stay byte-identical) are left alone.
    Return (changed, kept) line counts."""
    with open(path, encoding="utf-8") as handle:
        lines = handle.read().split("\n")
    changed = kept = 0
    in_msgstr = False
    start = lines.index("") if "" in lines else 0  # leave the header entry alone
    for index, line in enumerate(lines[start:], start):
        if line.startswith("msgstr"):
            in_msgstr = True
        elif not line.startswith('"'):
            in_msgstr = False
        if not in_msgstr:
            continue
        new = fix(line, pairs)
        if new == line:
            continue
        if line in keep:
            kept += 1
            continue
        lines[index], changed = new, changed + 1
    if changed:
        with open(path, "w", encoding="utf-8") as handle:
            handle.write("\n".join(lines))
    return changed, kept


def patch_lines(patches):
    """{.po path under translations/source/vi: lines an HST patch adds or keeps as context}."""
    keep = collections.defaultdict(set)
    series = os.path.join(patches, "series")
    if not os.path.isfile(series):
        return keep
    with open(series, encoding="utf-8") as handle:
        names = [n.strip() for n in handle if n.strip() and not n.startswith("#")]
    prefix = "+++ b/translations/source/vi/"
    for name in names:
        current = None
        with open(os.path.join(patches, name), encoding="utf-8") as handle:
            for line in handle.read().split("\n"):
                if line.startswith("+++ "):
                    current = line[len(prefix):].split("\t")[0] if line.startswith(prefix) else None
                elif current and line[:1] in ("+", " ") and not line.startswith("--- "):
                    keep[current].add(line[1:])
    return keep


def normalize_terms(tree, patches):
    """Glossary-wide replacements (File is "tệp tin") in every Vietnamese .po, after the overrides."""
    root = os.path.join(tree, "translations", "source", "vi")
    pairs = load_pairs()
    keep = patch_lines(patches)
    files = lines = kept = errors = 0
    for folder, _dirs, names in os.walk(root):
        for name in sorted(names):
            if not name.endswith(".po"):
                continue
            path = os.path.join(folder, name)
            rel = os.path.relpath(path, root)
            with open(path, encoding="utf-8") as handle:
                before = handle.read()
            count, left = normalize_po(path, pairs, frozenset(keep.get(rel, ())))
            if left:
                print(f"warning: {rel}: {left} lines come from an HST patch; fix the patch text instead")
                kept += left
            if not count:
                continue
            result = subprocess.run(["msgfmt", "--check", "-o", os.devnull, path], capture_output=True, text=True)
            if result.returncode:
                print(f"error: msgfmt rejects {rel} after term replacement:\n{result.stderr}")
                with open(path, "w", encoding="utf-8") as handle:
                    handle.write(before)
                errors += 1
                continue
            files, lines = files + 1, lines + count
    print(f"terms: {lines} lines in {files} files replaced, {kept} left to patches, {errors} errors")
    return 1 if errors else 0
