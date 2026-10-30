#!/usr/bin/env python3
# SPDX-License-Identifier: AGPL-3.0-only
"""Make the Windows installer (MSI) text Vietnamese whatever the Windows display language.

  python3 scripts/windows/msi-vietnamese-base.py --tree <libreoffice-src> [--check]

Why: the multilingual MSI (en-US,vi) uses en-US as its base database and embeds vi as a
language transform (msiglobal.pm create_transforms) that Windows Installer only applies on a
Vietnamese display language. So on English Windows every dialog is English. This script
writes the Vietnamese installer strings into the en-US slots of the installer string sources
before the build, so the base database is Vietnamese too; the vi transform keeps carrying the
same text. Only installer-UI strings are rewritten:
- instsetoo_native/inc_openoffice/windows/msi_languages/*.ulf (dialogs, buttons, progress,
  errors, launch conditions, custom-action messages, the dialog title suffix);
- scp2/source/*/module_*.ulf (Custom Setup feature names and descriptions).
Not touched: Explorer verbs and file-type names in Property.ulf (OS menus follow the OS
language), Start-menu/registry strings, the application UI and its language packs.

Source of truth is the vi .po after scripts/l10n/merge-vi.py and apply-overrides.py, matched
by msgctxt (the HST overrides keep the upstream msgid as key). Fails if a required string has
no Vietnamese translation, or if an en-US string was changed by an HST patch but the vi text
was not reviewed through l10n/vi-overrides.jsonl. Idempotent.
"""
import argparse
import glob
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, os.path.join(ROOT, "scripts", "l10n"))
from po_io import parse_po  # noqa: E402

MSI_PO = "instsetoo_native/inc_openoffice/windows/msi_languages.po"
MSI_ULF = "instsetoo_native/inc_openoffice/windows/msi_languages"
# Property.ulf: only the wizard title suffix is dialog text; ARP values are names/URLs.
PROPERTY_KEYS = {"OOO_STR_INSTALLATION_WIZARD"}
# Values that are not words (placeholders, units, layout) stay as they are.
NEUTRAL = re.compile(r"^(?:\[[^\]]*\]|\{[^}]*\}|[\s{}\[\],0-9]|OK|&OK|KB|MB|GB|bytes)*$")
# Feature strings for components never packaged on Windows, or for languages not built.
SKIP_SCP2 = re.compile(r"HELPPACK|_GNOME$|_KDE$|_TDE$|LANGPACK_(?!EN_US$|VI$|ROOT)")
SECTION = re.compile(r"^\[(.+)\]\s*$")
EN_US = re.compile(r'^(\s*en-US\s*=\s*)"(.*)"(\s*)$')
PO_ESCAPES = {"n": "\n", "t": "\t", "\\": "\\", '"': '"'}


def po_unescape(text):
    return re.sub(r'\\(.)', lambda m: PO_ESCAPES.get(m.group(1), "\\" + m.group(1)), text)


def ulf_quote(text):
    """ulf value form read by installer/windows/idtglobal.pm: only quotes are escaped."""
    if "\n" in text:
        raise ValueError(f"newline in installer string: {text!r}")
    return text.replace('"', '\\"')


def reviewed_keys():
    path = os.path.join(ROOT, "l10n", "vi-overrides.jsonl")
    with open(path, encoding="utf-8") as handle:
        return {(r["file"], r["msgctxt"]) for r in map(json.loads, filter(str.strip, handle))}


def rewrite_ulf(path, po_rel, translations, keys_filter, reviewed, problems, check):
    name = os.path.basename(path)
    with open(path, encoding="utf-8") as handle:
        lines = handle.read().split("\n")
    key, changed, done = None, 0, 0
    for index, line in enumerate(lines):
        match = SECTION.match(line)
        if match:
            key = match.group(1)
            continue
        match = EN_US.match(line)
        if not match or not key or not keys_filter(key):
            continue
        current = match.group(2)
        ctx = f"{name}\\n{key}\\nLngText.text"
        entry = translations.get(ctx)
        if NEUTRAL.match(current.replace('\\"', "")) and (not entry or not entry["msgstr"]):
            continue
        if not entry or not entry["msgstr"] or entry["fuzzy"]:
            problems.append(f"{po_rel}: no Vietnamese for {name} [{key}] {current!r}")
            continue
        vi = ulf_quote(po_unescape(entry["msgstr"]))
        source = ulf_quote(po_unescape(entry["msgid"]))
        if current not in (source, vi) and (po_rel, ctx) not in reviewed:
            problems.append(f"{name} [{key}]: en-US changed by an HST patch ({current!r}) but the vi "
                            f"text was not reviewed in l10n/vi-overrides.jsonl")
            continue
        done += 1
        if current != vi:
            lines[index] = f'{match.group(1)}"{vi}"{match.group(3)}'
            changed += 1
    if changed and not check:
        with open(path, "w", encoding="utf-8") as handle:
            handle.write("\n".join(lines))
    return done, changed


def load_po(tree, rel):
    return {e["msgctxt"]: e for e in parse_po(os.path.join(tree, "translations", "source", "vi", rel))}


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--tree", required=True)
    parser.add_argument("--check", action="store_true", help="report only; exit 1 if anything is left in English")
    args = parser.parse_args()
    tree = os.path.abspath(args.tree)
    reviewed, problems = reviewed_keys(), []
    total = changed = 0

    msi = load_po(tree, MSI_PO)
    for path in sorted(glob.glob(os.path.join(tree, MSI_ULF, "*.ulf"))):
        keep = (lambda k: k in PROPERTY_KEYS) if path.endswith("Property.ulf") else (lambda k: True)
        done, n = rewrite_ulf(path, MSI_PO, msi, keep, reviewed, problems, args.check)
        total, changed = total + done, changed + n

    for path in sorted(glob.glob(os.path.join(tree, "scp2", "source", "*", "module_*.ulf"))):
        rel = f"scp2/source/{os.path.basename(os.path.dirname(path))}.po"
        done, n = rewrite_ulf(path, rel, load_po(tree, rel), lambda k: not SKIP_SCP2.search(k),
                              reviewed, problems, args.check)
        total, changed = total + done, changed + n

    for problem in problems:
        print(f"error: {problem}")
    verb = "would change" if args.check else "changed"
    print(f"msi vietnamese base: {total} strings, {verb} {changed}, {len(problems)} errors")
    if problems or (args.check and changed):
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
