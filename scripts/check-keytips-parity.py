#!/usr/bin/env python3
# SPDX-License-Identifier: AGPL-3.0-only
"""Fail when the ribbon KeyTips, the tab access keys or the shortcuts drift from the familiar office suite.

Usage: python3 scripts/check-keytips-parity.py [--tree PATCHED_TREE]

Offline (CI), from the committed tables data/ribbon/keytips-office-parity.json and shortcuts-office-parity.json:
  1. the tab letters of the series' HstKeyTipTable.hxx are the suite's (H Home, N Insert, A Animations, ...);
  2. on every tab, the suite's command letters are prefix-free, and hst-ribbon-keytips-office.patch is generated
     from the table (scripts/patches/generate-keytips-office-parity.py);
  3. a ribbon tab label of the Vietnamese UI has no access key, or exactly its tab letter, so a label never shows
     a letter that Alt+letter does not open (l10n/access-keys-snapshot.json with l10n/vi-overrides.jsonl);
  4. every shortcut row marked changed is bound by hst-msoffice-shortcuts-parity.patch, and no later patch or the
     HST extension binds a parity key to another command.
With --tree (a fresh apply of the series, scripts/l10n merge applied for 3): the KeyTip assignment is replayed over
the notebookbar.ui files, every table letter must win on its tab, and every shortcut row must hold in Accelerators.xcu.
"""
import argparse
import importlib
import json
import os
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path[:0] = [os.path.join(ROOT, "scripts", "ribbon"), os.path.join(ROOT, "scripts", "l10n"),
                os.path.join(ROOT, "scripts", "patches")]
import accelerators_model as accel  # noqa: E402
import keytips_model as model  # noqa: E402
from access_keys_labels import load_overrides, mnemonic, resolve  # noqa: E402

PATCHES = os.path.join(ROOT, "patches", "libreoffice")
KEYTIPS = os.path.join(ROOT, "data", "ribbon", "keytips-office-parity.json")
SHORTCUTS = os.path.join(ROOT, "data", "ribbon", "shortcuts-office-parity.json")
SHORTCUT_PATCH = "hst-msoffice-shortcuts-parity.patch"
APP_OF_CONTAINER = {"Writer": "writer", "Calc": "calc", "Impress": "impress", "Draw": "draw"}


def read_json(path):
    with open(path, encoding="utf-8") as handle:
        return json.load(handle)


def check_tabs(table, tab_keys, errors):
    for app, tabs in table["tabs"].items():
        for tab, letter in tabs.items():
            if tab_keys.get(tab) != letter:
                errors.append(f"{app}: tab {tab} has KeyTip {tab_keys.get(tab)!r}, the suite uses {letter!r}")


def check_commands(table, errors):
    for module, tabs in table["commands"].items():
        for tab, commands in tabs.items():
            letters = [(ident, letter) for ident, (letter, _control) in commands.items()]
            for i, (a, la) in enumerate(letters):
                for b, lb in letters[i + 1:]:
                    if model.prefix_clash(la, lb):
                        errors.append(f"{module}/{tab}: {a} {la!r} and {b} {lb!r} cannot both have their letter")
    generator = importlib.import_module("generate-keytips-office-parity")
    with open(generator.PATCH, encoding="utf-8") as handle:
        if handle.read() != generator.patch_text():
            errors.append("hst-ribbon-keytips-office.patch is out of date: run "
                          "scripts/patches/generate-keytips-office-parity.py")


def check_tab_labels(table, snapshot, overrides, errors):
    labels = snapshot["labels"]
    for container in snapshot["containers"]:
        if container["type"] != "tab-bars":
            continue
        app = APP_OF_CONTAINER.get(container["path"].split(" > ")[0])
        for item in container["items"]:
            label, markers = resolve(dict(item, labels=[labels[i] for i in item["labels"]]), overrides)
            char = mnemonic(label, markers)
            tip = table["tabs"].get(app, {}).get(item["id"], "")
            if char and char.upper() != tip:
                errors.append(f"{container['path']}: tab label {label!r} shows access key {char.upper()}, "
                              f"but Alt+{char.upper()} does not open it (KeyTip {tip or 'none'})")


