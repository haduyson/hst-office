# SPDX-License-Identifier: AGPL-3.0-only
"""Owner rule: every shortcut and KeyTip matches the reference suite 100 %, checked against the parity data (no GUI).

Usage: python3 tests/runtime/check-ribbon-parity-data.py [--out DIR]
Reads data/ribbon/shortcuts-office-parity.json: every row must have status "match" ("handler": the suite's key runs
the same action through a key listener, scripts/check-keytips-parity.py --tree proves the listener). A row with status "changed" or
"deviation" is a FAIL and is listed with its app, the suite's key, the HST command and the recorded reason. No
exception list exists: an owner decision is needed to accept any of them. Reads data/ribbon/keytips-office-parity.json
for the KeyTip tables (one entry per tab and command). The runtime KeyTip and shortcut checks are
check-keytips-office-parity.py (Linux) and check-windows-keytips-office-parity.py (Windows); they run separately.
Exit 1 when any row is not "match". Writes <out>/parity-data.json when --out is given.
"""
import argparse
import collections
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "..", "..", "data", "ribbon")


def shortcut_failures(rows):
    """Rows whose status is neither "match" nor "handler", as dicts with the fields the report needs."""
    return [{"app": r["app"], "office": r["office"], "status": r["status"], "hst": r.get("hst"),
             "reason": r.get("reason", "")} for r in rows if r.get("status") not in ("match", "handler")]


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--out")
    args = parser.parse_args()
    with open(os.path.join(DATA, "shortcuts-office-parity.json"), encoding="utf-8") as handle:
        rows = json.load(handle)["rows"]
    with open(os.path.join(DATA, "keytips-office-parity.json"), encoding="utf-8") as handle:
        keytips = json.load(handle)
    failures = shortcut_failures(rows)
    per_app = collections.Counter(f["app"] for f in failures)
    print(f"shortcuts: {len(rows)} rows, {len(rows) - len(failures)} match, {len(failures)} not 100 %", flush=True)
    for app in ("writer", "calc", "impress", "draw"):
        print(f"  {app}: {per_app.get(app, 0)} not matching", flush=True)
    for f in failures:
        print(f"FAIL  {f['app']}  {f['office']}  {f['status']}  hst={f['hst']}  {f['reason']}", flush=True)
    keytip_commands = sum(len(v) for v in keytips["commands"].values())
    print(f"keytips table: {len(keytips['tabs'])} tab maps, {keytip_commands} command entries (runtime check separate)")
    if args.out:
        os.makedirs(args.out, exist_ok=True)
        with open(os.path.join(args.out, "parity-data.json"), "w", encoding="utf-8") as handle:
            json.dump({"rows": len(rows), "failures": failures, "per_app": per_app}, handle, ensure_ascii=False, indent=1)
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
