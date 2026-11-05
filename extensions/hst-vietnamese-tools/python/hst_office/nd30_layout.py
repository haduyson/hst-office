# SPDX-License-Identifier: AGPL-3.0-only
"""One layout for both creation paths (pure logic, no `uno`): the installed .ott templates and the wizard render the
blocks built here, so they cannot drift apart. Blocks are paragraphs and grids (borderless or ruled tables).

Provenance: ported from archive/onlyoffice-plugin-first@e0517d71c813535087c401b2683bec0784d71fd8
extensions/vn-admin-documents/logic/nd30-layout.js and re-validated against the annexes named in docs/TEMPLATES.md.
"""
import re

from .data_files import load_data
from .nd30 import format_issue_date, format_number, format_symbol, get_type, profile_rules
from .nd30_blocks import body_blocks, lines_of, para, run
from .nd30_metrics import ASCENT_EM, rule_for, text_width_mm
from .nd30_signature import signature_blocks


def value_of(fields, key, ph):
    return str(fields.get(key) or "").strip() or ph[key]


def number_text(t, fields, d):
    ph = d["placeholders"]
    number = format_number(fields.get("number")) or ph["number"]
    symbol = str(fields.get("symbol") or "").strip()
    if symbol:
        return "Số: %s/%s" % (number, format_symbol(symbol, t.get("abbr", "")))
    if t.get("officialLetter"):
        return "Số: %s/%s-%s" % (number, ph["symbolAgency"], ph["symbolUnit"])
    return "Số: %s/%s-%s" % (number, t.get("abbr", ""), ph["symbolAgency"])


def _agency_cell(fields, d, cell_mm):
    ph, T, R = d["placeholders"], d["typography"], d["ruleWidthMm"]
    cell = []
    if str(fields.get("parentAgency") or "").strip() or "_template" in fields:
        cell.append(para([run(value_of(fields, "parentAgency", ph).upper(), T["parentAgency"])], role="ParentAgency"))
    agency = value_of(fields, "agency", ph).upper()
    cell.append(para([run(agency, T["agency"], bold=True)], role="Agency",
                     rule_mm=rule_for(agency, T["agency"], True, cell_mm, R["agencyFraction"])))
    return cell


def _national_cell(d, cell_mm):
    T = d["typography"]
    motto = d["motto"]
    return [para([run(d["nationalTitle"], T["nationalTitle"], bold=True)], role="NationalTitle"),
            para([run(motto, T["motto"], bold=True)], role="Motto",
                 rule_mm=round(min(text_width_mm(motto, T["motto"], True), cell_mm), 2))]


def _date_para(fields, d):
    ph, T = d["placeholders"], d["typography"]
    date = format_issue_date(fields.get("date")) or ph["date"]
    text = "%s, %s" % (value_of(fields, "place", ph), date)
    return para([run(text, T["placeDate"], italic=True)], role="PlaceDate", spacing_before_pt=6)


def _number_gap(T):
    """Space above the number so its first line shares the baseline of the larger date, even when either one wraps."""
    return round(6 + (T["placeDate"] - T["number"]) * ASCENT_EM, 2)


def header_grid(t, fields, d, text_mm):
    """Agency | national title, then number | date in one row so they share a baseline (II.4c), then the V/v of a letter."""
    pct = d["layoutRules"]["headerWidthsPct"]
    T = d["typography"]
    left_mm, right_mm = text_mm * pct[0] / 100, text_mm * pct[1] / 100
    date = [] if t.get("noDate") else [_date_para(fields, d)]
    rows = [{"cells": [_agency_cell(fields, d, left_mm), _national_cell(d, right_mm)]},
            {"cells": [[para([run(number_text(t, fields, d), T["number"])], role="Number", spacing_before_pt=_number_gap(T))], date]}]
    if t.get("officialLetter"):
        # "V/v" already means "về việc": drop a typed "Về việc"/"V/v" so it is not doubled.
        summary = re.sub(r"^\s*(?:v/v|về việc)\s*:?\s*", "", value_of(fields, "summary", d["placeholders"]), flags=re.I)
        rows.append({"cells": [[para([run("V/v " + summary, T["summaryOfficialLetter"])], role="OfficialSummary", spacing_before_pt=6)], []]})
    return {"type": "grid", "name": "Header", "widthsPct": pct, "rows": rows}


