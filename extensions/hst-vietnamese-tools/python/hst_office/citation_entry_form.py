# SPDX-License-Identifier: AGPL-3.0-only
"""The source form: which fields each type of source shows, and the conversion between the form's text boxes and
a CSL-JSON item. Pure Python (no uno); the dialog is citation_entry_dialog.

Names are one per line: "Nguyễn Văn An" (Vietnamese, kept in full and in this order), "Smith, John" (others),
"{Bộ Y tế}" (an organisation); citation_names.parse_name reads them. Dates are "2010", "3/2010" or "15/3/2010".
"""
import re

FIELDS = ("title", "container-title", "issued", "publisher", "publisher-place", "volume", "issue", "page",
          "edition", "genre", "number", "authority", "DOI", "ISBN", "URL", "accessed", "language", "note")
DATE_FIELDS = ("issued", "accessed")
_COMMON = ("title", "issued", "language", "note")
TYPE_FIELDS = {
    "book": _COMMON + ("edition", "publisher", "publisher-place", "ISBN", "DOI", "URL"),
    "chapter": _COMMON + ("container-title", "publisher", "publisher-place", "page", "ISBN", "DOI"),
    "article-journal": _COMMON + ("container-title", "volume", "issue", "page", "DOI", "URL"),
    "paper-conference": _COMMON + ("container-title", "publisher", "publisher-place", "page", "DOI"),
    "thesis": _COMMON + ("genre", "publisher", "publisher-place", "URL"),
    "report": _COMMON + ("publisher", "publisher-place", "number", "DOI", "URL"),
    "legislation": _COMMON + ("number", "authority", "URL"),
    "webpage": _COMMON + ("container-title", "URL", "accessed"),
    "article-newspaper": _COMMON + ("container-title", "page", "URL", "accessed"),
    "article-magazine": _COMMON + ("container-title", "volume", "issue", "page", "URL"),
}
EDITOR_TYPES = ("book", "chapter", "paper-conference", "report")


def visible_fields(item_type):
    return set(TYPE_FIELDS.get(item_type, FIELDS))


def parse_date(text):
    """{"date-parts": [[y, m, d]]} from "2010", "3/2010", "15/3/2010" or "2010-03-15"; None when empty or invalid."""
    text = (text or "").strip()
    match = re.fullmatch(r"(?:(\d{1,2})[/.-])?(?:(\d{1,2})[/.-])?(\d{4})", text)
    if match:
        day, month, year = match.group(1), match.group(2), match.group(3)
        if day and not month:  # "3/2010": month and year
            day, month = None, day
        parts = [int(year)] + ([int(month)] if month else []) + ([int(day)] if day and month else [])
    else:
        iso = re.fullmatch(r"(\d{4})-(\d{1,2})(?:-(\d{1,2}))?", text)
        if not iso:
            return None
        parts = [int(p) for p in iso.groups() if p]
    if len(parts) > 1 and not 1 <= parts[1] <= 12 or len(parts) > 2 and not 1 <= parts[2] <= 31:
        return None
    return {"date-parts": [parts]}


def format_date(date):
    """"15/3/2010", "3/2010", "2010" or the literal text of a CSL date."""
    if not isinstance(date, dict):
        return ""
    parts = (date.get("date-parts") or [[]])[0]
    if parts:
        return "/".join(str(p) for p in reversed(parts))
    return str(date.get("literal") or date.get("raw") or "")


def names_to_text(names):
    from .citation_names import full_name, is_vietnamese
    lines = []
    for name in names or []:
        if name.get("literal"):
            lines.append("{%s}" % name["literal"])
        elif is_vietnamese(name) or not name.get("given"):
            lines.append(full_name(name))
        else:
            lines.append("%s, %s" % (" ".join(p for p in (name.get("non-dropping-particle"), name.get("family")) if p),
                                     name["given"]))
    return "\n".join(lines)


def text_to_names(text):
    from .citation_names import parse_name
    return [n for n in (parse_name(line.strip()) for line in (text or "").splitlines() if line.strip()) if n]


def values_of(item):
    """The form's text for every field, "authors" and "editors" of an item (empty strings for a new source)."""
    item = item or {}
    values = {f: (format_date(item.get(f)) if f in DATE_FIELDS else str(item.get(f) or "")) for f in FIELDS}
    values["authors"] = names_to_text(item.get("author"))
    values["editors"] = names_to_text(item.get("editor"))
    return values


def item_of(values, item_type, base=None):
    """(item, warnings): the validated item built from the form. ``base`` (the item being edited) keeps its id
    and the fields this form does not show (translator, abstract, …); shown fields left empty are removed."""
    from . import citation_model
    raw = dict(base or {})
    raw["type"] = item_type
    for field in FIELDS:
        raw.pop(field, None)
        value = (values.get(field) or "").strip()
        if not value or field not in visible_fields(item_type):
            continue
        raw[field] = parse_date(value) or {"literal": value} if field in DATE_FIELDS else value
    for key, field in (("author", "authors"), ("editor", "editors")):
        raw.pop(key, None)
        names = text_to_names(values.get(field))
        if names and (key == "author" or item_type in EDITOR_TYPES):
            raw[key] = names
    item, warnings = citation_model.normalize_item(raw)
    return citation_model.touch(item), warnings
