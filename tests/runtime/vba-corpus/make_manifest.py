# SPDX-License-Identifier: AGPL-3.0-only
"""The corpus as a manifest, no third-party files: fetch_corpus.py gets them from their pinned sources. Usage: make_manifest.py OUT.json SCAN:INDEX:POLICY..."""
import json
import sys


def main():
    rows = []
    for spec in sys.argv[2:]:
        scan_path, index_path, policy_path = spec.split(":")
        with open(index_path, encoding="utf-8") as handle:
            index = {}
            for entry in json.load(handle):
                if "name" in entry:
                    index.setdefault(entry["name"], entry)
        with open(policy_path, encoding="utf-8") as handle:
            policy = json.load(handle)
        with open(scan_path, encoding="utf-8") as handle:
            for line in handle:
                scan = json.loads(line)
                entry = index.get(scan["name"])
                if scan.get("has_macros") and entry and scan.get("bytes"):
                    verdict = policy.get(scan["name"], {})
                    rows.append(dict(repo=entry["repo"], commit=entry["commit"], path=entry["path"], sha256=entry["sha256"], licence=entry.get("licence"),
                                     app=scan.get("app") or None, codepage=scan.get("codepage"), runs=verdict.get("run"), flags=verdict.get("flags") or None))
    rows.sort(key=lambda r: (r["repo"], r["path"]))
    with open(sys.argv[1], "w", encoding="utf-8") as handle:
        handle.write("[\n" + ",\n".join(json.dumps(r, ensure_ascii=False, sort_keys=True) for r in rows) + "\n]\n")
    print(len(rows))


if __name__ == "__main__":
    main()
