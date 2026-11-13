# SPDX-License-Identifier: AGPL-3.0-only
"""CSL-JSON dates: parse what importers and users type into ``{"date-parts": [[y, m, d]]}``. Pure Python (no uno).

Accepted: "2010", "2010-05-07", "2010/05/07/" (RIS), "2010/05", "07/05/2010" (Vietnamese day first), "May 7, 2010",
"7 May 2010", "2010 May 7" and "2010 Jan-Feb" (PubMed), "ngày 7 tháng 5 năm 2010", "2010-2011" (a range).
Anything else is kept as ``{"literal": text}`` so nothing the user typed is lost.
"""
import re

from .citation_terms import MONTHS_EN

_MONTHS = {m.lower(): i + 1 for i, m in enumerate(MONTHS_EN)}
_MONTHS.update({m.lower()[:3]: i + 1 for i, m in enumerate(MONTHS_EN)})
_MONTHS.update({"sept": 9})
_YEAR = r"(1[0-9]{3}|20[0-9]{2}|2100)"
_VN = re.compile(r"(?:ngày\s*)?(\d{1,2})\s*tháng\s*(\d{1,2})\s*,?\s*năm\s*" + _YEAR, re.I)
_ISO = re.compile(r"^" + _YEAR + r"(?:[-/.](\d{1,2})(?:[-/.](\d{1,2}))?)?[-/.]*(?:T[0-9:.Z+-]*)?$")
_DMY_NUM = re.compile(r"^(\d{1,2})[/.-](\d{1,2})[/.-]" + _YEAR + "$")
_RANGE = re.compile(r"^" + _YEAR + r"\s*[-–/]\s*" + _YEAR + "$")
_WORDS = re.compile(r"[A-Za-z]+|\d+")


def _parts(year, month=0, day=0):
    parts = [int(year)]
    if month and 1 <= int(month) <= 12:
        parts.append(int(month))
        if day and 1 <= int(day) <= 31:
            parts.append(int(day))
    return parts


def parse(text):
    """CSL date object for the text ({} when empty or "n.d.")."""
    text = (text or "").strip().strip(",;")
    if not text or text.lower() in ("n.d.", "nd", "n. d.", "không năm", "không ngày", "k.n."):
        return {}
    if re.match(_YEAR + "/", text):
        text = "/".join(text.split("/")[:3])  # RIS "2010/05/07/Spring": the fourth part is free text
    match = _ISO.match(text)
    if match:
        year, month, day = match.group(1), int(match.group(2) or 0), int(match.group(3) or 0)
        return {"date-parts": [_parts(year, month, day)]}
    match = _RANGE.match(text)
    if match:
        return {"date-parts": [[int(match.group(1))], [int(match.group(2))]]}
    match = _DMY_NUM.match(text)
    if match:
        return {"date-parts": [_parts(match.group(3), int(match.group(2)), int(match.group(1)))]}
    match = _VN.search(text)
    if match:
        return {"date-parts": [_parts(match.group(3), int(match.group(2)), int(match.group(1)))]}
    return _words(text)


def _month(token):
    key = token.lower()
    return _MONTHS.get(key) or (_MONTHS.get(key[:3]) if len(key) >= 3 else 0) or 0


def _words(text):
    """Dates written with an English month name; extra words (a season, "Jan-Feb") keep only what is clear."""
    tokens = _WORDS.findall(text)
    year = next((t for t in tokens if re.fullmatch(_YEAR, t)), None)
    if not year:
        return {"literal": text}
    month = next((_month(t) for t in tokens if t.isalpha() and _month(t)), 0)
    day = next((int(t) for t in tokens if t.isdigit() and t != year and 1 <= int(t) <= 31), 0) if month else 0
    return {"date-parts": [_parts(year, month, day)]}


def normalize(value):
    """A clean CSL date object from a CSL date, a string or a bare year; None when the value is unusable."""
    if value is None or value == "":
        return None
    if isinstance(value, int):
        return {"date-parts": [[value]]}
    if isinstance(value, str):
        return parse(value) or None
    if not isinstance(value, dict):
        return None
    result = {}
    parts = value.get("date-parts")
    if isinstance(parts, list):
        clean = []
        for part in parts[:2]:
            if not isinstance(part, list) or not part:
                continue
            try:
                numbers = [int(str(p).strip()) for p in part[:3] if str(p).strip()]
            except ValueError:
                continue
            if numbers:
                clean.append(_parts(*numbers) if len(numbers) <= 3 else numbers[:1])
        if clean:
            result["date-parts"] = clean
    for key in ("literal", "season", "circa"):
        if value.get(key) not in (None, ""):
            result[key] = value[key] if key != "literal" else str(value[key])
    if "date-parts" not in result and value.get("raw"):
        result.update(parse(str(value["raw"])))
    return result or None


def year(date):
    """First year of a CSL date, or None."""
    try:
        return int(date["date-parts"][0][0])
    except (KeyError, IndexError, TypeError, ValueError):
        return None


def parts(date):
    """(year, month, day) of the first date; missing parts are 0."""
    try:
        values = list(date["date-parts"][0]) + [0, 0]
        return int(values[0]), int(values[1] or 0), int(values[2] or 0)
    except (KeyError, IndexError, TypeError, ValueError):
        return 0, 0, 0
