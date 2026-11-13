# SPDX-License-Identifier: AGPL-3.0-only
"""Export references (the library or the items of a document) to RIS, CSL-JSON or BibTeX, so they move to other
reference managers. Text is returned; the caller writes it as UTF-8. Pure Python (no uno)."""
import copy
import json
import re

from . import citation_dates as dates
from .citation_export_bibtex import to_bibtex
from .citation_ris_map import CSL_TO_TYPE, EXPORT_NAMES, EXPORT_TEXT

FORMATS = {"ris": ".ris", "bibtex": ".bib", "csl-json": ".json"}


def _ris_name(name):
    if name.get("literal"):
        return name["literal"]
    family = " ".join(p for p in (name.get("non-dropping-particle"), name.get("family")) if p)
    parts = [family] + [p for p in (name.get("given"), name.get("suffix")) if p]
    return ", ".join(parts)


def _ris_date(date):
    year, month, day = dates.parts(date)
    if not year:
        return date.get("literal", "")
    return "%04d/%s/%s/" % (year, "%02d" % month if month else "", "%02d" % day if day else "")


def _one_line(text):
    return re.sub(r"\s+", " ", str(text)).strip()


def to_ris(items):
    """RIS text (CRLF line ends, as the format expects)."""
    lines = []
    for item in items:
        lines.append("TY  - " + CSL_TO_TYPE.get(item.get("type"), "GEN"))
        for var, tag in EXPORT_NAMES:
            lines += ["%s  - %s" % (tag, _ris_name(n)) for n in item.get(var, [])]
        if item.get("issued"):
            year = dates.year(item["issued"])
            if year:
                lines.append("PY  - %d" % year)
            lines.append("DA  - " + _ris_date(item["issued"]))
        for var, tag in EXPORT_TEXT:
            if item.get(var):
                lines.append("%s  - %s" % (tag, _one_line(item[var])))
        if item.get("page"):
            pages = re.split(r"\s*[-–]\s*", item["page"], maxsplit=1)
            lines.append("SP  - " + pages[0])
            if len(pages) > 1 and pages[1]:
                lines.append("EP  - " + pages[1])
        for var in ("ISBN", "ISSN"):
            if item.get(var):
                lines.append("SN  - " + item[var])
        if item.get("accessed"):
            lines.append("Y2  - " + _ris_date(item["accessed"]))
        for keyword in re.split(r"\s*[;,]\s*", item.get("keyword", "")):
            if keyword:
                lines.append("KW  - " + keyword)
        lines += ["ER  - ", ""]
    return "\r\n".join(lines)


def strip_hst(item):
    """CSL-JSON without HST extras (the Vietnamese-name flag and custom.hst) for strict readers."""
    clean = copy.deepcopy(item)
    for var, value in clean.items():
        if isinstance(value, list):
            for name in value:
                if isinstance(name, dict):
                    name.pop("hst-vi", None)
    custom = clean.get("custom")
    if isinstance(custom, dict):
        custom.pop("hst", None)
        if not custom:
            del clean["custom"]
    return clean


def to_csl_json(items, portable=False):
    return json.dumps([strip_hst(i) if portable else i for i in items], ensure_ascii=False, indent=2) + "\n"


def export(items, fmt, portable=False):
    """Text of the items in ``fmt`` ("ris", "bibtex" or "csl-json")."""
    if fmt == "ris":
        return to_ris(items)
    if fmt == "bibtex":
        return to_bibtex(items)
    if fmt == "csl-json":
        return to_csl_json(items, portable)
    raise ValueError("định dạng xuất không hỗ trợ: %s" % fmt)
