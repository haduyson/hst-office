# SPDX-License-Identifier: AGPL-3.0-only
"""ND30 administrative-document data, formatting and validation (pure logic, no `uno`). Layout: nd30_layout.py.

Provenance: algorithms ported from archive/onlyoffice-plugin-first@e0517d71c813535087c401b2683bec0784d71fd8,
extensions/vn-admin-documents/logic/nd30-layout.js and nd30-validation.js, then re-validated against
docs/VIETNAMESE_OFFICE_SPEC.md (Nghi dinh 30/2020/ND-CP, Phu luc I, Phan I). Legal validity in 2026 is
UNVERIFIED (docs/BLOCKERS.md LEG-05): this is a presentation helper only.

Deliberate deviations from the archive: rule widths come from the estimated text width (spec II.1b: the motto
rule is as long as the line; II.2b/II.5b: 1/3-1/2 of the line) instead of fixed millimetres; the symbol is
upper-cased (II.3c); dates accept dd/mm/yyyy as well as ISO input; control characters are rejected.
"""
import datetime
import re

from .data_files import load_data

MAX_FIELD = 2000
MAX_BODY = 100000
_CONTROL = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")
FIELD_KEYS = ("parentAgency", "agency", "number", "symbol", "place", "date", "summary", "kinhGui", "body",
              "signerAuthority", "signerTitle", "signerName", "recipients")


def rules():
    return load_data("nd30.json")


def get_type(type_id, data=None):
    return next((t for t in (data or rules())["documentTypes"] if t["id"] == type_id), None)


def format_number(number):
    """II.3c: numbers below 10 get a leading zero ('5' -> '05')."""
    n = str(number or "").strip()
    return "0" + n if re.fullmatch(r"\d", n) else n


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
    number = (fields.get("number") or "").strip()
    if number and not re.fullmatch(r"\d{1,6}", number):
        errors.append({"field": "number", "code": "number-digits-only"})
    symbol = (fields.get("symbol") or "").strip()
    if symbol and re.search(r"[\s/]", symbol):
        errors.append({"field": "symbol", "code": "symbol-no-space-or-slash"})
    date = (fields.get("date") or "").strip()
    if date and parse_date_input(date) is None:
        errors.append({"field": "date", "code": "invalid-date"})
    return {"ok": not errors, "errors": errors}


def validate_margins(margins_mm, data=None):
    """I.3: top/bottom 20-25, left 30-35, right 15-20 mm. Non-numeric values are rejected."""
    errors = []
    for side, (low, high) in (data or rules())["marginRangesMm"].items():
        try:
            value = float((margins_mm or {})[side])
        except (KeyError, TypeError, ValueError):
            errors.append({"field": side, "code": "margin-not-number"})
            continue
        if value != value or not low <= value <= high:
            errors.append({"field": side, "code": "margin-out-of-range"})
    return {"ok": not errors, "errors": errors}