def later_conflicts(rows, texts, errors):
    """A patch after the parity patch ({name: [(key, command)]}) must not bind a parity key to another command."""
    for row in rows:
        if row["status"] == "deviation":
            continue
        for name, bound in texts.items():
            for key, command in bound:
                if key == row["key"] and command not in row["uno"]:
                    errors.append(f"{name} binds {key} to {command}; {row['app']} {row['office']} is "
                                  f"{'/'.join(row['uno'])} in {os.path.relpath(SHORTCUTS, ROOT)}")


def check_shortcut_patches(rows, errors):
    names = model.series_patches(PATCHES)
    if SHORTCUT_PATCH not in names:
        errors.append(f"{SHORTCUT_PATCH} is not in the series")
        return
    texts = {}
    for name in names[names.index(SHORTCUT_PATCH):]:
        with open(os.path.join(PATCHES, name), encoding="utf-8") as handle:
            texts[name] = accel.patch_bindings(handle.read())
    ours = texts.pop(SHORTCUT_PATCH)
    later_conflicts(rows, texts, errors)
    extension = accel.load([os.path.join(ROOT, accel.EXTENSION)])
    for row in rows:
        if row["status"] == "changed" and not any(k == row["key"] and c in row["uno"] for k, c in ours):
            errors.append(f"{row['app']} {row['office']}: {SHORTCUT_PATCH} does not bind {row['key']}")
        if row["status"] == "deviation":
            continue
        command = extension.get(accel.MODULES[row["app"]], {}).get(row["key"])
        if command and command.replace(".uno:", "") not in row["uno"]:
            errors.append(f"{accel.EXTENSION} binds {row['key']} to {command} in {row['app']}")


def check_tree(tree, table, rows, errors):
    general = model.parse_table(open(os.path.join(tree, model.TABLE_HEADER), encoding="utf-8").read(), "COMMAND_KEYS")
    office = {f"{m}/{t}/{i}": letter for m, tabs in table["commands"].items()
              for t, cs in tabs.items() for i, (letter, _c) in cs.items()}
    simulated = model.simulate(tree, office, general)
    for app, (module, _ui) in model.MODULES.items():
        for tab, commands in table["commands"].get(module, {}).items():
            got = dict(reversed(simulated.get(app, {}).get(tab, [])))  # the first item of a command counts
            for ident, (letter, control) in commands.items():
                if ident in got and got[ident] != letter:
                    errors.append(f"{app} {tab}: {ident} ({control}) gets {got[ident]!r}, the suite uses {letter!r}")
    bindings = accel.load([os.path.join(tree, accel.ACCELERATORS), os.path.join(ROOT, accel.EXTENSION)])
    for row in rows:
        actual = accel.effective(bindings, row["app"], row["key"])
        expected = row["uno"] if row["status"] != "deviation" else [row.get("hst") or ""]
        if actual not in expected:
            errors.append(f"{row['app']} {row['office']} ({row['key']}): HST runs {actual or 'nothing'}, "
                          f"the table says {'/'.join(x or 'nothing' for x in expected)}")


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--tree", help="patched source tree")
    args = parser.parse_args(argv)
    table, rows = read_json(KEYTIPS), read_json(SHORTCUTS)["rows"]
    errors = []
    try:
        with tempfile.TemporaryDirectory() as work:
            header = model.header_from_series(PATCHES, model.TABLE_HEADER, work)
        check_tabs(table, model.parse_table(header, "TAB_KEYS"), errors)
        check_commands(table, errors)
        check_tab_labels(table, read_json(os.path.join(ROOT, "l10n", "access-keys-snapshot.json")),
                         load_overrides(os.path.join(ROOT, "l10n", "vi-overrides.jsonl")), errors)
        check_shortcut_patches(rows, errors)
        if args.tree:
            check_tree(args.tree, table, rows, errors)
    except (OSError, ValueError, KeyError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    for error in errors:
        print("FAIL", error)
    keytips = sum(len(c) for tabs in table["commands"].values() for c in tabs.values())
    print(f"KeyTip parity: {keytips} command letters, {sum(len(t) for t in table['tabs'].values())} tab letters; "
          f"shortcuts: {len(rows)} rows; {'tree checked' if args.tree else 'offline'}; {len(errors)} failures")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
