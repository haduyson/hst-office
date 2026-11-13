# SPDX-License-Identifier: AGPL-3.0-only
"""Building blocks of the importers (RIS, BibTeX, EndNote XML, PubMed .nbib, EndNote .enw): an item builder that
collects raw fields and ends in citation_model.normalize_item, so every importer validates the same way."""
import re

from . import citation_dates as dates
from . import citation_dedupe as dedupe
from . import citation_language as language
from . import citation_model as model
from . import citation_names as names

_ISSN = re.compile(r"\b\d{4}-?\d{3}[\dXx]\b")


class ImportResult:
    """Items ready for the preview table, warnings for the user (Vietnamese, with line numbers)."""

    def __init__(self, items=None, warnings=None, fmt=""):
        self.items, self.warnings, self.format = items or [], warnings or [], fmt
        self.suggestions = []  # filled by citation_import (citation_vn_fix)

    def __repr__(self):
        return "ImportResult(%d items, %d warnings, %s)" % (len(self.items), len(self.warnings), self.format)


class ItemBuilder:
    """Collects one record; ``finish`` returns the normalised CSL item and its warnings."""

    def __init__(self, item_type="document", line=None):
        self.raw = {"type": item_type}
        self.notes, self.line, self.unknown = [], line, []

    def set(self, var, value, overwrite=False):
        value = (value or "").strip()
        if value and (overwrite or not self.raw.get(var)):
            self.raw[var] = value

    def add_name(self, var, text, organization=None):
        name = names.parse_name(text, organization)
        if name:
            self.raw.setdefault(var, []).append(name)

    def add_names(self, var, values):
        for text in values:
            self.add_name(var, text)

    def set_date(self, var, text):
        """Keep the most detailed date seen (RIS gives "PY  - 2015" and "DA  - 2015/05/28/")."""
        date = dates.parse(text)
        current = self.raw.get(var)
        detail = len((date.get("date-parts") or [[]])[0]) if date else 0
        if date and (not current or detail > len((current.get("date-parts") or [[]])[0])):
            self.raw[var] = date

    def set_pages(self, start, end=""):
        start, end = (start or "").strip(), (end or "").strip()
        if start and end and end != start and not re.search(r"[-–]", start):
            self.set("page", start + "-" + end)
        else:
            self.set("page", start)

    def set_identifier(self, text):
        """An RIS/EndNote "SN" field: ISBNs and ISSNs are told apart by their check digits."""
        found = dedupe.isbns(text)
        if found:
            self.set("ISBN", "; ".join(found))
        elif _ISSN.search(text or ""):
            self.set("ISSN", _ISSN.search(text).group(0))

    def add_note(self, text):
        text = (text or "").strip()
        if text:
            self.notes.append(text)

    def mark_unknown(self, tag):
        if tag not in self.unknown:
            self.unknown.append(tag)

    def finish(self):
        if self.notes:
            existing = self.raw.get("note", "")
            self.raw["note"] = "\n".join(([existing] if existing else []) + self.notes)
        if self.raw.get("DOI"):
            self.raw["DOI"] = dedupe.clean_doi(self.raw["DOI"]) or self.raw["DOI"]
        if self.raw.get("language"):
            self.raw["language"] = language.normalize(self.raw["language"]) or self.raw["language"]
        item, warnings = model.normalize_item(self.raw)
        where = ("Dòng %d: " % self.line) if self.line else ""
        warnings = [where + text for text in warnings]
        if self.unknown:
            warnings.append(where + "thẻ không hỗ trợ đã giữ trong ghi chú: " + ", ".join(self.unknown))
        return item, warnings

