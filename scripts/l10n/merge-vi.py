# SPDX-License-Identifier: AGPL-3.0-only
"""Store HST Vietnamese translations and merge them into the LibreOffice tree.

Usage:
  python3 scripts/l10n/merge-vi.py --collect work/l10n/done   # validate, then save to l10n/vi/
  python3 scripts/l10n/merge-vi.py --apply [--tree upstream/libreoffice]

l10n/vi/<module>.jsonl (committed) is the HST overlay: rows {file, msgctxt,
msgid, msgstr} for strings upstream leaves untranslated. --apply fills only
empty msgstr in translations/source/vi/**/*.po (upstream translations are never
replaced) and runs `msgfmt --check` on every changed file.
"""
import argparse
import collections
import importlib.util
import json
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
OVERLAY = os.path.join(ROOT, "l10n", "vi")
sys.path.insert(0, HERE)
from po_io import fill_po  # noqa: E402

_spec = importlib.util.spec_from_file_location("check", os.path.join(HERE, "check-translations.py"))
check = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(check)


def collect(done_dir):
    failures = 0
    os.makedirs(OVERLAY, exist_ok=True)
    for name in sorted(f for f in os.listdir(done_dir) if f.endswith(".jsonl")):
        rows = [json.loads(line) for line in open(os.path.join(done_dir, name), encoding="utf-8") if line.strip()]
        bad = [r for r in rows if check.check_row(r)[0]]
        if bad:
            failures += len(bad)
            print(f"{name}: {len(bad)} rows fail validation; not collected")
            continue
        with open(os.path.join(OVERLAY, name), "w", encoding="utf-8") as handle:
            for row in rows:
                keep = {k: row[k] for k in ("file", "msgctxt", "msgid", "msgid_plural", "msgstr") if k in row}
                handle.write(json.dumps(keep, ensure_ascii=False) + "\n")
        print(f"{name}: {len(rows)} rows collected")
    return 1 if failures else 0


def apply(tree):
    root = os.path.join(tree, "translations", "source", "vi")
    by_file = collections.defaultdict(dict)
    for name in sorted(os.listdir(OVERLAY)):
        for line in open(os.path.join(OVERLAY, name), encoding="utf-8"):
            if line.strip():
                row = json.loads(line)
                by_file[row["file"]][(row["msgctxt"], row["msgid"])] = row["msgstr"]
    total = 0
    for rel, translations in sorted(by_file.items()):
        path = os.path.join(root, rel)
        count = fill_po(path, translations)
        total += count
        if count:
            result = subprocess.run(["msgfmt", "--check", "-o", os.devnull, path], capture_output=True, text=True)
            if result.returncode:
                print(f"msgfmt rejects {rel}:\n{result.stderr}")
                return 1
    print(f"filled {total} empty msgstr in {len(by_file)} files")
    return 0


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--collect", metavar="DONE_DIR")
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--tree", default=os.path.join(ROOT, "upstream", "libreoffice"))
    args = parser.parse_args()
    if args.collect:
        return collect(args.collect)
    if args.apply:
        return apply(args.tree)
    parser.error("use --collect or --apply")
    return 2


if __name__ == "__main__":
    sys.exit(main())
