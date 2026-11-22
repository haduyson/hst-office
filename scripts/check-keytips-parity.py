#!/usr/bin/env python3
# SPDX-License-Identifier: LicenseRef-HST-Proprietary
# Copyright (C) 2026 HASON TECH
"""Fail when the ribbon KeyTips, the tab access keys or the shortcuts drift from the familiar office suite.

Usage: python3 scripts/check-keytips-parity.py [--tree PATCHED_TREE]

Offline (CI), from the committed tables data/ribbon/keytips-office-parity.json and shortcuts-office-parity.json:
  1. the tab letters of the series' HstKeyTipTable.hxx are the suite's (H Home, N Insert, A Animations, ...);
  2. on every tab, the suite's command letters are prefix-free, and hst-ribbon-keytips-office.patch is generated
     from the table (scripts/patches/generate-keytips-office-parity.py);
  3. a ribbon tab label of the Vietnamese UI has no access key, or exactly its tab letter, so a label never shows
     a letter that Alt+letter does not open (l10n/access-keys-snapshot.json with l10n/vi-overrides.jsonl);
  4. every shortcut row with "via" is bound by that patch, and no later patch or the HST extension binds a parity key
     to another command.
With --tree (a fresh apply of the series, scripts/l10n merge applied for 3): the KeyTip assignment is replayed over
the notebookbar.ui files, every table letter must win on its tab, and every shortcut row must hold in Accelerators.xcu
(macOS rows with the macOS values; a "vcl" row's key must stay free; a planned row's key free or already right); a
matching row must also match on macOS, with its "mac" key (the suite's Mac edition) or Cmd for Ctrl, unless it has a
"mac_exception".
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
            letters = [(ident, letter, control) for ident, (letter, control) in commands.items()]
            for i, (a, la, ca) in enumerate(letters):
                for b, lb, cb in letters[i + 1:]:
                    # twins (one control of the suite, widgets shown at different sizes) share their letter: the
                    # KeyTips only reach visible widgets (HstRibbonKeyTips.cxx CollectCommands)
                    if model.prefix_clash(la, lb) and not (la == lb and ca == cb):
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
        if row["status"] != "match":
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
    vias = {row["via"] for row in rows if row.get("via")}
    ours = {name: texts.pop(name, None) for name in vias}  # the parity patches; checked per row below
    later_conflicts(rows, texts, errors)
    extension = accel.load([os.path.join(ROOT, accel.EXTENSION)])
    for row in rows:
        via = row.get("via")
        if via and ours[via] is None:
            errors.append(f"{row['app']} {row['office']}: {via} is not in the series after {SHORTCUT_PATCH}")
        elif via and not any(k == row["key"] and c in row["uno"] for k, c in ours[via]):
            errors.append(f"{row['app']} {row['office']}: {via} does not bind {row['key']}")
        if row["status"] != "match" or row.get("platform"):
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
                if ident not in got:
                    errors.append(f"{app} {tab}: {ident} ({control}, {letter!r}) has no button on the tab: "
                                  "regenerate scripts/ribbon/build-keytips-parity.py")
                elif got[ident] != letter and not any(o != ident and c == [letter, control] and got.get(o) == letter
                                                      for o, c in commands.items()):
                    errors.append(f"{app} {tab}: {ident} ({control}) gets {got[ident]!r}, the suite uses {letter!r}")
    files = [os.path.join(tree, accel.ACCELERATORS), os.path.join(ROOT, accel.EXTENSION)]
    bindings = {p: accel.load(files, p) for p in ("unxwnt", "macosx")}
    for row in rows:
        if row["status"] == "handler":  # a key listener, not an accelerator: the tree must carry its key test
            path, test = row["handler"]
            source = os.path.join(tree, path)
            if not os.path.exists(source) or test not in open(source, encoding="utf-8").read():
                errors.append(f"{row['app']} {row['office']} ({row['key']}): {path} lacks {test!r}")
            continue
        platform = "macosx" if row.get("platform") == "macos" else "unxwnt"
        actual = accel.effective(bindings[platform], row["app"], row["key"])
        if row.get("handler") == "vcl":
            expected = [""]  # the window system handles the key; an accelerator would take it away
        elif row["status"] == "deviation":
            expected = [row.get("hst") or ""]
        elif row["status"] == "planned":
            expected = row["uno"] + [row.get("hst") or ""]
        else:
            expected = row["uno"]
        if actual not in expected:
            errors.append(f"{row['app']} {row['office']} ({row['key']}): HST runs {actual or 'nothing'}, "
                          f"the table says {'/'.join(x or 'nothing' for x in expected)}")
        if row["status"] == "match" and platform == "unxwnt" and not row.get("handler") and not row.get("mac_exception"):
            key = row.get("mac", row["key"])  # the suite's Mac key, else Cmd for Ctrl
            on_mac = accel.effective(bindings["macosx"], row["app"], key)
            if on_mac not in row["uno"]:
                errors.append(f"{row['app']} {row['office']} on macOS ({key}): HST runs {on_mac or 'nothing'}, "
                              f"the table says {'/'.join(row['uno'])}")


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
