# SPDX-License-Identifier: LicenseRef-HST-Proprietary
# Copyright (C) 2026 HASON TECH
"""Trộn thư, Word fields: the numeric picture switch \\# with Word's rules (ECMA-376 17.16.4.3). Pure Python.

  0 digit, # digit or a space, x drops digits, "." / "," radix and grouping, - + sign, 'text' literal, other
  characters as they are, "pos;neg" and "pos;neg;zero" sections.

Word reads "." and "," in a picture with the computer's separators. A picture shows what its author saw, so it is
read in the convention it is written in: "#,##0.00" groups with "," (1,500,000.00), "#.##0,00" with "."
(1.500.000,00); a lone separator followed by exactly three digit places after a "#" groups ("#,##0", "#.##0")."""
import re
from decimal import ROUND_HALF_UP, Decimal

PLACES = "0#x"
_NUMBER = re.compile(r"[+-]?(\d+([.,]\d+)?|\d{1,3}([.,]\d{3})+([.,]\d+)?)")


def to_number(value):
    """A float for a number or a text that reads as one ("1500000", "1.500.000", "1,234.5", "8250000,5"), else
    None."""
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return float(value)
    text = str(value or "").strip().replace(" ", "")
    if not _NUMBER.fullmatch(text):
        return None
    dots, commas = text.count("."), text.count(",")
    if dots and commas:  # the later one is the radix
        radix = "." if text.rfind(".") > text.rfind(",") else ","
    elif dots + commas == 1:
        mark = "." if dots else ","
        whole, _, fraction = text.lstrip("+-").partition(mark)
        radix = None if len(fraction) == 3 and whole not in ("", "0") else mark
    else:
        radix = None  # 1.500.000 or 1,500,000: grouping only
    group = {".": ",", ",": ".", None: None}[radix] if radix else ("." if dots else ",")
    text = text.replace(group, "") if group else text
    return float(text.replace(radix, ".") if radix else text)


def _split_sections(picture):
    sections, current, quoted = [], "", False
    for char in picture:
        if char == "'":
            quoted = not quoted
        if char == ";" and not quoted:
            sections.append(current)
            current = ""
        else:
            current += char
    return sections + [current]


def _items(section):
    """[(kind, text)]: ("lit", text) for literals, ("ph", c) for 0 # x, ("sep", c) for . and , ("sign", c)."""
    items, index = [], 0
    while index < len(section):
        char = section[index]
        if char == "'":
            end = section.find("'", index + 1)
            end = len(section) if end < 0 else end
            items.append(("lit", section[index + 1:end]))
            index = end + 1
            continue
        kind = "ph" if char in PLACES else "sep" if char in ".," else "sign" if char in "+-" else "lit"
        items.append((kind, char))
        index += 1
    return items


def _separators(items):
    """(group, radix) characters of the numeric part of a section."""
    seps = [(i, c) for i, (k, c) in enumerate(items) if k == "sep"]
    marks = {c for _, c in seps}
    if len(marks) == 2:
        radix = seps[-1][1]
        return ("," if radix == "." else "."), radix
    if not seps:
        return None, None
    index, mark = seps[0]
    before = [c for k, c in items[:index] if k == "ph"]
    after = []
    for kind, char in items[index + 1:]:
        if kind != "ph":
            break
        after.append(char)
    if len(seps) > 1 or (len(after) == 3 and before[:1] == ["#"]):
        return mark, None
    return None, mark


def _whole_part(digits, places, group):
    """The integer part: digits right-aligned over the places; "0" pads with 0, "#" with a space, "x" drops."""
    if "x" in places:
        digits = digits[-(len(places) - places.index("x")):] if digits else digits
    cells = []
    for position in range(max(len(digits), len(places))):
        place = places[-1 - position] if position < len(places) else "0"
        cells.append(digits[-1 - position] if position < len(digits) else {"0": "0", "#": " "}.get(place, ""))
    text = ""
    for position, cell in enumerate(cells):
        if group and position and position % 3 == 0:
            text = (group if cell.strip() else "") + text  # Word: no separator, and no space, without a digit
        text = cell + text
    return text


def format_number(value, picture):
    """`value` (float) through a Word numeric picture."""
    sections = _split_sections(picture)
    if value < 0 and len(sections) > 1:
        section, value, signed = sections[1], abs(value), True
    elif value == 0 and len(sections) > 2:
        section, signed = sections[2], False
    else:
        section, signed = sections[0], False
    items = _items(section)
    places = [i for i, (k, _) in enumerate(items) if k == "ph"]
    if not places:
        return "".join(c for _, c in items)
    group, radix = _separators(items)
    first, last = places[0], places[-1]
    radix_at = next((i for i, (k, c) in enumerate(items) if k == "sep" and c == radix), None)
    first = first if radix_at is None else min(first, radix_at)
    whole_places = "".join(c for i, (k, c) in enumerate(items) if k == "ph" and (radix_at is None or i < radix_at))
    fraction_places = "".join(c for i, (k, c) in enumerate(items) if k == "ph" and radix_at is not None and i > radix_at)
    amount = Decimal(str(abs(value))).quantize(Decimal(1).scaleb(-len(fraction_places)), rounding=ROUND_HALF_UP)
    whole, _, fraction = (format(amount, "f") if fraction_places else str(int(amount))).partition(".")
    number = _whole_part("" if whole == "0" and "0" not in whole_places and amount else whole, whole_places, group)
    if fraction_places:
        digits = fraction[:len(fraction_places)].rstrip("0")
        number += radix + "".join(digits[i] if i < len(digits) else {"0": "0", "#": " "}.get(p, "")
                                  for i, p in enumerate(fraction_places))
    has_sign = any(k == "sign" for k, _ in items)
    out = ""
    for index, (kind, char) in enumerate(items):
        if index == first:
            if value < 0 and not has_sign and not signed and amount:  # the minus goes right before the digits
                spaces = len(number) - len(number.lstrip(" "))
                number = number[:spaces] + "-" + number[spaces:]
            out += number
        elif first < index <= last and kind in ("ph", "sep"):
            continue
        elif kind == "sign":
            negative = value < 0 and amount
            out += ("-" if negative else " ") if char == "-" else ("-" if negative else "+" if amount else " ")
        else:
            out += char
    return out
