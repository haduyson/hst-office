# SPDX-License-Identifier: AGPL-3.0-only
"""ND30 administrative-document data, formatting and validation (pure logic, no `uno`). Layout: nd30_layout.py.

Provenance: algorithms ported from archive/onlyoffice-plugin-first@e0517d71c813535087c401b2683bec0784d71fd8,
extensions/vn-admin-documents/logic/nd30-layout.js and nd30-validation.js, then re-validated against
docs/VIETNAMESE_OFFICE_SPEC.md (Nghi dinh 30/2020/ND-CP, Phu luc I, Phan I). Legal validity in 2026 is
UNVERIFIED (docs/BLOCKERS.md LEG-05): this is a presentation helper only.

Rule widths come from the real line (nd30_metrics); official abbreviations such as TTr, CTr and QyĐ keep their case in
the symbol while everything else is upper-cased (II.3c); dates accept dd/mm/yyyy as well as ISO input; control
characters are rejected.
"""
import datetime
import re

from .data_files import load_data

MAX_FIELD = 2000
MAX_BODY = 100000
_CONTROL = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")
FIELD_KEYS = ("parentAgency", "agency", "number", "symbol", "place", "date", "summary", "kinhGui", "body",
              "signerAuthority", "signerTitle", "signerName", "secretaryName", "recipients", "contact")
_PROFILE_FILES = {"nd30": "nd30.json"}


def rules():
    data = dict(load_data("nd30.json"))
    data["documentTypes"] = load_data("document-types.json")["types"]
    return data


def profile_rules(profile):
    """The rule set of a profile: margins, typography, placeholders. Profiles never share a rule by accident."""
    data = dict(load_data(_PROFILE_FILES[profile]))
    data["documentTypes"] = load_data("document-types.json")["types"]
    return data


def rules_for(type_id):
    t = get_type(type_id)
    return profile_rules(t["profile"] if t else "nd30")


def get_type(type_id, data=None):
    types = data["documentTypes"] if data else load_data("document-types.json")["types"]
    return next((t for t in types if t["id"] == type_id), None)


def format_number(number):
    """II.3c: numbers below 10 get a leading zero ('5' -> '05')."""
    n = str(number or "").strip()
    return "0" + n if re.fullmatch(r"\d", n) else n


def official_abbreviations():
    """Abbreviations with a fixed spelling in the annex (TTr, CTr, QyĐ, TrS), keyed by their upper-case form."""
    extra = load_data("nd30.json")["layoutRules"].get("copyAbbreviations", ["SY", "SL", "TrS"])
    names = [t["abbr"] for t in load_data("document-types.json")["types"] if t.get("abbr")] + extra
    return {name.upper(): name for name in names}


def format_symbol(symbol, abbr=""):
    """Symbol in capitals except the official abbreviations; the type's abbreviation is added when it was left out."""
    official = official_abbreviations()
    groups = [g for g in str(symbol or "").strip().split("-") if g]
    groups = [official.get(g.upper(), g.upper()) for g in groups]
    if abbr and groups and groups[0] != abbr:
        groups.insert(0, abbr)
    return "-".join(groups)


def parse_date_input(text):
    """Accept YYYY-MM-DD or DD/MM/YYYY; return a datetime.date or None for empty/invalid input."""
    raw = str(text or "").strip()
    m = re.fullmatch(r"(\d{4})-(\d{2})-(\d{2})", raw)
    parts = (m.group(1), m.group(2), m.group(3)) if m else None
    if not parts:
        m = re.fullmatch(r"(\d{1,2})/(\d{1,2})/(\d{4})", raw)
        parts = (m.group(3), m.group(2), m.group(1)) if m else None
    if not parts:
        return None
    try:
        return datetime.date(int(parts[0]), int(parts[1]), int(parts[2]))
    except ValueError:
        return None


def format_issue_date(text):
    """II.4c: 'ngày 05 tháng 02 năm 2026' - day below 10 and months 1-2 are zero padded."""
    d = parse_date_input(text)
    if d is None:
        return None
    month = "%02d" % d.month if d.month <= 2 else str(d.month)
    return "ngày %02d tháng %s năm %d" % (d.day, month, d.year)


def validate_fields(type_id, fields, data=None):
    """Return {'ok': bool, 'errors': [{'field','code'}]}; empty fields are fine (placeholders are used)."""
    if get_type(type_id, data) is None:
        return {"ok": False, "errors": [{"field": "type", "code": "unknown-type"}]}
    errors = []
    for key, raw in (fields or {}).items():
        if raw is None:
            continue
        if not isinstance(raw, str):
            errors.append({"field": key, "code": "not-text"})
        elif len(raw) > (MAX_BODY if key == "body" else MAX_FIELD):
            errors.append({"field": key, "code": "too-long"})
        elif _CONTROL.search(raw):
            errors.append({"field": key, "code": "control-character"})
    number = str(fields.get("number") or "").strip() if isinstance(fields.get("number") or "", str) else ""
    if number and not re.fullmatch(r"\d{1,6}", number):
        errors.append({"field": "number", "code": "number-digits-only"})
    symbol = fields.get("symbol") or ""
    if isinstance(symbol, str) and re.search(r"[\s/]", symbol.strip()):
        errors.append({"field": "symbol", "code": "symbol-no-space-or-slash"})
    date = fields.get("date") or ""
    if isinstance(date, str) and date.strip() and parse_date_input(date) is None:
        errors.append({"field": "date", "code": "invalid-date"})
    return {"ok": not errors, "errors": errors}


def validate_margins(margins_mm, data=None):
    """Margins inside the ranges of the profile `data` (default ND30 I.3). Non-numeric values are rejected."""
    errors = []
    for side, (low, high) in (data or load_data("nd30.json"))["marginRangesMm"].items():
        try:
            value = float((margins_mm or {})[side])
        except (KeyError, TypeError, ValueError):
            errors.append({"field": side, "code": "margin-not-number"})
            continue
        if value != value or not low <= value <= high:
            errors.append({"field": side, "code": "margin-out-of-range"})
    return {"ok": not errors, "errors": errors}
