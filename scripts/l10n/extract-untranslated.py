# SPDX-License-Identifier: AGPL-3.0-only
"""Extract untranslated Vietnamese UI strings from the LibreOffice translations tree.

Usage: python3 scripts/l10n/extract-untranslated.py [--tree upstream/libreoffice] [--out build/l10n/todo]

Writes one JSONL work file per upstream module (help excluded) with entries
{"file", "msgctxt", "msgid", "comments"} whose vi msgstr is empty or fuzzy
(fuzzy rows add "fuzzy_hint" with the outdated upstream text), plus
summary.json with counts. Translators fill "msgstr" and the results are kept in
l10n/vi/ (see scripts/l10n/merge-vi.py).
"""
import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from po_io import parse_po  # noqa: E402

SKIP_MODULES = {"helpcontent2"}


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--tree", default="upstream/libreoffice")
    parser.add_argument("--out", default="work/l10n/todo")
    args = parser.parse_args()
    root = os.path.join(args.tree, "translations", "source", "vi")
    os.makedirs(args.out, exist_ok=True)
    summary = {}
    for module in sorted(os.listdir(root)):
        if module in SKIP_MODULES or not os.path.isdir(os.path.join(root, module)):
            continue
        rows = []
        for dirpath, _, files in os.walk(os.path.join(root, module)):
            for name in sorted(files):
                if not name.endswith(".po"):
                    continue
                path = os.path.join(dirpath, name)
                rel = os.path.relpath(path, root)
                for entry in parse_po(path):
                    if entry["msgid"] and (not entry["msgstr"] or entry["fuzzy"]):
                        row = {"file": rel, "msgctxt": entry["msgctxt"], "msgid": entry["msgid"],
                               "comments": entry["comments"]}
                        if entry["msgid_plural"]:  # vi has one form: translate the plural source
                            row["msgid_plural"] = entry["msgid_plural"]
                        if entry["fuzzy"]:  # outdated upstream text: a hint, not a translation
                            row["fuzzy_hint"] = entry["msgstr"]
                        rows.append(row)
        if rows:
            with open(os.path.join(args.out, f"{module}.jsonl"), "w", encoding="utf-8") as handle:
                for row in rows:
                    handle.write(json.dumps(row, ensure_ascii=False) + "\n")
            summary[module] = len(rows)
    with open(os.path.join(args.out, "summary.json"), "w", encoding="utf-8") as handle:
        json.dump({"total": sum(summary.values()), "modules": summary}, handle, indent=2)
    print(f"untranslated UI strings: {sum(summary.values())} in {len(summary)} modules")


if __name__ == "__main__":
    main()
