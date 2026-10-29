# SPDX-License-Identifier: AGPL-3.0-only
"""Apply reviewer corrections to translated JSONL files.

Usage: python3 scripts/l10n/apply-review.py work/l10n/done FIXES.jsonl [...]

Each fix row {file, line, msgid, old, new, reason} is applied only when the
target row still has that msgid and that old msgstr, so stale or misplaced
fixes are reported instead of silently overwriting another string.
"""
import json
import os
import sys


def main(argv):
    if len(argv) < 2:
        raise SystemExit(__doc__)
    done_dir, fix_files = argv[0], argv[1:]
    fixes = [json.loads(line) for path in fix_files for line in open(path, encoding="utf-8") if line.strip()]
    by_file = {}
    for fix in fixes:
        by_file.setdefault(fix["file"], []).append(fix)
    applied = skipped = 0
    for name, items in sorted(by_file.items()):
        path = os.path.join(done_dir, name)
        rows = [json.loads(line) for line in open(path, encoding="utf-8")]
        for fix in items:
            row = rows[fix["line"] - 1] if 0 < fix["line"] <= len(rows) else None
            if row and row["msgid"] == fix["msgid"] and row["msgstr"] == fix["old"]:
                row["msgstr"] = fix["new"]
                applied += 1
            else:
                skipped += 1
                print(f"skip {name}:{fix['line']} (row changed or msgid mismatch)")
        with open(path, "w", encoding="utf-8") as handle:
            for row in rows:
                handle.write(json.dumps(row, ensure_ascii=False) + "\n")
    print(f"applied {applied} fixes, skipped {skipped}")
    return 1 if skipped else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
