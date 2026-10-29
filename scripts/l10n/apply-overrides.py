#!/usr/bin/env python3
# SPDX-License-Identifier: AGPL-3.0-only
"""Apply l10n/vi-overrides.jsonl to the Vietnamese .po files of the LibreOffice tree.

Each row {file, msgctxt, msgid, msgstr, reason} replaces the msgstr of exactly that
(file, msgctxt, msgid) entry, overwriting an existing translation. Values use the
escaped .po form (\\n, \\") like the rows merged by merge-vi.py. Run it after merge-vi.py
so the overrides win. Idempotent; every changed file must pass `msgfmt --check`; a key that
no longer exists in the tree is an error (the upstream string changed).

  scripts/l10n/apply-overrides.py [--tree DIR] [--overrides FILE]
"""
import argparse
import collections
import json
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, HERE)
from po_io import fill_po, parse_po  # noqa: E402

REQUIRED = ("file", "msgctxt", "msgid", "msgstr", "reason")


def load_rows(path):
    rows = []
    with open(path, encoding="utf-8") as handle:
        for number, line in enumerate(handle, 1):
            if not line.strip():
                continue
            row = json.loads(line)
            missing = [key for key in REQUIRED if key not in row]
            if missing:
                raise ValueError(f"{path}:{number}: missing {', '.join(missing)}")
            rows.append(row)
    return rows


def apply(tree, overrides):
    root = os.path.join(tree, "translations", "source", "vi")
    by_file = collections.defaultdict(dict)
    for row in load_rows(overrides):
        by_file[row["file"]][(row["msgctxt"], row["msgid"])] = row["msgstr"]
    changed = errors = 0
    for rel, translations in sorted(by_file.items()):
        path = os.path.join(root, rel)
        if not os.path.isfile(path):
            print(f"error: {rel}: no such file")
            errors += 1
            continue
        existing = {(e["msgctxt"], e["msgid"]) for e in parse_po(path)}
        absent = [key for key in translations if key not in existing]
        for ctx, msgid in absent:
            print(f"error: {rel}: no entry {ctx!r} / {msgid[:60]!r}")
        errors += len(absent)
        with open(path, encoding="utf-8") as handle:
            before = handle.read()
        fill_po(path, {k: v for k, v in translations.items() if k in existing}, overwrite=True)
        with open(path, encoding="utf-8") as handle:
            if handle.read() == before:
                continue
        changed += 1
        result = subprocess.run(["msgfmt", "--check", "-o", os.devnull, path],
                                capture_output=True, text=True)
        if result.returncode:
            print(f"error: msgfmt rejects {rel}:\n{result.stderr}")
            with open(path, "w", encoding="utf-8") as handle:
                handle.write(before)
            errors += 1
    print(f"overrides: {sum(map(len, by_file.values()))} rows, {changed} files changed, {errors} errors")
    return 1 if errors else 0


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--tree", default=os.path.join(ROOT, "upstream", "libreoffice"))
    parser.add_argument("--overrides", default=os.path.join(ROOT, "l10n", "vi-overrides.jsonl"))
    args = parser.parse_args()
    return apply(args.tree, args.overrides)


if __name__ == "__main__":
    sys.exit(main())
