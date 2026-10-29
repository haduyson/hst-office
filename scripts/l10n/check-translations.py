# SPDX-License-Identifier: AGPL-3.0-only
"""Validate Vietnamese translations (JSONL rows with msgid/msgstr) before merging.

Usage: python3 scripts/l10n/check-translations.py <file.jsonl|dir> [...] [--strict]

Errors (always fail): empty msgstr, changed placeholders (%PRODUCTNAME, %FOO,
$(ARG1), %1, %s/%d, {name}, XML tags, \\n count), unescaped double quotes.
Warnings (fail only with --strict): accelerator (~ or _ mnemonic) count
mismatch, msgstr identical to a multi-word English msgid, whitespace or
ellipsis/colon mismatch.
"""
import json
import os
import re
import sys

PLACEHOLDER = re.compile(r"%PRODUCTNAME|%[A-Z][A-Z0-9_]+%?|\$\([A-Z0-9_]+\)|%\d+|%[sdiu]|\{[A-Za-z0-9_]+\}|"
                         r"</?(?!(?:None|All|Default|Unknown)>)[A-Za-z][A-Za-z0-9:_-]*(?:\s[^>]*)?/?>|\\n|\\t|\$[A-Z][A-Z0-9_]+\$?|#[0-9]")
ACCEL = re.compile(r"(?<![~_])[~_](?=[^\s~_])")


def tokens(text):
    return sorted(PLACEHOLDER.findall(text))


def accelerators(text):
    return len(ACCEL.findall(re.sub(r"%[A-Z_]+|\$\([A-Z0-9_]+\)", "", text)))


def check_row(row):
    errors, warnings = [], []
    # Plural entries: the single vi form (nplurals=1) must match the plural source.
    src, dst = row.get("msgid_plural") or row.get("msgid", ""), row.get("msgstr", "")
    if not dst.strip():
        # A whitespace-only label (e.g. msgid " ") is translated by itself.
        return ([] if (not src.strip() and dst == src) else ["empty msgstr"]), []
    if tokens(src) != tokens(dst):
        errors.append(f"placeholders {tokens(src)} != {tokens(dst)}")
    if accelerators(src) != accelerators(dst) and accelerators(src) <= 1:
        warnings.append(f"accelerator count {accelerators(src)} != {accelerators(dst)}")
    if re.search(r'(?<!\\)"', dst):
        errors.append("unescaped double quote")
    if dst == src and len(src.split()) > 1:
        warnings.append("identical to English")
    if src.strip() != src and dst.strip() == dst:
        warnings.append("surrounding whitespace dropped")
    for mark in ("...", "…", ":"):
        if src.rstrip().endswith(mark) != dst.rstrip().endswith(mark):
            warnings.append(f"ending '{mark}' differs")
    return errors, warnings


def rows_from(path):
    files = [path] if os.path.isfile(path) else sorted(
        os.path.join(path, f) for f in os.listdir(path) if f.endswith(".jsonl"))
    for name in files:
        with open(name, encoding="utf-8") as handle:
            for number, line in enumerate(handle, 1):
                if line.strip():
                    yield name, number, json.loads(line)


def main(argv):
    strict = "--strict" in argv
    paths = [a for a in argv if a != "--strict"]
    if not paths:
        raise SystemExit(__doc__)
    n_rows = n_err = n_warn = 0
    for path in paths:
        for name, number, row in rows_from(path):
            n_rows += 1
            errors, warnings = check_row(row)
            n_err += bool(errors)
            n_warn += bool(warnings)
            for message in errors + (warnings if strict else []):
                print(f"{name}:{number}: {message} | {row.get('msgid', '')[:60]!r}")
    print(f"checked {n_rows} rows: {n_err} with errors, {n_warn} with warnings")
    return 1 if n_err or (strict and n_warn) else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
