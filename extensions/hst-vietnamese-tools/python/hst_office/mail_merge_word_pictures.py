# SPDX-License-Identifier: LicenseRef-HST-Proprietary
# Copyright (C) 2026 HASON TECH
"""Trộn thư, Word fields: the date picture switch \\@ and the format switch \\* with Word's rules (ECMA-376 17.16.4).
Pure Python. The numeric picture \\# is in mail_merge_word_numbers.

  \\@ d dd ddd dddd, M MM MMM MMMM, yy yyyy, H HH h hh, m mm, s ss, AM/PM am/pm, 'text'
  \\* Upper, Lower, Caps, FirstCap, Arabic, roman, ROMAN, alphabetic, ALPHABETIC"""
import datetime
import re
from decimal import ROUND_HALF_UP, Decimal

from .mail_merge_word_numbers import format_number, to_number  # noqa: F401 - one place for the field code

NULL_DATE = datetime.date(1899, 12, 30)
MONTHS = {"vi": ["tháng %d" % m for m in range(1, 13)],
          "en": ["January", "February", "March", "April", "May", "June", "July", "August", "September", "October",
                 "November", "December"]}
MONTHS_SHORT = {"vi": ["thg %d" % m for m in range(1, 13)], "en": [m[:3] for m in MONTHS["en"]]}
DAYS = {"vi": ["Thứ Hai", "Thứ Ba", "Thứ Tư", "Thứ Năm", "Thứ Sáu", "Thứ Bảy", "Chủ Nhật"],
        "en": ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]}
DAYS_SHORT = {"vi": ["Th 2", "Th 3", "Th 4", "Th 5", "Th 6", "Th 7", "CN"], "en": [d[:3] for d in DAYS["en"]]}


def to_date(value):
    """A datetime for a spreadsheet day number or a dd/mm/yyyy (or yyyy-mm-dd) text, else None."""
    if isinstance(value, datetime.datetime):
        return value
    if isinstance(value, datetime.date):
        return datetime.datetime(value.year, value.month, value.day)
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        try:
            return datetime.datetime.combine(NULL_DATE, datetime.time()) + datetime.timedelta(days=float(value))
        except OverflowError:
            return None
    text = str(value or "").strip()
    for pattern in ("%d/%m/%Y", "%d-%m-%Y", "%d.%m.%Y", "%Y-%m-%d", "%d/%m/%Y %H:%M", "%d/%m/%Y %H:%M:%S"):
        try:
            return datetime.datetime.strptime(text, pattern)
        except ValueError:
            continue
    return None


_DATE_TOKEN = re.compile(r"'[^']*'|AM/PM|am/pm|A/P|a/p|([dDyY])\1*|M{1,4}|H{1,2}|h{1,2}|m{1,2}|s{1,2}|.", re.S)


def format_date(moment, picture, language="vi"):
    """A datetime through a Word date-time picture ("dd/MM/yyyy", "'ngày' dd 'tháng' MM 'năm' yyyy")."""
    names = language if language in MONTHS else "vi"
    out = []
    for match in _DATE_TOKEN.finditer(picture):
        token = match.group(0)
        lower = token.lower()
        if token.startswith("'"):
            out.append(token[1:-1])
        elif lower[0] == "d":
            out.append({1: str(moment.day), 2: "%02d" % moment.day, 3: DAYS_SHORT[names][moment.weekday()]}
                       .get(len(token), DAYS[names][moment.weekday()]))
        elif lower[0] == "y":
            out.append("%02d" % (moment.year % 100) if len(token) <= 2 else "%04d" % moment.year)
        elif token[0] == "M":
            out.append({1: str(moment.month), 2: "%02d" % moment.month, 3: MONTHS_SHORT[names][moment.month - 1]}
                       .get(len(token), MONTHS[names][moment.month - 1]))
        elif token[0] in "Hh":
            hour = moment.hour if token[0] == "H" else (moment.hour % 12 or 12)
            out.append(str(hour) if len(token) == 1 else "%02d" % hour)
        elif token[0] in "ms" and token in ("m", "mm", "s", "ss"):
            part = moment.minute if token[0] == "m" else moment.second
            out.append(str(part) if len(token) == 1 else "%02d" % part)
        elif lower in ("am/pm", "a/p"):
            text = "AM" if moment.hour < 12 else "PM"
            text = text if lower == "am/pm" else text[0]
            out.append(text if token[0].isupper() else text.lower())
        else:
            out.append(token)
    return "".join(out)


def _roman(number):
    pairs = ((1000, "M"), (900, "CM"), (500, "D"), (400, "CD"), (100, "C"), (90, "XC"), (50, "L"), (40, "XL"),
             (10, "X"), (9, "IX"), (5, "V"), (4, "IV"), (1, "I"))
    out = ""
    for amount, letters in pairs:
        while number >= amount:
            out, number = out + letters, number - amount
    return out


def _alphabetic(number):
    letter = chr(ord("A") + (number - 1) % 26)
    return letter * ((number - 1) // 26 + 1)


def format_text(text, kind):
    """A \\* format switch: case for text, Arabic / roman / alphabetic for whole numbers; others leave it."""
    key = kind.lower()
    if key == "upper":
        return text.upper()
    if key == "lower":
        return text.lower()
    if key == "caps":  # each word: first letter up, the rest down (fixes names typed in capitals)
        return re.sub(r"\w+", lambda m: m.group(0)[:1].upper() + m.group(0)[1:].lower(), text)
    if key == "firstcap":
        return text[:1].upper() + text[1:]
    number = to_number(text)
    if key in ("arabic", "roman", "alphabetic") and number is not None and number >= 1:
        whole = int(Decimal(str(number)).quantize(Decimal(1), rounding=ROUND_HALF_UP))
        if key == "arabic":
            return str(whole)
        result = _roman(whole) if key == "roman" else _alphabetic(whole)
        return result.lower() if kind[0].islower() else result
    return text

