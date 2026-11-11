#!/usr/bin/env python3
# SPDX-License-Identifier: AGPL-3.0-only
"""Compare VBA corpus results of the reference suite and HST Office, check by check.

  vba_compare.py REFERENCE.json HST.json [--md OUT.md] [--json OUT.json]

Each case function returns `key=value` lines (see vba_corpus_kit.py). Kinds: match; mismatch (both ran,
values differ); hst-error (HST raised ERRn where the reference gave a value); reference-error (the other way);
error-differs (both raised, different numbers); missing (a check line only one side produced); call-failed
(the whole function could not be called on one side, e.g. compile error or missing object).
"""
import argparse
import json
from pathlib import Path
import sys


def parse_lines(text):
    """Ordered {key: value} from `key=value` lines; a value keeps any '=' it contains."""
    out = {}
    for line in text.split("\n"):
        if "=" in line:
            key, value = line.split("=", 1)
            out[key] = value
    return out


def load(path):
    report = json.loads(Path(path).read_text(encoding="utf-8-sig"))
    files = {}
    for row in report.get("files", []):
        files[row["file"]] = row
    return report, files


def is_error(value):
    return value.startswith("ERR") and value[3:].isdigit()


def classify(ref, hst):
    if ref is None or hst is None:
        return "missing"
    if ref == hst:
        return "match"
    if is_error(hst) and not is_error(ref):
        return "hst-error"
    if is_error(ref) and not is_error(hst):
        return "reference-error"
    if is_error(ref) and is_error(hst):
        return "error-differs"
    return "mismatch"


def compare(ref_files, hst_files):
    """Rows: dict(file, function, key, reference, hst, kind) for every check, matches included."""
    rows = []
    for name in sorted(set(ref_files) | set(hst_files)):
        ref_row, hst_row = ref_files.get(name, {}), hst_files.get(name, {})
        functions = list(dict.fromkeys(list(ref_row.get("functions", {})) + list(hst_row.get("functions", {}))))
        if not functions:
            rows.append(dict(file=name, function="*", key="*", reference=ref_row.get("status", "absent"),
                             hst=hst_row.get("status", "absent") + (": " + hst_row["error"] if hst_row.get("error") else ""),
                             kind="call-failed"))
        for function in functions:
            ref_call = ref_row.get("functions", {}).get(function)
            hst_call = hst_row.get("functions", {}).get(function)
            ref_ok = bool(ref_call) and ref_call["status"] == "ok"
            hst_ok = bool(hst_call) and hst_call["status"] == "ok"
            if not (ref_ok and hst_ok):
                rows.append(dict(file=name, function=function, key="*",
                                 reference=(ref_call or {}).get("value", "not run") if not ref_ok else "ok",
                                 hst=(hst_call or {}).get("value", "not run") if not hst_ok else "ok", kind="call-failed"))
                continue
            ref_lines, hst_lines = parse_lines(ref_call["value"]), parse_lines(hst_call["value"])
            for key in dict.fromkeys(list(ref_lines) + list(hst_lines)):
                rows.append(dict(file=name, function=function, key=key, reference=ref_lines.get(key),
                                 hst=hst_lines.get(key), kind=classify(ref_lines.get(key), hst_lines.get(key))))
    return rows


def cell(value):
    text = "—" if value is None else str(value)
    return text.replace("|", "\\|").replace("\n", " ")[:160]


def markdown(rows, title="VBA comparison"):
    counts = {}
    for row in rows:
        counts[row["kind"]] = counts.get(row["kind"], 0) + 1
    lines = [f"## {title}", "", "| Kind | Checks |", "|---|---|"]
    lines += [f"| {kind} | {count} |" for kind, count in sorted(counts.items())]
    lines += ["", "| File | Function | Check | Reference | HST | Kind |", "|---|---|---|---|---|---|"]
    for row in rows:
        if row["kind"] != "match":
            lines.append("| " + " | ".join(cell(row[k]) for k in ("file", "function", "key", "reference", "hst", "kind")) + " |")
    return "\n".join(lines) + "\n"


def main(argv):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("reference")
    parser.add_argument("hst")
    parser.add_argument("--md")
    parser.add_argument("--json")
    parser.add_argument("--title", default="VBA comparison")
    args = parser.parse_args(argv[1:])
    rows = compare(load(args.reference)[1], load(args.hst)[1])
    text = markdown(rows, args.title)
    if args.md:
        Path(args.md).write_text(text, encoding="utf-8")
    if args.json:
        Path(args.json).write_text(json.dumps(rows, indent=1, ensure_ascii=False), encoding="utf-8")
    sys.stdout.write(text if not args.md else text.split("\n\n| File")[0] + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
