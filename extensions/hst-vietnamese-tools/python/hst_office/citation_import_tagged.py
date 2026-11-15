# SPDX-License-Identifier: AGPL-3.0-only
"""Line-tagged formats besides RIS: PubMed/MEDLINE ``.nbib`` ("PMID- 123", "FAU - Smith, John") and EndNote /
refer ``.enw`` ("%0 Journal Article", "%A Smith, John"). Pure Python (no uno)."""
import re

from . import citation_language as language
from .citation_import_common import ImportResult, ItemBuilder
from .citation_import_endnote import REF_TYPES

_NBIB = re.compile(r"^([A-Z][A-Z0-9]{1,3})\s*- ?(.*)$")
_ENW = re.compile(r"^%(\S)\s?(.*)$")
NBIB_TEXT = {"TI": "title", "BTI": "container-title", "JT": "container-title", "TA": "container-title-short",
             "VI": "volume", "IP": "issue", "PB": "publisher", "AB": "abstract", "PMID": "PMID", "PMC": "PMCID",
             "EN": "edition", "CTI": "collection-title"}
ENW_TEXT = {"T": "title", "J": "container-title", "B": "container-title", "V": "volume", "N": "issue",
            "I": "publisher", "C": "publisher-place", "R": "DOI", "U": "URL", "X": "abstract", "7": "edition",
            "9": "genre", "S": "collection-title", "!": "title-short", "K": "keyword"}
ENW_NAMES = {"A": "author", "E": "editor", "Y": "collection-editor", "H": "translator"}


def _records(text, pattern, starts):
    """[(line number, [(tag, value)])]; a tagless line continues the previous value."""
    records, current = [], None
    for number, raw in enumerate(text.split("\n"), 1):
        match = pattern.match(raw)
        if match and match.group(1) in starts:
            current = (number, [])
            records.append(current)
        if match and current is not None:
            current[1].append([match.group(1), match.group(2).strip()])
        elif raw.strip() and current is not None and current[1] and raw.startswith((" ", "\t")):
            current[1][-1][1] += " " + raw.strip()
    return records


def _nbib_item(line, fields):
    tags = [tag for tag, _ in fields]
    kind = "chapter" if "BTI" in tags and "TI" in tags else "book" if "BTI" in tags else "article-journal"
    builder = ItemBuilder(kind, line)
    names = "FAU" if "FAU" in tags else "AU"
    for tag, value in fields:
        if tag == names:
            builder.add_name("author", value, organization=False)
        elif tag in ("FED", "ED") and (tag == "FED" or "FED" not in tags):
            builder.add_name("editor", value, organization=False)
        elif tag == "CN":
            builder.add_name("author", value, organization=True)
        elif tag == "DP":
            builder.set_date("issued", value)
        elif tag == "PG":
            builder.set_pages(value)
        elif tag in ("LID", "AID") and value.endswith("[doi]"):
            builder.set("DOI", value[:-5].strip())
        elif tag == "LA":
            builder.set("language", language.normalize(value))
        elif tag == "IS" and not builder.raw.get("ISSN"):
            builder.set("ISSN", value.split(" ")[0])
        elif tag in ("TI", "BTI"):
            builder.set(NBIB_TEXT[tag], value[:-1] if value.endswith(".") else value)  # MEDLINE ends titles with "."
        elif tag in NBIB_TEXT:
            builder.set(NBIB_TEXT[tag], value)
    if kind == "book" and builder.raw.get("container-title") and not builder.raw.get("title"):
        builder.raw["title"] = builder.raw.pop("container-title")
    return builder.finish()


def _enw_item(line, fields):
    kind = REF_TYPES.get(next((v for t, v in fields if t == "0"), "").lower(), "document")
    builder = ItemBuilder(kind, line)
    for tag, value in fields:
        if tag in ENW_NAMES:
            builder.add_name(ENW_NAMES[tag], value)
        elif tag == "D":
            builder.set_date("issued", value)
        elif tag == "8" and not builder.raw.get("issued"):
            builder.set_date("issued", value)
        elif tag == "P":
            builder.set_pages(value)
        elif tag == "@":
            builder.set_identifier(value)
        elif tag == "G":
            builder.set("language", language.normalize(value))
        elif tag == "Z":
            builder.add_note(value)
        elif tag == "K" and builder.raw.get("keyword"):
            builder.raw["keyword"] += "; " + value
        elif tag in ENW_TEXT:
            builder.set(ENW_TEXT[tag], value)
    return builder.finish()


def parse_nbib(text):
    result = ImportResult(fmt="nbib")
    for line, fields in _records(text, _NBIB, ("PMID",)):
        item, warnings = _nbib_item(line, fields)
        result.items.append(item)
        result.warnings += warnings
    if not result.items:
        result.warnings.append("Không tìm thấy bản ghi PubMed nào (mỗi bản ghi bắt đầu bằng “PMID- ”)")
    return result


def parse_enw(text):
    result = ImportResult(fmt="enw")
    for line, fields in _records(text, _ENW, ("0",)):
        item, warnings = _enw_item(line, fields)
        result.items.append(item)
        result.warnings += warnings
    if not result.items:
        result.warnings.append("Không tìm thấy bản ghi EndNote nào (mỗi bản ghi bắt đầu bằng “%0 ”)")
    return result
