# SPDX-License-Identifier: AGPL-3.0-only
"""EndNote XML import (<xml><records><record>…), common in Vietnamese medical faculties. Parsed with the standard
library; a DOCTYPE or ENTITY declaration is refused before parsing, so entity expansion cannot be abused.
Pure Python (no uno)."""
import re
import xml.etree.ElementTree as ElementTree

from .citation_import_common import ImportResult, ItemBuilder
from .citation_text_io import ImportFailure

REF_TYPES = {
    "journal article": "article-journal", "electronic article": "article-journal", "book": "book",
    "edited book": "book", "electronic book": "book", "book section": "chapter", "electronic book section": "chapter",
    "conference paper": "paper-conference", "conference proceedings": "paper-conference", "thesis": "thesis",
    "report": "report", "government document": "report", "web page": "webpage", "statute": "legislation",
    "bill": "bill", "case": "legal_case", "newspaper article": "article-newspaper",
    "magazine article": "article-magazine", "dataset": "dataset", "patent": "patent", "computer program": "software",
    "unpublished work": "manuscript", "manuscript": "manuscript", "generic": "document", "standard": "standard",
    "dictionary": "entry-dictionary", "encyclopedia": "entry-encyclopedia", "map": "map", "blog": "post-weblog",
}
REF_NUMBERS = {"17": "article-journal", "6": "book", "28": "book", "5": "chapter", "47": "paper-conference",
               "10": "paper-conference", "32": "thesis", "27": "report", "46": "report", "12": "webpage",
               "31": "legislation", "4": "bill", "7": "legal_case", "23": "article-newspaper",
               "19": "article-magazine", "59": "dataset", "25": "patent", "9": "software", "34": "manuscript",
               "13": "document", "43": "article-journal"}
TEXT = {"titles/title": "title", "titles/secondary-title": "container-title", "titles/tertiary-title":
        "collection-title", "titles/short-title": "title-short", "titles/alt-title": "container-title-short",
        "periodical/full-title": "container-title", "periodical/abbr-1": "container-title-short",
        "volume": "volume", "number": "issue", "edition": "edition", "publisher": "publisher",
        "pub-location": "publisher-place", "electronic-resource-num": "DOI", "language": "language",
        "abstract": "abstract", "work-type": "genre", "section": "section", "num-vols": "number-of-volumes",
        "urls/related-urls/url": "URL", "urls/web-urls/url": "URL", "accession-num": "", "label": ""}
NAMES = {"contributors/authors/author": "author", "contributors/secondary-authors/author": "editor",
         "contributors/tertiary-authors/author": "collection-editor",
         "contributors/subsidiary-authors/author": "translator", "contributors/translated-authors/author":
         "translator"}


def _text(node):
    return re.sub(r"\s+", " ", "".join(node.itertext())).strip() if node is not None else ""


def _record(record, index):
    ref = record.find("ref-type")
    name = (ref.get("name", "") if ref is not None else "").lower()
    kind = REF_TYPES.get(name) or REF_NUMBERS.get(_text(ref), "document")
    builder = ItemBuilder(kind)
    for path, var in NAMES.items():
        for node in record.findall(path):
            builder.add_name(var, _text(node))
    for path, var in TEXT.items():
        if var:
            builder.set(var, _text(record.find(path)))
    if kind in ("book", "thesis", "report") and builder.raw.get("container-title"):
        builder.raw.setdefault("collection-title", builder.raw.pop("container-title"))
    year = _text(record.find("dates/year"))
    full = _text(record.find("dates/pub-dates/date"))
    builder.set_date("issued", "%s %s" % (full, year) if full and year and year not in full else full or year)
    builder.set_date("accessed", _text(record.find("access-date")))
    builder.set_pages(_text(record.find("pages")))
    builder.set_identifier(_text(record.find("isbn")))
    builder.add_note(_text(record.find("notes")))
    keywords = [_text(k) for k in record.findall("keywords/keyword")]
    builder.set("keyword", "; ".join(k for k in keywords if k))
    item, warnings = builder.finish()
    return item, ["Bản ghi %d: %s" % (index, text) for text in warnings]


def parse(text):
    """ImportResult of EndNote XML text. Raises ImportFailure for malformed or unsafe XML."""
    head = text[:4096].upper()
    if "<!DOCTYPE" in head or "<!ENTITY" in text.upper():
        raise ImportFailure("tệp XML có khai báo DOCTYPE/ENTITY, không nhập vì lý do an toàn")
    try:
        root = ElementTree.fromstring(text.encode("utf-8"))
    except ElementTree.ParseError as exc:
        raise ImportFailure("XML hỏng (%s)" % exc, exc.position[0] if exc.position else None) from exc
    records = root.findall(".//record")
    result = ImportResult(fmt="endnote-xml")
    for index, record in enumerate(records, 1):
        item, warnings = _record(record, index)
        result.items.append(item)
        result.warnings += warnings
    if not records:
        result.warnings.append("Không tìm thấy bản ghi EndNote nào (<record>)")
    return result
