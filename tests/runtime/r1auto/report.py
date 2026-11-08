#!/usr/bin/env python3
# SPDX-License-Identifier: AGPL-3.0-only
"""Initialize before download; summarize even if installation or tooling fails."""
import argparse
import json
import os
from pathlib import Path
from results import Results, parse_items, summary

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("action", choices=("init", "summary"))
parser.add_argument("--out", required=True)
parser.add_argument("--platform", choices=("windows", "macos"))
parser.add_argument("--run-id")
parser.add_argument("--items", default="")
args = parser.parse_args()
if args.action == "init":
    Results(args.out, args.platform, args.run_id, parse_items(args.items, args.platform))
else:
    out = Path(args.out)
    report = json.loads((out / "results.json").read_text(encoding="utf-8"))
    text = summary(report)
    (out / "summary.md").write_text(text, encoding="utf-8")
    with open(os.environ["GITHUB_STEP_SUMMARY"], "a", encoding="utf-8") as handle:
        handle.write(text)
