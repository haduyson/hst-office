# SPDX-License-Identifier: AGPL-3.0-only
""""Chèn lại trích dẫn" by number: read what the user typed just before the cursor and map numbers to sources.
Pure Python (no uno).

The user types the number of a source already in the bibliography, the way theses cite, and presses Alt+Shift+I:
    [3        [3]        [3, tr. 15]        [3–5]        [3, 7]        [3, 7, tr. 15-16]        [12, p. 4]
The typed text is replaced by a real citation of those sources (with the page as locator). The number is the
source's position in the bibliography as it is now (for numeric styles exactly the printed number).
"""
import re

MAX_SOURCES = 30
_NUM = r"\d{1,4}(?:\s*[-–]\s*\d{1,4})?"
_LABELS = {"tr": "page", "trang": "page", "p": "page", "pp": "page", "page": "page", "tập": "volume",
           "vol": "volume", "chương": "chapter", "ch": "chapter"}
TYPED = re.compile(
    r"\[\s*(?P<nums>" + _NUM + r"(?:\s*[,;]\s*" + _NUM + r")*)"
    r"(?:\s*,\s*(?P<label>tr|trang|pp|p|page|tập|vol|chương|ch)\.?\s*(?P<loc>[0-9ivxlcIVXLC][0-9ivxlcIVXLC\s,–-]{0,30}?))?"
    r"\s*\]?$")


def parse_typed(text):
    """{"numbers": [3, 4, 5], "locator": "15", "label": "page", "length": n} for the typed citation that ends
    ``text`` (the paragraph up to the cursor), or None. ``length`` is how many characters to replace."""
    if not text:
        return None
    tail = text[-80:]
    match = TYPED.search(tail)
    if not match:
        return None
    numbers = []
    for part in re.split(r"\s*[,;]\s*", match.group("nums").strip()):
        bounds = [int(n) for n in re.split(r"\s*[-–]\s*", part)]
        low, high = bounds[0], bounds[-1]
        if low < 1 or high < low:
            return None
        if high - low + 1 + len(numbers) > MAX_SOURCES:
            return None
        numbers.extend(n for n in range(low, high + 1) if n not in numbers)
    result = {"numbers": numbers, "locator": "", "label": "page", "length": len(match.group(0))}
    if match.group("label"):
        result["locator"] = match.group("loc").strip().rstrip(",").strip()
        result["label"] = _LABELS.get(match.group("label").lower(), "page")
        if not result["locator"]:
            return None
    return result


def ids_for_numbers(numbers, ordered_ids):
    """(ids, missing numbers): ``ordered_ids`` are the sources in bibliography order (number 1 first)."""
    ids, missing = [], []
    for number in numbers:
        if 1 <= number <= len(ordered_ids):
            ids.append(ordered_ids[number - 1])
        else:
            missing.append(number)
    return ids, missing


def cluster_for(ids, locator="", label="page"):
    """A new citation cluster citing ``ids``; the locator goes with the last source, as in "[3, 7, tr. 15]"."""
    cites = [{"id": item_id} for item_id in ids]
    if cites and locator:
        cites[-1]["locator"], cites[-1]["label"] = locator, label
    return {"citationID": "", "items": cites, "mode": "normal"}
