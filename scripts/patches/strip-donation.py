# SPDX-License-Identifier: AGPL-3.0-only
"""Remove every user-visible "Donate" entry point from a LibreOffice source tree.

Usage: python3 scripts/patches/strip-donation.py <tree-root> [file ...]

HST Office decision (owner, 2026-10-29): nothing about donating to LibreOffice
is shown. This script edits a tree so patches/libreoffice/hst-remove-donation.patch
can be regenerated for a new LibreOffice version:
- menu XML: drop `<menu:menuitem menu:id=".uno:Donation"/>` lines;
- NotebookBar .ui: drop the `<child>` block holding the `.uno:Donation` menu item.
Every file named must change, so an upstream layout change fails loudly.
The Start Center button/banner are handled in hst-start-center-banner.patch.
"""
import os
import re
import sys

MENU_LINE = re.compile(r'^[ \t]*<menu:menuitem menu:id="\.uno:Donation"[^>]*/>[ \t]*\n', re.M)
UI_CHILD = re.compile(
    r'^[ \t]*<child>\s*<object class="GtkMenuItem" id="[^"]*">'
    r'(?:\s*<property name="[^"]+">[^<]*</property>)*?'
    r'\s*<property name="action[-_]name">\.uno:Donation</property>'
    r'(?:\s*<property name="[^"]+">[^<]*</property>)*'
    r'\s*</object>\s*</child>[ \t]*\n', re.M)
# After removal two separator children can become adjacent; keep only the first.
DOUBLE_SEPARATOR = re.compile(
    r'(<child>\s*<object class="GtkSeparatorMenuItem" id="[^"]*">(?:\s*<property name="[^"]+">[^<]*</property>)*'
    r'\s*</object>\s*</child>[ \t]*\n)[ \t]*<child>\s*<object class="GtkSeparatorMenuItem" id="[^"]*">'
    r'(?:\s*<property name="[^"]+">[^<]*</property>)*\s*</object>\s*</child>[ \t]*\n')


def strip(text, path):
    pattern = MENU_LINE if path.endswith(".xml") else UI_CHILD
    result, count = pattern.subn("", text)
    if count == 0 or ".uno:Donation" in result:
        raise SystemExit(f"{path}: Donation entry not removed cleanly ({count} matches)")
    if path.endswith(".ui"):
        result = DOUBLE_SEPARATOR.sub(r"\1", result)
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
                        if ".uno:Donation" in handle.read():
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
