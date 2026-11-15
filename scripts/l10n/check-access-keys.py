#!/usr/bin/env python3
# SPDX-License-Identifier: AGPL-3.0-only
"""Check explicit Vietnamese menu/notebookbar mnemonics, with an offline CI snapshot.

Snapshot labels retain escaped PO msgid/msgstr, decoded msgctxt, and fallback
order. Only base PO translations/fuzzy flags are excluded from freshness checks.
Counts are duplicate-key groups, not pairs. Dynamic popup contents are outside
this static XML model; controls and contextual-only tab conflicts are warnings.
Exceptions match a problem's kind, container, uppercase key and exact label
multiset; kind defaults to collision. Stale exceptions fail --strict.
Snapshot v2 pools repeated label sources, with
one source/container per line to keep offline checks compact and reviewable.
"""
import argparse
from collections import defaultdict
import json
from pathlib import Path
import sys
import xml.etree.ElementTree as ET

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(HERE))
from access_keys_dialogs import dialog_containers, english_groups, is_override  # noqa: E402
# the parts of this check, re-exported for its callers and tests
from access_keys_labels import (LANG, MENU, OOR, UI_PO, escape, label_text, load_overrides,  # noqa: E402,F401
                                mnemonic, resolve, strip_mnemonics, unescape)
from access_keys_model import APPS, ModelBuilder, build_model, finish  # noqa: E402,F401
from access_keys_snapshot import (REGENERATE, load_model, load_tree_model, merge_addons,  # noqa: E402,F401
                                  read_snapshot, stale_containers, structure, write_json, write_snapshot)


def load_exceptions(path):
    if not Path(path).exists():
        return []
    exceptions = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(exceptions, list):
        raise ValueError("access-key exceptions must be a list")
    seen = set()
    for entry in exceptions:
        kind = entry.get("kind", "collision") if isinstance(entry, dict) else None
        if (not isinstance(entry, dict) or set(entry) - {"kind"} != {"container", "key", "labels", "reason"}
                or kind not in ("collision", "non-ascii")
                or not all(isinstance(entry[k], str) and entry[k].strip()
                           for k in ("container", "key", "reason"))
                or entry["key"] != entry["key"].upper()
                or not isinstance(entry["labels"], list)
                or (len(entry["labels"]) != 1 if kind == "non-ascii" else len(entry["labels"]) < 2)
                or not all(isinstance(label, str) for label in entry["labels"])):
            raise ValueError("invalid access-key exception")
        identity = (kind, entry["container"], entry["key"], tuple(sorted(entry["labels"])))
        if identity in seen:
            raise ValueError("duplicate access-key exception")
        seen.add(identity)
    return exceptions


