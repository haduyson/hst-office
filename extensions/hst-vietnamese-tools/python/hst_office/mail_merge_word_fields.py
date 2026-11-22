# SPDX-License-Identifier: LicenseRef-HST-Proprietary
# Copyright (C) 2026 HASON TECH
"""Trộn thư, Word fields: MERGEFIELD and IF evaluated for one recipient with Word's rules. Pure Python.

A Word mail-merge document opened in HST keeps each field Writer cannot evaluate itself as a database field whose
column name is the Word instruction, nested fields written { … } (the DOCX import, sw/source/writerfilter/hst):

  MERGEFIELD Lương \\# "#,##0"
  IF { MERGEFIELD Giới_tính } = "Nam" "Ông" "Bà"

The staging copy of the recipients gets one computed column per such instruction (mail_merge_word_link), so the
engine merges Word's result, and the Word export writes the instruction back unchanged.

Rules (ECMA-376 17.16): MERGEFIELD name [\\# picture] [\\@ picture] [\\* format] [\\b before] [\\f after]; \\b and \\f
only when the value is not empty. IF a op b true false (op = <> < <= > >=): numbers compare as numbers, other text
compares exactly (with case); with = and <> the second text may hold * and ? wildcards. "IF value true false" is
true for a number other than 0. A field name matches a column also when Word wrote spaces as "_" ("Họ_và_tên")."""
import re

from . import mail_merge_format as fmt
from . import mail_merge_word_pictures as pictures
from .mail_merge_word_parse import (  # noqa: F401 - the field functions callers use
    Field, _plain, is_word_code, merge_names, name_key, names_text, parse)

OPERATORS = ("=", "<>", "<", "<=", ">", ">=")


class Record:
    """One recipient: `lookup(name)` -> (value, column kind) or None for an unknown name; `position` from 1."""

    def __init__(self, lookup, position=1, language="vi"):
        self.lookup, self.position, self.language = lookup, position, language


def table_lookup(table, row):
    """lookup() over a mail_merge_table.Table row: exact header first, else Word's name rules."""
    keys = {}
    for header in table.headers:
        keys.setdefault(name_key(header), header)

    def lookup(name):
        header = name if name in table.headers else keys.get(name_key(name))
        return None if header is None else (table.value(row, header), table.kind(header))
    return lookup


def general(value, kind):
    """A value without switches: text as it is, numbers as typed (1500000, 8250000,5), dates dd/MM/yyyy."""
    if value is None or value == "":
        return ""
    if isinstance(value, str):
        return value
    if kind == fmt.COL_DATE:
        moment = pictures.to_date(value)
        return pictures.format_date(moment, "dd/MM/yyyy") if moment else fmt.plain_number(value)
    return fmt.plain_number(value)


def token_text(token, record):
    return "".join(p if isinstance(p, str) else evaluate(p, record) for p in token[0])


def evaluate(field, record):
    """The text Word shows for `field` and this recipient."""
    if field.kind == "MERGEFIELD":
        arguments = field.arguments
        found = record.lookup(token_text(arguments[0], record)) if arguments else None
        value, kind = found if found else (None, fmt.COL_TEXT)
        return _switches(field, record, general(value, kind), value, kind, merge=True)
    if field.kind == "IF":
        return _switches(field, record, _if(field, record), None, fmt.COL_TEXT)
    if field.kind in ("MERGEREC", "MERGESEQ"):
        return _switches(field, record, str(record.position), record.position, fmt.COL_NUMBER)
    return ""


def _switches(field, record, text, value, kind, merge=False):
    before = after = ""
    for letter, argument in field.switches():
        argument = token_text(argument, record) if argument else ""
        if letter == "#":
            number = value if isinstance(value, float) and kind == fmt.COL_NUMBER else pictures.to_number(text)
            text = pictures.format_number(number, argument) if number is not None and text != "" else text
        elif letter == "@":
            moment = pictures.to_date(value if kind == fmt.COL_DATE and value is not None else text)
            text = pictures.format_date(moment, argument, record.language) if moment and text != "" else text
        elif letter == "*":
            text = pictures.format_text(text, argument)
        elif letter == "b" and merge:
            before = argument
        elif letter == "f" and merge:
            after = argument
    return before + text + after if text != "" else text


def _wildcard(pattern):
    return re.compile("".join(".*" if c == "*" else "." if c == "?" else re.escape(c) for c in pattern), re.S)


def compare(left, operator, right):
    """Word's IF comparison of two texts."""
    numbers = pictures.to_number(left), pictures.to_number(right)
    if None not in numbers:
        a, b = numbers
    elif operator in ("=", "<>") and ("*" in right or "?" in right):
        same = bool(_wildcard(right).fullmatch(left))
        return same if operator == "=" else not same
    else:
        a, b = left, right
    return {"=": a == b, "<>": a != b, "<": a < b, "<=": a <= b, ">": a > b, ">=": a >= b}[operator]


def _if(field, record):
    texts = [token_text(token, record) for token in field.arguments]
    plain = [_plain(token) if not token[1] and all(isinstance(p, str) for p in token[0]) else None
             for token in field.arguments]
    if len(texts) >= 3 and plain[1] in OPERATORS:
        outcome = compare(texts[0], plain[1], texts[2])
        rest = texts[3:]
    elif texts:
        number = pictures.to_number(texts[0])
        outcome, rest = bool(number), texts[1:]
    else:
        return ""
    rest = rest + ["", ""]
    return rest[0] if outcome else rest[1]


def evaluate_code(code, record):
    """evaluate() of an instruction text; an instruction that cannot be read gives ""."""
    try:
        return evaluate(parse(code), record)
    except (ValueError, IndexError):
        return ""
