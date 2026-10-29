# SPDX-License-Identifier: AGPL-3.0-only
"""Remove the Help-menu entries that lead to online services from a LibreOffice source tree.

Usage: python3 scripts/patches/strip-donation.py <tree-root> [file ...]

HST Office decisions (owner, 2026-10-29): nothing about donating, no "Send Feedback"
and no "Get Involved" entry (they pointed at a repository website that may move).
This script edits a tree so patches/libreoffice/hst-remove-donation.patch can be
regenerated for a new LibreOffice version. For each command in COMMANDS:
- menu XML: drop `<menu:menuitem menu:id=".uno:<Command>"/>` lines;
- NotebookBar .ui: drop the `<child>` block holding the `.uno:<Command>` menu item;
- adjacent separators left behind are collapsed to one.
Every file named must change, so an upstream layout change fails loudly.
The Start Center button/banner are handled in hst-start-center-banner.patch.
"""
import os
import re
import sys

COMMANDS = ("Donation", "SendFeedback", "GetInvolved")
ANY_COMMAND = "|".join(COMMANDS)
MENU_LINE = re.compile(rf'^[ \t]*<menu:menuitem menu:id="\.uno:(?:{ANY_COMMAND})"[^>]*/>[ \t]*\n', re.M)
# Removed items are replaced by a marker line first, so only separators made adjacent by
# the removal are collapsed (upstream's own layout elsewhere stays untouched).
MARKER = "@@removed@@\n"
MENU_SEPARATOR_AROUND_MARKER = re.compile(
    r'(^[ \t]*<menu:menuseparator/>[ \t]*\n)(?:@@removed@@\n)+[ \t]*<menu:menuseparator/>[ \t]*\n', re.M)
UI_CHILD = re.compile(
    r'^[ \t]*<child>\s*<object class="GtkMenuItem" id="[^"]*">'
    r'(?:\s*<property name="[^"]+">[^<]*</property>)*?'
    rf'\s*<property name="action[-_]name">\.uno:(?:{ANY_COMMAND})</property>'
    r'(?:\s*<property name="[^"]+">[^<]*</property>)*'
    r'\s*</object>\s*</child>[ \t]*\n', re.M)
# After removal two separator children can become adjacent; keep only the first.
DOUBLE_SEPARATOR = re.compile(
    r'(<child>\s*<object class="GtkSeparatorMenuItem" id="[^"]*">(?:\s*<property name="[^"]+">[^<]*</property>)*'
    r'\s*</object>\s*</child>[ \t]*\n)[ \t]*<child>\s*<object class="GtkSeparatorMenuItem" id="[^"]*">'
    r'(?:\s*<property name="[^"]+">[^<]*</property>)*\s*</object>\s*</child>[ \t]*\n')


def strip(text, path):
    is_xml = path.endswith(".xml")
    result, count = (MENU_LINE if is_xml else UI_CHILD).subn(MARKER if is_xml else "", text)
    if count == 0 or any(f".uno:{name}" in result for name in COMMANDS):
        raise SystemExit(f"{path}: entries not removed cleanly ({count} matches)")
    if path.endswith(".ui"):
        previous = None
        while previous != result:  # three or more adjacent separators need repeated passes
            previous, result = result, DOUBLE_SEPARATOR.sub(r"\1", result)
    else:
        previous = None
        while previous != result:
            previous, result = result, MENU_SEPARATOR_AROUND_MARKER.sub(r"\1", result)
        result = result.replace(MARKER, "")
    return result


def main(argv):
    if not argv:
        raise SystemExit(__doc__)
    root, files = argv[0], argv[1:]
    if not files:
        files = []
        for dirpath, dirnames, filenames in os.walk(root):
            dirnames[:] = [d for d in dirnames if d not in {"workdir", "instdir", "external"}]
            for name in filenames:
                if name.endswith((".xml", ".ui")):
                    path = os.path.join(dirpath, name)
                    with open(path, encoding="utf-8") as handle:
                        content = handle.read()
                    if any(f".uno:{command}" in content for command in COMMANDS):
                        files.append(os.path.relpath(path, root))
    for rel in sorted(files):
        path = os.path.join(root, rel)
        with open(path, encoding="utf-8") as handle:
            text = handle.read()
        with open(path, "w", encoding="utf-8") as handle:
            handle.write(strip(text, rel))
        print(f"stripped {rel}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
