# SPDX-License-Identifier: AGPL-3.0-only
"""ND30 layout builder (pure logic, no `uno`): editor-independent paragraphs and two-column blocks.

Provenance: ported from archive/onlyoffice-plugin-first@e0517d71c813535087c401b2683bec0784d71fd8
extensions/vn-admin-documents/logic/nd30-layout.js and re-validated against docs/VIETNAMESE_OFFICE_SPEC.md.
Rule widths follow the text length (II.1b motto rule = line length; II.2b/II.5b rules 1/3-1/2 of the line).
"""
import re
import unicodedata

from .nd30 import format_issue_date, format_number, get_type, rules

RULE_FRACTION_AGENCY = 0.4  # spec II.2b: rule is 1/3-1/2 of the agency-name line
RULE_FRACTION_TITLE = 0.4   # spec II.5b: same for the summary under the type name
_NARROW = set("ijlt.,;:'!|()[]/ fIr-")
_WIDE = set("mwMW")


def estimate_text_width_mm(text, size_pt, bold=False):
    """Rough Times New Roman advance width. Diacritics do not change width, so measure the NFD base letters."""
    em = 0.0
    for ch in unicodedata.normalize("NFD", text):
        if unicodedata.combining(ch):
            continue
        if ch in _NARROW:
            em += 0.3
        elif ch in _WIDE:
            em += 0.9 if ch.isupper() else 0.78
        elif ch.isupper():
            em += 0.72
        else:
            em += 0.5
    return em * size_pt * 0.3528 * (1.04 if bold else 1.0)


def _run(text, size, **extra):
    return {"text": text, "size": size, "bold": False, "italic": False, **extra}


def _para(runs, align="center", **extra):
    return {"type": "paragraph", "align": align, "runs": runs, **extra}


def _lines(text):
    return [line.strip() for line in str(text or "").splitlines() if line.strip()]


def _value(fields, key, ph):
    return str(fields.get(key) or "").strip() or ph[key]


def _ruled(text, size, fraction, cell_mm):
    """Rule width = fraction of the estimated line width, never wider than the cell."""
    return round(min(estimate_text_width_mm(text, size, True) * fraction, cell_mm), 1)


def _header(t, fields, d, text_mm):
    ph, T = d["placeholders"], d["typography"]
    left_mm, right_mm = text_mm * d["layoutRules"]["headerWidthsPct"][0] / 100, text_mm * d["layoutRules"]["headerWidthsPct"][1] / 100
    left = []
    if str(fields.get("parentAgency") or "").strip():
        left.append(_para([_run(fields["parentAgency"].strip().upper(), T["parentAgency"])]))
    agency = _value(fields, "agency", ph).upper()
    left.append(_para([_run(agency, T["agency"], bold=True)], rule_mm=_ruled(agency, T["agency"], RULE_FRACTION_AGENCY, left_mm)))
    symbol = _value(fields, "symbol", ph).upper()
    left.append(_para([_run("Số: %s/%s" % (format_number(fields.get("number")) or ph["number"], symbol), T["number"])]))
    if t["officialLetter"]:
        # "V/v" already means "về việc": drop a typed "Về việc"/"V/v" so it is not doubled.
        summary = re.sub(r"^\s*(?:v/v|về việc)\s*:?\s*", "", _value(fields, "summary", ph), flags=re.I)
        left.append(_para([_run("V/v " + summary, T["summaryOfficialLetter"])], spacing_before_pt=6))
    date = format_issue_date(fields.get("date")) or ph["date"]
    motto = d["motto"]
    right = [_para([_run(d["nationalTitle"], T["nationalTitle"], bold=True)]),
             _para([_run(motto, T["motto"], bold=True)], rule_mm=round(min(estimate_text_width_mm(motto, T["motto"], True), right_mm), 1)),
             _para([_run("%s, %s" % (_value(fields, "place", ph), date), T["placeDate"], italic=True)], spacing_before_pt=6)]
    return {"type": "two-column", "widthsPct": d["layoutRules"]["headerWidthsPct"], "left": left, "right": right}


