# SPDX-License-Identifier: AGPL-3.0-only
"""Report terminology inconsistencies in translated JSONL files.

Usage: python3 scripts/l10n/term-report.py work/l10n/done [--json out.json]

For every curated term in data/l10n/vi-glossary.json "corrections", list rows
whose English msgid contains the term as a whole word but whose msgstr does not
contain the approved Vietnamese rendering (case-insensitive, accelerators
ignored). Also flags rows that use known wrong renderings from the old
auto-built glossary. The report feeds a human/agent review; it does not edit.
"""
import argparse
import json
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
WRONG = {"Redo": "Đỏ", "Copy": "Sao ", "Good": "Vàng", "Pivot Table": "Bộ lọc", "Index": "Số mũ",
         "Plain Text": "Nhập thô", "Insert Table": "Chèn tập tin"}


def plain(text):
    return re.sub(r"[~_]", "", text).lower()


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("done_dir")
    parser.add_argument("--json")
    args = parser.parse_args()
    with open(os.path.join(ROOT, "data/l10n/vi-glossary.json"), encoding="utf-8") as handle:
        corrections = json.load(handle)["corrections"]
    findings = []
    for name in sorted(f for f in os.listdir(args.done_dir) if f.endswith(".jsonl")):
        with open(os.path.join(args.done_dir, name), encoding="utf-8") as handle:
            for number, line in enumerate(handle, 1):
                row = json.loads(line)
                src, dst = plain(row["msgid"]), plain(row["msgstr"])
                for term, approved in corrections.items():
                    if not re.search(r"(?<![a-z])" + re.escape(term.lower()) + r"(?![a-z])", src):
                        continue
                    wrong = WRONG.get(term)
                    if approved.lower() not in dst or (wrong and wrong.lower() in dst):
                        findings.append({"file": name, "line": number, "term": term, "approved": approved,
                                         "msgid": row["msgid"], "msgstr": row["msgstr"]})
    by_term = {}
    for item in findings:
        by_term[item["term"]] = by_term.get(item["term"], 0) + 1
    print(json.dumps({"findings": len(findings), "by_term": by_term}, ensure_ascii=False, indent=1))
    if args.json:
        with open(args.json, "w", encoding="utf-8") as handle:
            json.dump(findings, handle, ensure_ascii=False, indent=1)
    return 0


if __name__ == "__main__":
    sys.exit(main())
