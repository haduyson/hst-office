# SPDX-License-Identifier: AGPL-3.0-only
"""The options every HST citation style has (the university differences are options, not separate styles).

Each style file gives a value for every option; a preset or the document's settings (``HSTCitationStyle`` opts)
override some of them. A value written as {"vi": ..., "other": ...} differs by the item's language group.
"""

NAME_FORMS = ("natural", "family-comma-initials", "family-initials", "family-compact", "initials-family",
              "family-comma-given", "given-family")
SCHEMA = {
    # bibliography order and grouping
    "order": "enum:alpha|cite",                 # ABC, or order of first citation (IEEE, Vancouver, ĐH Hồng Đức)
    "groupByLanguage": "bool",                  # Vietnamese first, then English, French… (ĐHQGHN, HVTC)
    "groupOrder": "list",
    "groupHeadings": "bool",
    "bibTitle": "loc",
    "language": "enum:vi|en",                   # language of the document: citation terms, group headings
    "termLanguage": "enum:item|document",      # "tr." for Vietnamese items and "pp." for English ones, or one set
    # names
    "viSort": "enum:given|family",              # Vietnamese names by given name (tên) or letter by letter
    "viName": "enum:natural|given-comma-initials|as-foreign",  # Nguyễn Văn An / An, N. V. (ĐH Cần Thơ) / foreign
    "viAscii": "bool",                          # drop Vietnamese accents (IEEE at ĐH KHTN)
    "foreignName": "enum:" + "|".join(NAME_FORMS),
    "firstInverted": "bool",                    # only the first name uses foreignName, the others are natural
    "familyUpper": "bool",                      # SMITH, John (ISO 690)
    "initialsSpace": "bool",                    # "Smith, J. A." or "Smith, J.A." (Harvard)
    "nameDelimiter": "str",
    "bibAnd": "loc",                            # "" for none, "&", "và"/"and"
    "bibAndComma": "enum:always|never|3+",
    "bibEtAl": "etal",                          # null: list every author
    "etAlTerm": "loc",                          # và cộng sự / & cộng sự / và ctv. / et al.
    "etAlComma": "bool",
    # citations in the text
    "citeEtAl": "etal",
    "citeAnd": "loc",
    "citeAndComma": "enum:always|never|3+",
    "citeViName": "enum:full|given|family",     # (Nguyễn Văn An, 2010) / (An, 2010) (ĐH Cần Thơ)
    "brackets": "enum:[]|()|sup",
    "multiCite": "enum:combined|separate",      # [5, 21, 49] or [19], [25], [41]
    "compress": "bool",                         # [7–11]
    "citeSort": "bool",
    "collapseYears": "bool",                    # (Smith, 2019, 2020)
    "citeYear": "bool",                         # MLA prints author and page only
    "citeYearSep": "str",
    "citeItemSep": "str",
    "locatorLabel": "bool",                     # [15, tr. 314–315] or [15, 314–315] (ĐH Hồng Đức)
    "locatorSep": "str",
    "yearSuffix": "bool",                       # 2010a, 2010b
    "disambiguateInitials": "bool",             # (J. Smith, 2001; A. Smith, 2001): APA 7 §8.20
    # entries
    "quotes": "enum:curly|straight|single|none",
    "punctInQuote": "bool",
    "pageRange": "enum:expanded|minimal",
    "pageDash": "str",
    "doiPrefix": "str",
    "publisherPrefix": "loc",                   # Nxb / NXB / nothing
    "titleCase": "enum:as-is|title-en",
    "bibLabel": "str",                          # "[%s]", "%s." or "" (author-date)
    "hangingIndent": "bool",
    "subsequentAuthor": "str",                  # MLA "---"
    # notes (Chicago notes and bibliography)
    "ibid": "bool",
    "shortNoteVi": "enum:sdd|short-title",      # "Nguyễn Văn An, Sđd, tr. 15." or the short title
    "noteEtAl": "etal",
}


DEFAULTS = {
    "order": "alpha", "groupByLanguage": False, "groupOrder": ["vi", "en", "fr", "de", "ru", "zh", "ja"],
    "groupHeadings": False, "bibTitle": {"vi": "TÀI LIỆU THAM KHẢO", "other": "References"}, "language": "vi",
    "termLanguage": "item", "viSort": "given", "viName": "natural", "viAscii": False,
    "foreignName": "family-comma-initials", "firstInverted": False, "familyUpper": False, "initialsSpace": True,
    "nameDelimiter": ", ", "bibAnd": "", "bibAndComma": "never", "bibEtAl": None,
    "etAlTerm": {"vi": "và cộng sự", "other": "et al."}, "etAlComma": False, "citeEtAl": {"min": 3, "use": 1},
    "citeAnd": "&", "citeAndComma": "never", "citeViName": "full", "brackets": "[]", "multiCite": "combined",
    "compress": True, "citeSort": True, "collapseYears": False, "citeYear": True, "citeYearSep": ", ",
    "citeItemSep": "; ", "locatorLabel": True, "locatorSep": ", ", "yearSuffix": False, "disambiguateInitials": False, "quotes": "curly",
    "punctInQuote": False, "pageRange": "expanded", "pageDash": "–", "doiPrefix": "https://doi.org/",
    "publisherPrefix": "", "titleCase": "as-is", "bibLabel": "", "hangingIndent": True, "subsequentAuthor": "",
    "ibid": True, "shortNoteVi": "short-title", "noteEtAl": {"min": 3, "use": 1},
}  # reference values (imported CSL styles start from these); every bundled style file states its own


def check_value(name, value):
    """Error text for a bad option value, or None."""
    kind = SCHEMA.get(name)
    if kind is None:
        return "tùy chọn không có: %s" % name
    if kind == "bool" and not isinstance(value, bool):
        return "%s phải là true/false" % name
    if kind == "str" and not isinstance(value, str):
        return "%s phải là chuỗi" % name
    if kind == "list" and not (isinstance(value, list) and all(isinstance(v, str) for v in value)):
        return "%s phải là danh sách chuỗi" % name
    if kind == "loc" and not (isinstance(value, str) or (isinstance(value, dict) and value and all(
            isinstance(k, str) and isinstance(v, str) for k, v in value.items()))):
        return "%s phải là chuỗi hoặc {\"vi\": …, \"other\": …}" % name
    if kind.startswith("enum:") and value not in kind[5:].split("|"):
        return "%s phải là một trong %s" % (name, kind[5:].replace("|", ", "))
    if kind == "etal" and value is not None:
        ok = isinstance(value, dict) and all(isinstance(value.get(k), int) and not isinstance(value.get(k), bool)
                                             and value.get(k) >= 1 for k in ("min", "use"))
        if not ok or value["use"] > value["min"] or not isinstance(value.get("last", False), bool):
            return "%s phải là null hoặc {\"min\": n, \"use\": m (≤ n), \"last\": false}" % name
    return None


def merge(defaults, *overrides, strict=False):
    """(options, warnings): defaults updated by each override in turn. Bad override values are skipped with a
    warning (documents written by a newer HST must still open), or raise ValueError when ``strict``."""
    options, warnings = dict(defaults), []
    for override in overrides:
        for name, value in (override or {}).items():
            error = check_value(name, value)
            if error:
                if strict:
                    raise ValueError(error)
                warnings.append(error)
                continue
            options[name] = value
    return options, warnings
