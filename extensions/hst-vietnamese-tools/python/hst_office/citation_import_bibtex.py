# SPDX-License-Identifier: AGPL-3.0-only
"""BibTeX / BibLaTeX import (Google Scholar, Scopus, doi.org, arXiv, Zotero, Mendeley): entry types and fields
mapped to CSL-JSON, LaTeX decoded, "and"-separated names parsed (a braced name is an organisation; Vietnamese
names without a comma are recognised by citation_names). Pure Python (no uno)."""
import re

from . import citation_language as language
from .citation_bibtex_latex import decode
from .citation_bibtex_parse import entries
from .citation_import_common import ImportResult, ItemBuilder

TYPES = {"article": "article-journal", "book": "book", "mvbook": "book", "booklet": "pamphlet", "inbook": "chapter",
         "incollection": "chapter", "inproceedings": "paper-conference", "conference": "paper-conference",
         "proceedings": "book", "collection": "book", "manual": "report", "mastersthesis": "thesis",
         "phdthesis": "thesis", "thesis": "thesis", "techreport": "report", "report": "report", "misc": "document",
         "online": "webpage", "electronic": "webpage", "www": "webpage", "unpublished": "manuscript",
         "patent": "patent", "dataset": "dataset", "software": "software", "periodical": "periodical",
         "inreference": "entry-encyclopedia", "legislation": "legislation", "standard": "standard"}
TEXT = {"title": "title", "shorttitle": "title-short", "journal": "container-title", "journaltitle": "container-title",
        "booktitle": "container-title", "shortjournal": "container-title-short", "volume": "volume",
        "publisher": "publisher", "address": "publisher-place", "location": "publisher-place", "doi": "DOI",
        "isbn": "ISBN", "issn": "ISSN", "url": "URL", "edition": "edition", "series": "collection-title",
        "abstract": "abstract", "type": "genre", "keywords": "keyword", "chapter": "chapter-number",
        "pmid": "PMID", "pmcid": "PMCID", "eventtitle": "event-title", "venue": "event-place",
        "pagetotal": "number-of-pages", "origtitle": "original-title"}
NAMES = {"author": "author", "editor": "editor", "translator": "translator"}
HOSTS = ("school", "institution", "organization")
SKIP = {"file", "timestamp", "owner", "groups", "mendeley-groups", "mendeley-tags", "eprinttype", "urldate",
        "month", "year", "date", "number", "issue", "pages", "note", "language", "langid", "eprint",
        "archiveprefix", "primaryclass", "howpublished", "annote", "copyright", "eid", "bdsk-url-1", "crossref"}
DEGREE = {"phdthesis": "PhD thesis", "mastersthesis": "Master's thesis"}


def split_names(raw):
    """Names of an "and"-separated BibTeX list, split outside braces only."""
    parts, depth, current = [], 0, ""
    tokens = re.split(r"(\s+and\s+|[{}])", raw, flags=re.I)
    for token in tokens:
        if token == "{":
            depth += 1
        elif token == "}":
            depth -= 1
        if depth == 0 and re.fullmatch(r"\s+and\s+", token or "", re.I):
            parts.append(current)
            current = ""
        else:
            current += token or ""
    parts.append(current)
    return [p.strip() for p in parts if p.strip() and p.strip().lower() != "others"]


def _name_text(raw):
    """A fully braced name ("{World Health Organization}") stays braced so citation_names keeps it whole."""
    raw = raw.strip()
    if raw.startswith("{") and raw.endswith("}") and raw.count("{") == 1:
        return "{" + decode(raw[1:-1]) + "}"
    return decode(raw)


def _item(kind, fields, line):
    builder = ItemBuilder(TYPES.get(kind, "document"), line)
    value = {name: decode(raw) for name, raw in fields.items() if name not in NAMES}
    for field, var in NAMES.items():
        for raw in split_names(fields.get(field, "")):
            builder.add_name(var, _name_text(raw))
    for field, var in TEXT.items():
        if field in value:
            builder.set(var, value[field])
    for field in HOSTS:
        builder.set("publisher", value.get(field, ""))
    date, year, month = value.get("date", ""), value.get("year", ""), value.get("month", "")
    if not date and year:
        if month.isdigit() and 1 <= int(month) <= 12:
            date = "%s-%02d" % (year, int(month))
        else:
            date = ("%s %s" % (month, year)).strip()  # "May 2010"
    builder.set_date("issued", date)
    builder.set_date("accessed", value.get("urldate", ""))
    builder.set("issue" if builder.raw["type"] == "article-journal" else "number",
                value.get("number") or value.get("issue", ""))
    builder.set_pages(value.get("pages", "").replace("–", "-"))
    builder.set("language", language.normalize(value.get("langid") or value.get("language")) or "")
    if kind in DEGREE:
        builder.set("genre", DEGREE[kind])
    if value.get("eprint"):
        prefix = value.get("archiveprefix") or value.get("eprinttype") or ""
        builder.add_note(("%s:%s" % (prefix, value["eprint"])) if prefix else value["eprint"])
    howpublished = value.get("howpublished", "")
    if howpublished.startswith(("http://", "https://")):
        builder.set("URL", howpublished)
    else:
        builder.add_note(howpublished)
    builder.add_note(value.get("note", ""))
    if builder.raw["type"] == "document" and builder.raw.get("URL") and not builder.raw.get("publisher"):
        builder.raw["type"] = "webpage"
    for field in sorted(set(fields) - set(TEXT) - set(NAMES) - set(HOSTS) - SKIP):
        builder.add_note("%s: %s" % (field, value[field]))
        builder.mark_unknown(field)
    return builder.finish()


def parse(text):
    """ImportResult of BibTeX text (already decoded by citation_text_io)."""
    found, warnings = entries(text)
    result = ImportResult(warnings=warnings, fmt="bibtex")
    for kind, _key, fields, line in found:
        if kind not in TYPES:
            result.warnings.append("Dòng %d: kiểu @%s không hỗ trợ, nhập như “Tài liệu khác”" % (line, kind))
        item, item_warnings = _item(kind, fields, line)
        result.items.append(item)
        result.warnings += item_warnings
    if not found:
        result.warnings.append("Không tìm thấy mục BibTeX nào (mỗi mục bắt đầu bằng “@article{”, “@book{”…)")
    return result