def _title(t, fields, d, text_mm):
    ph, T, R = d["placeholders"], d["typography"], d["ruleWidthMm"]
    summary = value_of(fields, "summary", ph)
    if fields.get("summary") is None or not str(fields.get("summary")).strip() or not summary.lower().startswith("về việc"):
        summary = t.get("summaryPrefix", "") + summary
    return [para([run(t["typeName"], T["typeName"], bold=True)], role="TypeName", spacing_before_pt=12),
            para([run(summary, T["summary"], bold=True)], role="Summary",
                 rule_mm=rule_for(summary, T["summary"], True, text_mm, R["titleFraction"]))]


def _addressee(fields, d, text_mm):
    ph, T = d["placeholders"], d["typography"]
    targets = lines_of(fields.get("kinhGui"))
    size = T["kinhGui"]
    if len(targets) <= 1:
        return [para([run("Kính gửi: %s." % (targets[0] if targets else ph["kinhGui"]), size)], role="KinhGui",
                     spacing_before_pt=12, spacing_after_pt=6)]
    # Annex I, II.9b: one recipient per line, the dashes aligned under the colon of "Kinh gui:".
    items = ["- %s%s" % (x, "." if i == len(targets) - 1 else ";") for i, x in enumerate(targets)]
    label_mm = text_width_mm("Kính gửi", size)
    widest = max(text_width_mm(x, size) for x in items)
    left_mm = round(max(0.0, min((text_mm - label_mm - widest) / 2, text_mm / 3)), 2)
    blocks = [para([run("Kính gửi:", size)], "left", role="KinhGui", spacing_before_pt=12, indent_left_mm=left_mm)]
    blocks += [para([run(x, size)], "left", role="KinhGui", indent_left_mm=round(left_mm + label_mm, 2)) for x in items]
    blocks[-1]["spacing_after_pt"] = 6
    return blocks


def skeleton(t):
    """Placeholder paragraphs of a type."""
    return load_data("skeletons-%s.json" % t["group"])[t["id"]]


def build_layout(type_id, fields=None, margins_mm=None, data=None, template=False):
    """{'typeId', 'profile', 'textWidthMm', 'blocks'}; `template` keeps every optional placeholder for the .ott."""
    t = get_type(type_id, data)
    if t is None:
        raise ValueError("unknown-type")
    d = profile_rules(t["profile"])
    fields = dict(fields or {})
    m = margins_mm or d["defaultMarginsMm"]
    text_mm = d["pageSizeMm"]["width"] - float(m["left"]) - float(m["right"])
    if template:
        fields = {"kinhGui": "[Cơ quan, tổ chức nhận văn bản 1]\n[Cơ quan, tổ chức nhận văn bản 2]"} if t.get("officialLetter") else {}
        fields["_template"] = "1"
    blocks = [header_grid(t, fields, d, text_mm)]
    if not t.get("officialLetter"):
        blocks += _title(t, fields, d, text_mm)
    if t.get("kinhGui"):
        blocks += _addressee(fields, d, text_mm)
    blocks += body_blocks(lines_of(fields.get("body")) or skeleton(t), d["typography"])
    blocks += signature_blocks(t, fields, d, text_mm)
    return {"typeId": type_id, "profile": t["profile"], "textWidthMm": text_mm, "blocks": blocks}


def _cell_text(paragraphs):
    return ["".join(r["text"] for r in p["runs"]) for p in paragraphs]


def layout_to_text(layout):
    """Plain-text form of a layout: every paragraph on its line, the cells of a grid separated."""
    out = []
    for block in layout["blocks"]:
        if block["type"] == "paragraph":
            out.append("".join(r["text"] for r in block["runs"]))
            continue
        for row in block["rows"]:
            for index, cell in enumerate(row["cells"]):
                out += (["  ---"] if index else []) + _cell_text(cell)
    return "\n".join(out)
