# SPDX-License-Identifier: AGPL-3.0-only
"""Trộn thư ▸ Quy tắc, the address block and the greeting as computed columns of the staging copy. Pure Python.

Rules live in the document (mail_merge_store meta "rules", "skip"):
  {"type": "if", "name", "column", "op", "value", "then", "else"}  -> column "Nếu: <name>" (texts may hold {Cột})
  {"type": "ask", "name", "prompt", "value"}                       -> column "Hỏi: <name>", asked once per merge
  {"type": "seq", "name", "start"}                                 -> column "<name>": 1, 2, 3 ... in merge order
  skip: [{"column", "op", "value"}]   "Bỏ qua bản ghi nếu": matching recipients are left out of preview and output
The engine merges these columns like any other, so preview and output always agree."""
from . import mail_merge_address as address
from . import mail_merge_format as fmt
from . import mail_merge_table as mt
from .vietnamese_text import remove_diacritics

OPS = ("eq", "ne", "contains", "not_contains", "empty", "not_empty", "gt", "lt")
NO_VALUE = ("empty", "not_empty")
BLOCK_COLUMN, GREETING_COLUMN = "Khối địa chỉ", "Dòng chào"
PREFIX = {"if": "Nếu: ", "ask": "Hỏi: ", "seq": ""}


def _fold(text):
    return " ".join(remove_diacritics(str(text)).casefold().split())


def _number(table, row, column, wanted):
    """(value, wanted) as numbers when the column holds numbers or dates and `wanted` reads as one, else None."""
    from .mail_merge_source import csv_cell
    kind = table.kind(column)
    value = table.value(row, column)
    target = csv_cell(str(wanted))
    if kind in (fmt.COL_NUMBER, fmt.COL_DATE) and isinstance(value, float) and target[0] in (fmt.COL_NUMBER, fmt.COL_DATE):
        return value, target[1]
    return None


def matches(table, row, condition):
    """Whether the row meets {"column", "op", "value"}; a missing column never matches. Text compares without case
    or diacritics ("nu" = "Nữ"); numbers and dates compare by value ("1.000.000", "01/01/1990")."""
    column, op, wanted = condition.get("column"), condition.get("op", "eq"), condition.get("value", "")
    if column not in table.headers or op not in OPS:
        return False
    text = table.text(row, column).strip()
    if op in NO_VALUE:
        return (text == "") == (op == "empty")
    numbers = _number(table, row, column, wanted)
    if op in ("gt", "lt"):
        if numbers is None:
            return False
        return numbers[0] > numbers[1] if op == "gt" else numbers[0] < numbers[1]
    if op in ("eq", "ne"):
        same = numbers[0] == numbers[1] if numbers else _fold(text) == _fold(wanted)
        return same == (op == "eq")
    inside = _fold(wanted) in _fold(text)
    return inside == (op == "contains")


def skipped(table, row, conditions):
    return any(matches(table, row, condition) for condition in conditions or ())


def rule_column(rule):
    return PREFIX.get(rule.get("type"), "") + rule.get("name", "")


def valid_rules(rules):
    return [r for r in rules or () if isinstance(r, dict) and r.get("type") in PREFIX and r.get("name")]


def _rule_function(rule, table):
    kind = rule["type"]
    if kind == "if":
        return lambda row, position: mt.fill(rule.get("then" if matches(table, row, rule) else "else", ""), table, row)
    if kind == "ask":
        return lambda row, position: str(rule.get("value", ""))
    start = int(rule.get("start", 1) or 1)
    return lambda row, position: str(start + position - 1)


def extra_columns(meta, table):
    """[(column name, function(row, position))] of the address block, the greeting and every rule."""
    extra = []
    block = address.settings(meta.get("block"), table.headers, address.BLOCK_DEFAULT)
    greeting = address.settings(meta.get("greeting"), table.headers, address.GREETING_DEFAULT)
    if block.get("name") or meta.get("block"):
        extra.append((BLOCK_COLUMN, lambda row, position: address.address_block(table, row, block)))
    if greeting.get("name") or meta.get("greeting"):
        extra.append((GREETING_COLUMN, lambda row, position: address.greeting(table, row, greeting)))
    for rule in valid_rules(meta.get("rules")):
        extra.append((rule_column(rule), _rule_function(rule, table)))
    return extra


def upsert(rules, rule):
    """The rule list with `rule` added, or replacing the rule of the same type and name."""
    kept = [r for r in valid_rules(rules) if (r["type"], r["name"]) != (rule["type"], rule["name"])]
    return kept + [rule]
