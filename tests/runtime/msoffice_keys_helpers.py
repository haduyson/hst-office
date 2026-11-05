# SPDX-License-Identifier: AGPL-3.0-only
"""Small steps shared by the Word key checks."""
from shortcut_keys import check


def dialog_check(office, keys, combo, name):
    found = keys.dialog_after(combo)
    check(f"{name} ({combo} opens a dialog)", found is not None)
    if found:
        print(f"      dialog title: {found[1]!r}")
        keys.close_dialog(found[0])
    office.raise_windows()


def iterate(text):
    enum = text.createEnumeration()
    while enum.hasMoreElements():
        yield enum.nextElement()


def text_field_count(fields):
    enum, n = fields.createEnumeration(), 0
    while enum.hasMoreElements():
        enum.nextElement()
        n += 1
    return n