def check(model, overrides, exceptions=()):
    problems, info, summary = [], [], {}
    for container in model["containers"]:
        group = container["app"] + " menus" if container["type"] == "menus" else container["type"]
        counts = summary.setdefault(group, {"collisions": 0, "non-ascii": 0})
        keys = defaultdict(list)
        dialog = container["type"] == "dialogs"
        english = english_groups(container, mnemonic) if dialog else {}

        def report(kind, key, items, strict):
            problems.append(dict(container=container["path"], type=container["type"],
                                 kind=kind, key=key, items=items, strict=strict))
            counts["collisions" if kind == "collision" else kind] += 1

        for item in container["items"]:
            label, markers = resolve(item, overrides)
            char = mnemonic(label, markers)
            shown = dict(id=item["id"], command=item["command"], label=label,
                         contextual=item.get("contextual", False))
            if dialog:
                shown["override"] = is_override(item, overrides)
            if not char:
                if not dialog:
                    info.append(dict(container=container["path"], kind="auto" if item.get("auto") else "none", **shown))
                continue
            keys[char.upper()].append(shown)
            if not (char.isascii() and char.isalnum()):
                report("non-ascii", char.upper(), [shown], container["strict"] and shown.get("override", True))
        for key, items in sorted(keys.items()):
            if len(items) > 1:
                strict = container["strict"] and not (container["type"] == "tab-bars"
                                                       and all(i["contextual"] for i in items))
                if dialog:  # strict only when HST chose one of the keys and English has no such collision
                    ids = {i["id"] for i in items}
                    strict = (any(i["override"] for i in items)
                              and not any(ids <= group for group in english.values()))
                report("collision", key, items, strict)
    by_identity = {(p["kind"], p["container"], p["key"], tuple(sorted(i["label"] for i in p["items"]))): p
                   for p in problems}
    stale = []
    for entry in exceptions:
        identity = (entry.get("kind", "collision"), entry["container"], entry["key"], tuple(sorted(entry["labels"])))
        if identity in by_identity:
            by_identity[identity]["exception"] = entry["reason"]
        else:
            stale.append(entry)
    return dict(problems=problems, info=info, summary=summary, stale_exceptions=stale,
                strict_problems=sum(p["strict"] and "exception" not in p for p in problems) + len(stale))


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--tree", type=Path, default=ROOT / "upstream/libreoffice")
    parser.add_argument("--overrides", type=Path, default=ROOT / "l10n/vi-overrides.jsonl")
    parser.add_argument("--snapshot", type=Path, default=ROOT / "l10n/access-keys-snapshot.json")
    parser.add_argument("--exceptions", type=Path, default=ROOT / "l10n/access-keys-exceptions.json")
    parser.add_argument("--addons", type=Path, default=ROOT / "extensions/hst-vietnamese-tools/Addons.xcu")
    parser.add_argument("--json", type=Path)
    for flag in ("strict", "write-snapshot", "verbose", "no-dialogs"):
        parser.add_argument("--" + flag, action="store_true")
    args = parser.parse_args(argv)
    try:
        model = load_model(args.tree, args.snapshot, args.write_snapshot, args.addons)
        dialogs = Path(args.tree).exists() and not args.no_dialogs
        if dialogs:  # .ui dialogs come from the tree only; see access_keys_dialogs.py
            model["containers"] += dialog_containers(args.tree, ModelBuilder(args.tree))
        exceptions = load_exceptions(args.exceptions)
        if not dialogs:  # dialog exceptions ("x.ui:Dialog") cannot be checked without the tree
            exceptions = [e for e in exceptions if ".ui:" not in e["container"]]
        result = check(model, load_overrides(args.overrides), exceptions)
        if args.json:
            write_json(args.json, result)
    except (OSError, ValueError, SyntaxError, KeyError, ET.ParseError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    for problem in result["problems"]:
        if problem["type"] == "dialogs" and not problem["strict"] and not args.verbose:
            continue  # upstream Vietnamese dialog keys: counted below, listed with --verbose
        labels = " | ".join(i["label"] for i in problem["items"])
        kind = "key" if problem["kind"] == "collision" else "non-ascii"
        severity = "strict" if problem["strict"] else "warning"
        if "exception" in problem:
            severity = "excepted: " + problem["exception"]
        print(f"{problem['container']}: {kind} {problem['key']}: {labels} [{severity}]")
    for entry in result["stale_exceptions"]:
        print(f"{entry['container']}: stale exception for key {entry['key']}: {entry['labels']} [strict]")
    if args.verbose:
        for item in result["info"]:
            print(f"{item['container']}: {item['kind']}: {item['label']} ({item['id']})")
    print(f"{'Container type':<24} {'Collisions':>10} {'Non-ASCII':>10}")
    for group, counts in sorted(result["summary"].items()):
        print(f"{group:<24} {counts['collisions']:>10} {counts['non-ascii']:>10}")
    print(f"Strict problems: {result['strict_problems']}; auto items: "
          f"{sum(i['kind'] == 'auto' for i in result['info'])} (details: --verbose/--json)")
    print(f"Excepted problems: {sum('exception' in p for p in result['problems'])}; "
          f"stale exceptions: {len(result['stale_exceptions'])}")
    if dialogs:
        print("Dialogs: strict only where an override chose a key that English does not share "
              "(upstream Vietnamese keys are warnings, listed with --verbose)")
    else:
        print("Dialogs: not checked (needs the source tree)")
    return int(args.strict and result["strict_problems"] > 0)


if __name__ == "__main__":
    sys.exit(main())
