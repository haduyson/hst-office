# SPDX-License-Identifier: AGPL-3.0-only
"""Trộn thư ▸ Kiểm tra lỗi: simulate the merge on the effective rows (the staging copy: checked recipients in order,
with computed columns) and list what would come out wrong. Pure Python.

Problems (code, position from 1 or 0 for the whole document, column, value):
  missing-column  a field of the document reads a column the list does not have (shown as <Cột> in every copy)
  empty           a field would be empty for that recipient
  bad-mail        the e-mail column holds something that is not an e-mail address (only when e-mail is chosen)
  same-file       two recipients would get the same file name (the second gets a number)
  no-recipient    nobody is checked
  no-field        the document has no merge field: every copy is the same"""
import re

from . import mail_merge_format as fmt

MAIL = re.compile(r"[^@\s,;<>]+@[^@\s,;<>]+\.[^@\s,;<>.]{2,}")
LIMIT = 500  # problems listed at most (the dialog says how many more)


def problems(table, used_columns, mail_column="", file_names=()):
    """List of (code, position, column, value) for the effective `table` (headers + rows in merge order)."""
    found = []
    if not table.rows:
        return [("no-recipient", 0, "", "")]
    if not used_columns:
        found.append(("no-field", 0, "", ""))
    columns = []
    for column in used_columns:
        base = fmt.split_word_column(column)[0] if column not in table.headers else column
        if base not in table.headers:
            found.append(("missing-column", 0, column, ""))
        elif base not in columns:
            columns.append(base)
    for position, row in enumerate(table.rows, 1):
        for column in columns:
            if table.text(row, column).strip() == "":
                found.append(("empty", position, column, ""))
        if mail_column and mail_column in table.headers:
            value = table.text(row, mail_column).strip()
            if not MAIL.fullmatch(value):
                found.append(("bad-mail", position, mail_column, value))
    seen = {}
    for position, name in enumerate(file_names, 1):
        key = name.lower()
        if key in seen:
            found.append(("same-file", position, "", name))
        seen.setdefault(key, position)
    return found


def lines(found, texts, name_of=None):
    """Readable lines, e.g. "Người 3 (Phạm Đức Đạt): trường «Địa chỉ» trống". `name_of(position)`: who it is."""
    result = []
    for code, position, column, value in found[:LIMIT]:
        who = texts["chk.whole"] if position == 0 else texts["chk.person"] % position
        if position and name_of:
            label = name_of(position)
            who += " (%s)" % label if label else ""
        result.append("%s: %s" % (who, texts["chk." + code] % {"column": column, "value": value}))
    if len(found) > LIMIT:
        result.append(texts["chk.more"] % (len(found) - LIMIT))
    return result