def _title_and_addressee(t, fields, d, text_mm):
    ph, T = d["placeholders"], d["typography"]
    blocks = []
    if not t["officialLetter"]:
        summary = _value(fields, "summary", ph)
        blocks += [_para([_run(t["typeName"], T["typeName"], bold=True)], spacing_before_pt=12),
                   _para([_run(summary, T["summary"], bold=True)], rule_mm=_ruled(summary, T["summary"], RULE_FRACTION_TITLE, text_mm))]
    if t["kinhGui"]:
        targets = _lines(fields.get("kinhGui"))
        if len(targets) <= 1:
            blocks.append(_para([_run("Kính gửi: %s." % (targets[0] if targets else ph["kinhGui"]), T["kinhGui"])], spacing_before_pt=12))
        else:
            # Phu luc I, II.9b: one recipient per line, the dashes aligned under the colon of "Kinh gui:".
            items = ["- %s%s" % (x, "." if i == len(targets) - 1 else ";") for i, x in enumerate(targets)]
            label_mm = estimate_text_width_mm("Kính gửi", T["kinhGui"])
            widest = max(estimate_text_width_mm(x, T["kinhGui"]) for x in items)
            left_mm = round(max(0.0, min((text_mm - label_mm - widest) / 2, text_mm / 3)), 1)
            blocks.append(_para([_run("Kính gửi:", T["kinhGui"])], "left", spacing_before_pt=12, indent_left_mm=left_mm))
            blocks += [_para([_run(x, T["kinhGui"])], "left", indent_left_mm=round(left_mm + label_mm, 1)) for x in items]
    return blocks


def _body(fields, d):
    T = d["typography"]
    texts = _lines(fields.get("body")) or [d["placeholders"]["body"]]
    return [_para([_run(x, T["body"])], "justify", indent_first_mm=T["bodyFirstLineIndentMm"],
                  spacing_after_pt=T["paragraphSpacingPt"], line_spacing=T["lineSpacing"]) for x in texts]


def _signature(fields, d):
    ph, T = d["placeholders"], d["typography"]
    items = [re.sub(r"[;.]$", "", re.sub(r"^[-–]\s*", "", x)) for x in _lines(fields.get("recipients"))]
    if not any(re.match(r"Lưu\b", x, re.I) for x in items):
        items.append(d["layoutRules"]["recipientsAppendLuuIfMissing"])
    left = [_para([_run("Nơi nhận:", T["recipientsHeading"], bold=True, italic=True)], "left")]
    left += [_para([_run("- %s%s" % (x, "." if i == len(items) - 1 else ";"), T["recipientsList"])], "left") for i, x in enumerate(items)]
    right = [_para([_run(_value(fields, "signerAuthority", ph).upper(), T["signerAuthority"], bold=True)])]
    if str(fields.get("signerTitle") or "").strip():
        right.append(_para([_run(fields["signerTitle"].strip().upper(), T["signerAuthority"], bold=True)]))
    right += [_para([_run("", T["signerName"])], spacing_after_pt=60), _para([_run(_value(fields, "signerName", ph), T["signerName"], bold=True)])]
    return {"type": "two-column", "widthsPct": d["layoutRules"]["signatureWidthsPct"], "left": left, "right": right, "spacing_before_pt": 12}


def build_layout(type_id, fields=None, margins_mm=None, data=None):
    """Editor-independent layout: {'typeId', 'textWidthMm', 'blocks': [paragraph | two-column]}."""
    d = data or rules()
    t = get_type(type_id, d)
    if t is None:
        raise ValueError("unknown-type")
    fields = fields or {}
    m = margins_mm or d["defaultMarginsMm"]
    text_mm = d["pageSizeMm"]["width"] - float(m["left"]) - float(m["right"])
    blocks = [_header(t, fields, d, text_mm)] + _title_and_addressee(t, fields, d, text_mm) + _body(fields, d) + [_signature(fields, d)]
    return {"typeId": type_id, "textWidthMm": text_mm, "blocks": blocks}


def layout_to_text(layout):
    """Plain-text preview of a layout (what the wizard shows before anything is written)."""
    def lines(paras):
        return ["".join(r["text"] for r in p["runs"]) for p in paras]
    out = []
    for block in layout["blocks"]:
        if block["type"] == "paragraph":
            out.append("".join(r["text"] for r in block["runs"]))
        else:
            out += lines(block["left"]) + ["  ---"] + lines(block["right"])
    return "\n".join(out)
