# SPDX-License-Identifier: AGPL-3.0-only
"""Calc number-format helpers. Format selection is pure; `apply_format` talks to UNO objects passed in by
the caller and never imports `uno` at module level. Cell values and formulas are never rewritten."""
import re

from .data_files import load_data

KINDS = ("date", "vnd", "percent", "integer")
# number-formats.json codes use en-US separators (',' thousands, '.' decimals) even though the format is registered
# for vi-VN: LibreOffice reads codes in the separators of the locale they are added for, so they must be converted.
CODE_LOCALE = "en-US"
_CODE = re.compile(r"[0#,.%/\-:\[\]$₫A-Za-z0-9 ]+")
CELL_VALUE, CELL_DATETIME, CELL_STRING, CELL_FORMULA = 1, 2, 4, 16  # com.sun.star.sheet.CellFlags


def format_spec(kind, data=None):
    """{'code','example','locale','language','country'} for a format kind from number-formats.json."""
    data = data or load_data("number-formats.json")
    if kind not in KINDS or kind not in data["formats"]:
        raise ValueError("unknown-format: %r" % (kind,))
    code = data["formats"][kind]["code"]
    if not _CODE.fullmatch(code):
        raise ValueError("unsafe-format-code: %r" % (code,))
    language, _, country = data["locale"].partition("-")
    return {"code": code, "example": data["formats"][kind]["example"], "locale": data["locale"],
            "language": language, "country": country, "codeLocale": CODE_LOCALE}


def sheet_blockers(sheet_is_protected, has_selection):
    """Reasons the format must not be applied (checked before any mutation)."""
    reasons = []
    if not has_selection:
        reasons.append("no-selection")
    if sheet_is_protected:
        reasons.append("sheet-protected")
    return reasons


def apply_format(doc, selection, kind, data=None):
    """Apply a registered vi-VN number format to `selection` (cell/range/ranges). Returns a summary dict."""
    import uno  # imported lazily so this module stays importable in plain Python
    spec = format_spec(kind, data)
    locale = uno.createUnoStruct("com.sun.star.lang.Locale")
    locale.Language, locale.Country = spec["language"], spec["country"]
    source = uno.createUnoStruct("com.sun.star.lang.Locale")
    source.Language, source.Country = spec["codeLocale"].split("-")
    key = doc.getNumberFormats().addNewConverted(spec["code"], source, locale)  # returns the existing key if already registered
    selection.NumberFormat = key
    return {"key": key, "code": spec["code"], "text_cells": _count(selection, CELL_STRING)}


def _count(selection, flags):
    try:
        found = selection.queryContentCells(flags)
        return sum((a.EndColumn - a.StartColumn + 1) * (a.EndRow - a.StartRow + 1) for a in found.getRangeAddresses())
    except Exception:  # noqa: BLE001 - informational count only; formatting itself already succeeded
        return 0
