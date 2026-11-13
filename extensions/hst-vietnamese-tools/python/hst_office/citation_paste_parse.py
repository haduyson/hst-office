# SPDX-License-Identifier: AGPL-3.0-only
"""Paste a formatted reference line and get the fields back (offline, by pattern), for the user to check and fix in
the item form before saving. Handles the Vietnamese thesis pattern (Tác giả (Năm), "Tên", Tạp chí, tập (số), tr.),
APA/Harvard (Name (Year). Title.), IEEE ("Title," Journal, vol., no., pp.) and Vancouver (Title. J. 2020;1(2):3-4).
Online matching of the same line through Crossref is citation_lookup.lookup_reference (only on the user's click).

    item, info = parse_reference(text)      # info = {"confidence": 0..1, "found": [fields], "warnings": []}
"""
import re

from . import citation_dates as dates
from . import citation_dedupe as dedupe
from . import citation_language as language
from . import citation_model as model
from .citation_paste_authors import LEADING_INITIALS, split_authors
from .citation_paste_fields import fill_fields, take

_NUMBERING = re.compile(r"^\s*(?:\[\d+\]|\d+[.)])\s+")
_DOI = re.compile(r"(?:https?://(?:dx\.)?doi\.org/|doi:\s*)?(10\.\d{4,9}/[^\s]+)", re.I)
_URL = re.compile(r"<?(https?://[^\s>]+)>?")
_ACCESSED = re.compile(r"[,.]?\s*\[?(?:truy cập(?: lần cuối)?(?: ngày)?|accessed:?|retrieved|cited|viewed|xem ngày)\s*"
                       r"([^\]\[]*?\d{4}(?:\s+[A-Za-z]{3,9}\.?\s+\d{1,2})?)\]?(?:,\s*(?:từ|from))?", re.I)
_YEAR_PAREN = re.compile(r"\((1[5-9]\d\d|20\d\d)[a-z]?(?:,[^)]*)?\)|\((n\.d\.|không năm|no date)\)")
_YEAR = re.compile(r"\b(1[5-9]\d\d|20\d\d)\b")
_YEAR_DOT = re.compile(r"\.\s+(1[5-9]\d\d|20\d\d|n\.\s?d)[a-z]?[.,]\s")  # Chicago "Author. 2015. Title."
_VANCOUVER_NAMES = re.compile(r"^(?:[^,.]+?\s[A-Z]{1,3}(?:,\s|\.\s|,\s*et al\.\s))+")
_QUOTED = re.compile(r"[“\"‘]([^”\"’]{3,}?)[,.]?[”\"’]")
_VANCOUVER = re.compile(r"\.\s*(1[5-9]\d\d|20\d\d)[^;.]*;\s*(\d+)(?:\s*\(([^)]+)\))?:\s*([A-Za-z]?\d+(?:\s*[-–]\s*\d+)?)")


def parse_reference(text):
    raw = re.sub(r"\s+", " ", (text or "").strip())
    rest = _NUMBERING.sub("", raw)
    item, info = {"type": "document"}, {"found": [], "warnings": []}
    match, rest = take(_DOI, rest)
    if match:
        item["DOI"] = dedupe.clean_doi(match.group(1).rstrip(".,;)")) or match.group(1)
    match, rest = take(_ACCESSED, rest)
    if match:
        item["accessed"] = dates.parse(match.group(1))
    match, rest = take(_URL, rest)
    if match:
        item["URL"] = match.group(1).rstrip(".,;")
    rest = re.sub(r"\s*\[(?:Online|Internet|Trực tuyến)\]|Available(?: from| at)?:|Truy cập tại:", "", rest, flags=re.I)
    vancouver = _VANCOUVER.search(rest)
    year = _YEAR_PAREN.search(rest) or _YEAR_DOT.search(rest)
    names_part = None if year else _VANCOUVER_NAMES.match(rest)
    if year:
        authors, rest = rest[:year.start()], rest[year.end():]
        if year.group(1) and year.group(1).isdigit():
            item["issued"] = {"date-parts": [[int(year.group(1))]]}
    elif vancouver or names_part:
        authors, rest = (rest[:names_part.end()], rest[names_part.end():]) if names_part else rest.partition(". ")[::2]
        if vancouver:
            item["issued"] = {"date-parts": [[int(vancouver.group(1))]]}
            item.update({"volume": vancouver.group(2), "page": vancouver.group(4)})
            if vancouver.group(3):
                item["issue"] = vancouver.group(3)
            rest = rest[:rest.find(vancouver.group(0).lstrip(". "))] if vancouver.group(0).lstrip(". ") in rest else rest
        else:
            years = _YEAR.findall(rest)
            if years:
                item["issued"] = {"date-parts": [[int(years[-1])]]}
    else:
        quoted = _QUOTED.search(rest)
        authors = rest[:quoted.start()] if quoted else _authors_prefix(rest)
        rest = rest[len(authors):]
        years = _YEAR.findall(rest)
        if years:
            item["issued"] = {"date-parts": [[int(years[-1])]]}
    item["author"] = split_authors(authors)
    fill_fields(item, rest.strip(" .,;"))
    item, warnings = model.normalize_item(item)
    item.setdefault("language", language.guess(item))
    info["warnings"] = warnings
    info["found"] = [k for k in ("author", "title", "issued", "container-title", "publisher", "page") if item.get(k)]
    info["confidence"] = round(len([k for k in ("author", "title", "issued") if item.get(k)]) / 3, 2)
    return item, info


def _authors_prefix(text):
    """Author part of a line without a year in parentheses: IEEE "J. K. Author, A. B. Other, Title…" or
    Chicago/MLA/ISO "Author. Title." (a period after a single initial does not end the names)."""
    if LEADING_INITIALS.match(text):
        pieces, taken = text.split(", "), []
        for piece in pieces:
            if LEADING_INITIALS.match(piece) or piece.endswith("et al.") and not taken:
                taken.append(piece)
            else:
                break
        return ", ".join(taken) + (", " if taken and len(taken) < len(pieces) else "")
    match = re.search(r"(?<![\s.][A-ZĐ])\.\s", text)
    return text[:match.end()] if match else ""


def parse_many(text):
    """[(item, info)] for pasted text with one reference per line (numbering like "[1]" or "1." is dropped)."""
    return [parse_reference(line) for line in (text or "").split("\n") if len(line.strip()) > 10]
