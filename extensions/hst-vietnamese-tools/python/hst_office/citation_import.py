# SPDX-License-Identifier: AGPL-3.0-only
"""Import entry point: pick the format from the file name or the content, parse, and attach the "sửa tên Việt"
suggestions for the preview table.

    result = citation_import.import_file(path)          # or import_bytes(data, "export.ris")
    result.items, result.warnings, result.suggestions, result.format

Formats: RIS (.ris), BibTeX/BibLaTeX (.bib), CSL-JSON (.json), EndNote XML (.xml), PubMed (.nbib), EndNote tagged
(.enw). Raises citation_text_io.ImportFailure when the file cannot be read at all. Pure Python (no uno).
"""
import os
import re

from . import citation_import_bibtex as bibtex
from . import citation_import_csl as csl
from . import citation_import_endnote as endnote
from . import citation_import_ris as ris
from . import citation_import_tagged as tagged
from . import citation_vn_fix as vn_fix
from .citation_text_io import ImportFailure, decode

PARSERS = {"ris": ris.parse, "bibtex": bibtex.parse, "csl-json": csl.parse, "endnote-xml": endnote.parse,
           "nbib": tagged.parse_nbib, "enw": tagged.parse_enw}
EXTENSIONS = {".ris": "ris", ".bib": "bibtex", ".bibtex": "bibtex", ".json": "csl-json", ".xml": "endnote-xml",
              ".nbib": "nbib", ".enw": "enw"}
FILTER = (("Tệp tài liệu tham khảo", "*.ris;*.bib;*.json;*.xml;*.nbib;*.enw;*.txt"), ("RIS", "*.ris"),
          ("BibTeX", "*.bib"), ("CSL-JSON", "*.json"), ("EndNote XML", "*.xml"), ("PubMed", "*.nbib"),
          ("EndNote", "*.enw"))


def detect(text, filename=""):
    """Format name from the extension, else from the first meaningful characters."""
    extension = os.path.splitext(filename or "")[1].lower()
    if extension in EXTENSIONS:
        return EXTENSIONS[extension]
    head = text.lstrip("﻿ \n\t")[:2000]
    if re.match(r"TY\s{1,2}-", head) or re.search(r"^TY\s{1,2}- ", head, re.M):
        return "ris"
    if head.startswith(("[", "{")):
        return "csl-json"
    if head.startswith("<") and "<record" in text[:20000]:
        return "endnote-xml"
    if re.search(r"^PMID-", head, re.M):
        return "nbib"
    if re.search(r"^%0 ", head, re.M):
        return "enw"
    if re.search(r"^\s*@[A-Za-z]+\s*[{(]", head, re.M):
        return "bibtex"
    raise ImportFailure("không nhận ra định dạng (RIS, BibTeX, CSL-JSON, EndNote XML, PubMed, EndNote)")


def import_text(text, filename="", fmt=None):
    fmt = fmt or detect(text, filename)
    if fmt not in PARSERS:
        raise ImportFailure("định dạng không hỗ trợ: %s" % fmt)
    result = PARSERS[fmt](text)
    result.suggestions = vn_fix.suggest(result.items)
    return result


def import_bytes(data, filename="", fmt=None):
    return import_text(decode(data), filename, fmt)


def import_file(path, fmt=None):
    with open(path, "rb") as stream:
        data = stream.read(10 * 1024 * 1024 + 1)
    return import_bytes(data, os.path.basename(path), fmt)
