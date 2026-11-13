# SPDX-License-Identifier: AGPL-3.0-only
"""BibTeX export: CSL types and fields mapped back to BibTeX entries with readable, unique keys (trinh2019kinh).
Special characters are escaped; Unicode letters stay as written (UTF-8 BibTeX/biber). Pure Python (no uno)."""
import re

from . import citation_dates as dates
from .citation_bibtex_latex import encode
from .vietnamese_text import remove_diacritics

TYPES = {"article-journal": "article", "article-magazine": "article", "article-newspaper": "article",
         "book": "book", "chapter": "incollection", "paper-conference": "inproceedings", "report": "techreport",
         "webpage": "online", "post-weblog": "online", "manuscript": "unpublished", "patent": "patent",
         "dataset": "dataset", "software": "software", "entry-encyclopedia": "inreference"}
FIELDS = (("title", "title"), ("container-title", None), ("collection-title", "series"), ("edition", "edition"),
          ("volume", "volume"), ("issue", "number"), ("number", "number"), ("page", "pages"),
          ("publisher", None), ("publisher-place", "address"), ("genre", "type"), ("DOI", "doi"), ("ISBN", "isbn"),
          ("ISSN", "issn"), ("URL", "url"), ("language", "language"), ("keyword", "keywords"), ("note", "note"),
          ("abstract", "abstract"))
_MASTER = re.compile(r"master|thạc sĩ|m\.s\.|msc", re.I)


def _kind(item):
    if item.get("type") == "thesis":
        return "mastersthesis" if _MASTER.search(item.get("genre", "")) else "phdthesis"
    return TYPES.get(item.get("type"), "misc")


def _container_field(kind):
    return "journal" if kind == "article" else "booktitle" if kind in ("incollection", "inproceedings") else None


def _publisher_field(kind):
    return {"phdthesis": "school", "mastersthesis": "school", "techreport": "institution"}.get(kind, "publisher")


def _name(name):
    if name.get("literal"):
        return "{" + encode(name["literal"]) + "}"
    family = " ".join(p for p in (name.get("non-dropping-particle"), name.get("family")) if p)
    parts = [encode(family)] + [encode(p) for p in (name.get("suffix"), name.get("given")) if p]
    return ", ".join(parts) if len(parts) > 1 else "{" + encode(family) + "}"


def _key(item, used):
    people = item.get("author") or item.get("editor") or []
    first = people[0] if people else {}
    word = first.get("family") or first.get("literal") or item.get("title", "ref")
    base = re.sub(r"[^a-z0-9]", "", remove_diacritics(word.split(" ")[0]).lower()) or "ref"
    title_words = [w for w in re.findall(r"[a-z0-9]+", remove_diacritics(item.get("title", "")).lower()) if len(w) > 3]
    key = base + str(dates.year(item.get("issued")) or "") + (title_words[0] if title_words else "")
    unique, number = key, 1
    while unique in used:
        number += 1
        unique = key + chr(ord("a") + number - 2) if number <= 27 else key + str(number)
    used.add(unique)
    return unique


def _date_fields(item):
    fields = []
    year, month, day = dates.parts(item.get("issued") or {})
    if year:
        fields.append(("year", str(year)))
        if month:
            fields.append(("month", str(month)))
            fields.append(("date", "%04d-%02d" % (year, month) + ("-%02d" % day if day else "")))
    if item.get("accessed"):
        y, m, d = dates.parts(item["accessed"])
        if y:
            fields.append(("urldate", "-".join(("%04d" % y, "%02d" % m if m else "", "%02d" % d if d else "")).strip("-")))
    return fields


def entry(item, used):
    kind = _kind(item)
    fields = []
    for var, field in (("author", "author"), ("editor", "editor"), ("translator", "translator")):
        if item.get(var):
            fields.append((field, " and ".join(_name(n) for n in item[var])))
    for var, field in FIELDS:
        value = item.get(var)
        if not value or (var == "number" and item.get("issue")):
            continue
        field = field or (_container_field(kind) if var == "container-title" else _publisher_field(kind))
        if field:
            text = re.sub(r"\s*[-–]\s*", "--", value) if var == "page" else value
            fields.append((field, text if field == "url" else encode(text)))
    fields += _date_fields(item)
    body = ",\n".join("  %s = {%s}" % (name, value) for name, value in fields)
    return "@%s{%s,\n%s\n}\n" % (kind, _key(item, used), body)


def to_bibtex(items):
    used = set()
    return "\n".join(entry(item, used) for item in items)
