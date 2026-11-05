# SPDX-License-Identifier: AGPL-3.0-only
"""Coverage table and ranked gaps from sandbox results.

Usage: summarize.py OUT.md CENSUS.json GROUP=POLICY:SCAN:RESULTS... . "Pass" means the procedure ended without an error. It says nothing about correctness:
macros with an asserted result are reported separately, and passes under On Error Resume Next are counted as masked.
"""
import collections
import json
import re
import sys

MISSING = re.compile(r"(?:Property or method not found|procedure not defined\.?\s*Additional information|Variable not defined\.?\s*Additional information)[:\s]+\$?\(?(\w+)", re.I)
RESUME = re.compile(r"On\s+Error\s+Resume\s+Next", re.I)
PROC = re.compile(r"(?im)^[ \t]*(?:(?:Public|Private|Friend|Static)[ \t]+)*(?:Sub|Function|Property[ \t]+\w+)[ \t]+([^\s(]+)(.*?)^[ \t]*End[ \t]+(?:Sub|Function|Property)", re.S)
COLUMNS = ["macro files", "blocked by policy", "loaded", "load failed", "files w/ compile error", "procedures", "run", "pass", "pass masked", "compile error", "unsupported", "error, other", "needs earlier state", "windows-only", "timeout", "crash", "blocked procs", "with params", "over limit", "formula cells", "from file", "UDF cells", "differ"]


def records(path):
    with open(path, encoding="utf-8", errors="replace") as handle:
        for line in handle:
            if line.startswith("@@R "):
                try:
                    yield json.loads(line[4:])
                except ValueError:
                    pass


def classify(result):
    """(column of the table, name of the gap)."""
    status = result["status"]
    if status == "pass":
        return "pass", None
    if status == "timeout":
        return "timeout", "timeout (hang or very slow)"
    if status in ("exception", "load-raised"):
        return "crash", "office crashed"
    if status == "no-return":
        texts = [t for d in result.get("dialogs", []) for t in d["text"][1:2]]
        first = next((t for t in texts if "syntax" in t.lower()), texts[0] if texts else "no return")
        return "compile error", "compile: " + re.sub(r"BASIC syntax error\.?\s*", "", first).replace("\n", " ")[:70]
    if status == "wrong-result":
        return "error, other", "wrong result"
    if status != "error":
        return "error, other", status
    err = result.get("err", ["", "", "", ""])
    text = re.sub(r"\s+", " ", str(err[-1]))
    source = (result.get("where") or {}).get("source", "")
    match = MISSING.search(str(err[-1]))
    if match:
        return "unsupported", "missing: " + match.group(1)
    if str(err[0]) == "91":
        return "needs earlier state", "object not set (needs earlier state or missing object)"
    if "Not implemented" in text or re.search(r"\bDeclare\b", source):
        return "windows-only", "Windows API (Declare)" if "(" in source and "Not implemented" in text else "not implemented: " + source[:60]
    text = re.sub(r"An exception occurred Type: com\.sun\.star\.\w+\.", "UNO ", text)
    return "error, other", text[:60]


def masked_procs(scan_path):
    out = {}
    with open(scan_path, encoding="utf-8") as handle:
        for line in handle:
            scan = json.loads(line)
            if scan.get("has_macros"):
                code = "\n".join(m["code"] or "" for m in scan.get("modules", []))
                out[scan["name"]] = {m.group(1).lower() for m in PROC.finditer(code) if RESUME.search(m.group(2))}
    return out


def main():
    table, gaps, gap_files, examples = {}, collections.Counter(), collections.defaultdict(set), {}
    out_path, census_path = sys.argv[1:3]
    for spec in sys.argv[3:]:
        group_name, rest = spec.split("=")
        policy_path, scan_path, results_path = rest.split(":")
        with open(policy_path, encoding="utf-8") as handle:
            policy = json.load(handle)
        masked = masked_procs(scan_path)
        for verdict in policy.values():
            group = table.setdefault((group_name, verdict.get("kind") or "other"), collections.Counter())
            group["macro files"] += 1
            group["blocked by policy"] += not verdict["run"]
        compile_files = collections.defaultdict(set)
        for result in records(results_path):
            verdict = policy.get(result["file"], {})
            key = (group_name, verdict.get("kind") or "other")
            group = table.setdefault(key, collections.Counter())
            if result["event"] == "file":
                loaded = result.get("status") == "loaded"
                group["loaded"] += loaded
                group["load failed"] += not loaded
                for module in result.get("modules", []):
                    group["procedures"] += len(module["procs"])
                    group["with params"] += module.get("parameters", 0)
                recalc = result.get("recalc") or {}
                group["formula cells"] += recalc.get("formula_cells", 0)
                group["from file"] += recalc.get("from_file", 0)
                group["UDF cells"] += recalc.get("udf_cells", 0)
                group["differ"] += recalc.get("differ", 0)
            elif result["event"] == "proc":
                column, gap = classify(result)
                group["run"] += 1
                group[column] += 1
                if column == "pass":
                    group["pass masked"] += result["proc"].lower() in masked.get(result["file"], ())
                else:
                    gaps[(key[1], gap)] += 1
                    gap_files[(key[1], gap)].add(result["file"])
                    examples.setdefault((key[1], gap), (verdict.get("repo"), (verdict.get("path") or "")[-36:], result["proc"], (result.get("where") or {}).get("source", "")[:70]))
                    if column == "compile error":
                        compile_files[key].add(result["file"])
            elif result["event"] == "policy-skip":
                group["blocked procs"] += len(result["procs"])
            elif result["event"] == "file-done":
                group["over limit"] += result.get("skipped_over_limit", 0)
        for key, files in compile_files.items():
            table[key]["files w/ compile error"] += len(files)
    lines = ["| Group | " + " | ".join(COLUMNS) + " |", "|---|" + "---|" * len(COLUMNS)]
    total = collections.Counter()
    for (group_name, kind), group in sorted(table.items()):
        total.update(group)
        lines.append(f"| {group_name} {kind} | " + " | ".join(str(group[c]) for c in COLUMNS) + " |")
    lines.append("| **all** | " + " | ".join(str(total[c]) for c in COLUMNS) + " |")
    lines += ["", "| Rank | App | Gap | Procedures | Files | Example |", "|---|---|---|---:|---:|---|"]
    ranked = sorted(gaps, key=lambda k: (-len(gap_files[k]), -gaps[k]))
    for rank, key in enumerate(ranked[:80], 1):
        example = examples[key]
        lines.append(f"| {rank} | {key[0]} | {key[1]} | {gaps[key]} | {len(gap_files[key])} | {example[1]} {example[2]}: `{example[3]}` |")
    text = "\n".join(lines) + "\n"
    with open(out_path, "w", encoding="utf-8") as handle:
        handle.write(text)
    print(text)


if __name__ == "__main__":
    main()
