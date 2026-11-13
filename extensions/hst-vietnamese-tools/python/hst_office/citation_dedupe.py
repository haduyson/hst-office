# SPDX-License-Identifier: AGPL-3.0-only
"""Duplicate detection of references: normalised DOI, then ISBN-13, then title + year + first family name
(accents and case ignored). DOIs keep their parentheses: "10.54607/hcmue.js.18.8.3112(2021)" is a real DOI."""
import re

from . import citation_model as model
from .vietnamese_text import remove_diacritics

_DOI_PREFIX = re.compile(r"^(?:https?://(?:dx\.)?doi\.org/|doi:\s*|urn:doi:)", re.I)
_DOI = re.compile(r"^10\.\d{4,9}/\S+$")


def clean_doi(text):
    """Bare DOI as written ("https://doi.org/10.1056/NEJMe2002387" -> "10.1056/NEJMe2002387"); "" if not a DOI."""
    value = _DOI_PREFIX.sub("", (text or "").strip()).rstrip(".,;")
    return value if _DOI.match(value) else ""


def normalize_doi(text):
    """Lower-case bare DOI for comparisons (DOIs are case-insensitive)."""
    return clean_doi(text).lower()


def _digits(text):
    return re.sub(r"[^0-9Xx]", "", text or "").upper()


def isbn13(text):
    """ISBN-13 digits of an ISBN-10 or ISBN-13 with a valid check digit; "" otherwise."""
    digits = _digits(text)
    if len(digits) == 10 and digits[:9].isdigit():
        total = sum((10 - i) * int(d) for i, d in enumerate(digits[:9]))
        check = (11 - total % 11) % 11
        if digits[9] != ("X" if check == 10 else str(check)):
            return ""
        digits = "978" + digits[:9]
        return digits + str((10 - sum((1 if i % 2 == 0 else 3) * int(d) for i, d in enumerate(digits)) % 10) % 10)
    if len(digits) == 13 and digits.isdigit():
        total = sum((1 if i % 2 == 0 else 3) * int(d) for i, d in enumerate(digits[:12]))
        return digits if (10 - total % 10) % 10 == int(digits[12]) else ""
    return ""


def isbns(text):
    """Every valid ISBN-13 found in an ISBN field ("978-604-0-00000-0; 0-306-40615-2")."""
    found = []
    for piece in re.findall(r"[0-9][0-9Xx\- ]{8,16}[0-9Xx]", text or ""):
        value = isbn13(piece)
        if value and value not in found:
            found.append(value)
    return found


def title_key(item):
    title = remove_diacritics(item.get("title", "")).lower()
    return re.sub(r"[^0-9a-z]+", "", title)


def keys(item):
    """Duplicate keys of an item, strongest first."""
    result = []
    doi = normalize_doi(item.get("DOI", ""))
    if doi:
        result.append("doi:" + doi)
    result += ["isbn:" + value for value in isbns(item.get("ISBN", ""))]
    title = title_key(item)
    if title:
        people = item.get("author") or item.get("editor") or []
        first = people[0] if people else {}
        family = remove_diacritics(first.get("family") or first.get("literal") or "").lower()
        result.append("tya:%s|%s|%s" % (title, model.year(item) or "", re.sub(r"\W+", "", family)))
    return result


class Index:
    """Key -> item id lookup over a collection."""

    def __init__(self, items=()):
        self.by_key = {}
        for item in items:
            self.add(item)

    def add(self, item):
        for key in keys(item):
            self.by_key.setdefault(key, item["id"])

    def find(self, item):
        """Id of an existing duplicate, or None."""
        for key in keys(item):
            if key in self.by_key:
                return self.by_key[key]
        return None
