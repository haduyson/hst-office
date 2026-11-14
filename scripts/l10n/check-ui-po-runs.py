#!/usr/bin/env python3
# SPDX-License-Identifier: AGPL-3.0-only
"""Fail when a patch breaks the per-source-file runs of the Vietnamese officecfg UI.po.

cfgex reads only the first contiguous run of entries of a source file. An entry of GenericCommands.xcu placed
outside its run is ignored, and one placed before it makes cfgex skip the whole real run: every generic command
label of the Vietnamese registry then falls back to English.

  scripts/l10n/check-ui-po-runs.py [--tree DIR] [--write-baseline PRISTINE_UI_PO]

Always (needs only the repository): for the UI.po hunks of patches/libreoffice/series, every entry that stays added must
sit beside a comment hash of its own source file, known from the pristine file (data/l10n/ui-po-runs.json).
With a LibreOffice tree: the file itself must have one run per source file, and when cfgex is built it must yield at
least MIN_GENERIC Vietnamese GenericCommands labels.
"""
import argparse
import json
import os
import re
import subprocess
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
UI_PO = "translations/source/vi/officecfg/registry/data/org/openoffice/Office/UI.po"
BASELINE = os.path.join(ROOT, "data/l10n/ui-po-runs.json")
SOURCE = re.compile(r'^"(\w+\.xcu)\\n"$')
REFERENCE = re.compile(r"^#: (\w+\.xcu)$")  # the source reference line of a neighbouring entry
HUNK = re.compile(r"^@@ -\d+(?:,\d+)? \+\d+(?:,\d+)? @@")
MIN_GENERIC = 1000


def runs_of(lines):
    """[[source file, first line, last line]] with 1-based line numbers of the marker lines."""
    runs = []
    for number, line in enumerate(lines, 1):
        match = SOURCE.match(line)
        if not match:
            continue
        if runs and runs[-1][0] == match.group(1):
            runs[-1][2] = number
        else:
            runs.append([match.group(1), number, number])
    return runs


def duplicates(runs):
    seen, bad = set(), []
    for name, first, _last in runs:
        if name in seen:
            bad.append(f"{name} has a second run at line {first}")
        seen.add(name)
    return bad


def anchors_of(lines):
    """{hash of an entry comment: source file} of a .po text."""
    found, current = {}, None
    for line in lines:
        if line.startswith("#. "):
            current = line[3:].strip()
        match = SOURCE.match(line)
        if match and current:
            found.setdefault(current, match.group(1))
            current = None
    return found


def patch_hunks(path):
    """[(context lines, removed lines, added lines)] of the UI.po section of one patch."""
    with open(path, encoding="utf-8", errors="replace") as handle:
        text = handle.read()
    hunks = []
    for section in re.split(r"(?m)^(?=--- )", text):
        if not section.startswith(f"--- a/{UI_PO}"):
            continue
        current = None
        for line in section.split("\n"):
            if HUNK.match(line):
                current = ([], [], [])
                hunks.append(current)
            elif current is not None and line[:1] in (" ", "-", "+"):
                current[" -+".index(line[0])].append(line[1:])
    return hunks


def entry_keys(lines):
    """The command path lines of the entries in added or removed lines."""
    return [line for line in lines if line.startswith('"..')]


def replay(baseline, series_dir):
    """Problems of entries that end up beside entries of another source file."""
    anchors = {value: source for source, values in baseline.items() for value in values.split()}
    placed = {}  # entry path line -> (patch, source, source of its neighbour)
    with open(os.path.join(series_dir, "series"), encoding="utf-8") as handle:
        names = [line.strip() for line in handle if line.strip() and not line.startswith("#")]
    for name in names:
        for context, removed, added in patch_hunks(os.path.join(series_dir, name)):
            for key in entry_keys(removed):
                placed.pop(key, None)
            neighbour = next((anchors[c[3:].strip()] for c in context if c.startswith("#. ") and c[3:].strip() in anchors), None)
            if neighbour is None:  # no known comment hash (HST hashes repeat across files): the neighbour's
                # source marker or its "#: <file>.xcu" reference line, else nothing to go by
                neighbour = next((m.group(1) for line in context for m in (SOURCE.match(line), REFERENCE.match(line)) if m),
                                 None)
            source, keys = None, []
            for line in added:
                match = SOURCE.match(line)
                if match:
                    source = match.group(1)
                elif line.startswith('"..') and source:
                    keys.append((line, source))
            for key, entry_source in keys:
                placed[key] = (name, entry_source, neighbour)
            anchors.update({k: v for k, v in anchors_of(added).items() if not k.startswith("hst")})
    return [f"{name}: {key[1:-3]} of {source} is added beside {neighbour or 'nothing known'}"
            for key, (name, source, neighbour) in placed.items() if neighbour != source]


def tree_problems(tree):
    path = os.path.join(tree, UI_PO)
    if not os.path.isfile(path):
        return None, "no tree"
    with open(path, encoding="utf-8") as handle:
        problems = duplicates(runs_of(handle.read().split("\n")))
    cfgex = os.path.join(tree, "workdir/LinkTarget/Executable/cfgex")
    source = os.path.join(tree, "officecfg/registry/data/org/openoffice/Office/UI/GenericCommands.xcu")
    if not (os.path.exists(cfgex) and os.path.exists(source)):
        return problems, "cfgex not built"
    with tempfile.TemporaryDirectory() as work:
        merge, out = os.path.join(work, "merge"), os.path.join(work, "out.xcu")
        with open(merge, "w", encoding="utf-8") as handle:
            handle.write(path + "\n")
        env = dict(os.environ, LD_LIBRARY_PATH=os.path.join(tree, "instdir/program"))
        run = subprocess.run([cfgex, "-i", source, "-o", out, "-m", merge, "-l", "vi"], env=env, cwd=tree, capture_output=True, text=True)
        if run.returncode or not os.path.exists(out):
            return problems + [f"cfgex failed: {run.stderr[:200]}"], "cfgex"
        with open(out, encoding="utf-8") as handle:
            count = handle.read().count('xml:lang="vi"')
    if count < MIN_GENERIC:
        problems.append(f"cfgex yields {count} Vietnamese GenericCommands labels, expected at least {MIN_GENERIC}")
    return problems, f"cfgex yields {count} Vietnamese GenericCommands labels"


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--tree", default=os.path.join(ROOT, "upstream/libreoffice"))
    parser.add_argument("--write-baseline", help="pristine UI.po to record the run ranges from")
    args = parser.parse_args()
    if args.write_baseline:
        with open(args.write_baseline, encoding="utf-8") as handle:
            found = anchors_of(handle.read().split("\n"))
        by_source = {}
        for value, source in sorted(found.items()):
            by_source.setdefault(source, []).append(value)
        with open(BASELINE, "w", encoding="utf-8") as handle:
            json.dump({source: " ".join(values) for source, values in sorted(by_source.items())}, handle, indent=0)
            handle.write("\n")
        print(f"{len(found)} entries of {len(by_source)} source files written to {BASELINE}")
        return 0
    with open(BASELINE, encoding="utf-8") as handle:
        baseline = json.load(handle)
    problems = replay(baseline, os.path.join(ROOT, "patches/libreoffice"))
    tree, note = tree_problems(args.tree)
    problems += tree or []
    for problem in problems:
        print("FAIL", problem)
    print(f"UI.po runs: {len(baseline)} source files, {len(problems)} problems ({note})")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
