# SPDX-License-Identifier: AGPL-3.0-only
"""The top of a document (pure logic): header grid of the state profiles, title, addressee, e-signature line, annex title."""
import re

from .nd30 import format_issue_date, format_number, format_symbol, parse_date_input
from .nd30_blocks import lines_of, para, run
from .nd30_metrics import ASCENT_EM, rule_for, text_width_mm
from .nd30_rule_length import FIELD as RULE_FIELD, agency_rule_mm


def value_of(fields, key, ph):
    return str(fields.get(key) or "").strip() or ph[key]


def number_text(t, fields, d):
    ph = d["placeholders"]
    number = format_number(fields.get("number")) or ph["number"]
    if d.get("numberWithYear"):  # Decree 187, Annex I, II.3: number/year/type-agency
        date = parse_date_input(fields.get("date"))
        number = "%s/%s" % (number, date.year if date else ph["year"])
    symbol = str(fields.get("symbol") or "").strip()
    if symbol:
        return "Số: %s/%s" % (number, format_symbol(symbol, t.get("abbr", "")))
    if t.get("officialLetter"):
        return "Số: %s/%s-%s" % (number, ph["symbolAgency"], ph["symbolUnit"])
    if t.get("abbr"):
        return "Số: %s/%s-%s" % (number, t["abbr"], ph["symbolAgency"])
    return "Số: %s/%s" % (number, ph["symbolAgency"])


def agency_cell(t, fields, d, cell_mm):
    ph, T, R = d["placeholders"], d["typography"], d["ruleWidthMm"]
    cell, parent = [], ""
    typed_parent = str(fields.get("parentAgency") or "").strip()
    if typed_parent or ("_template" in fields and not t.get("noParent")):
        parent = value_of(fields, "parentAgency", ph).upper()
        cell.append(para([run(parent, T["parentAgency"])], role="ParentAgency"))
    agency = value_of(fields, "agency", ph).upper()
    # the length the user chose in the wizard (nd30_rule_length); without a choice the profile's fraction
    rule_mm = (agency_rule_mm(fields[RULE_FIELD], agency, parent, T, cell_mm, R["agencyFraction"]) if fields.get(RULE_FIELD)
               else rule_for(agency, T["agency"], True, cell_mm, R["agencyFraction"]))
    cell.append(para([run(agency, T["agency"], bold=True)], role="Agency", rule_mm=rule_mm))
    return cell


def national_cell(d, cell_mm):
    T = d["typography"]
    motto = d["motto"]
    return [para([run(d["nationalTitle"], T["nationalTitle"], bold=True)], role="NationalTitle"),
            para([run(motto, T["motto"], bold=True)], role="Motto", rule_mm=round(min(text_width_mm(motto, T["motto"], True), cell_mm), 2))]


def date_para(fields, d, role="PlaceDate", before=6):
    ph, T = d["placeholders"], d["typography"]
    date = format_issue_date(fields.get("date")) or ph["date"]
    return para([run("%s, %s" % (value_of(fields, "place", ph), date), T["placeDate"], italic=True)], role=role, spacing_before_pt=before)


def number_gap(T):
    """Space above the number so its first line shares the baseline of the larger date, even when either one wraps."""
    return round(6 + (T["placeDate"] - T["number"]) * ASCENT_EM, 2)


def header_grid(t, fields, d, text_mm):
    """Agency | national title, then number | date in one row so they share a baseline (II.4c), then the V/v of a letter."""
    pct, T = d["layoutRules"]["headerWidthsPct"], d["typography"]
    left_mm, right_mm = text_mm * pct[0] / 100, text_mm * pct[1] / 100
    rows = [{"cells": [agency_cell(t, fields, d, left_mm), national_cell(d, right_mm)]}]
    number = [] if t.get("noNumber") else [para([run(number_text(t, fields, d), T["number"])], role="Number", spacing_before_pt=number_gap(T))]
    date = [] if t.get("noDate") else [date_para(fields, d)]
    if number or date:
        rows.append({"cells": [number, date]})
    if t.get("officialLetter"):
        # "V/v" already means "về việc": drop a typed "Về việc"/"V/v" so it is not doubled.
        summary = re.sub(r"^\s*(?:v/v|về việc)\s*:?\s*", "", value_of(fields, "summary", d["placeholders"]), flags=re.I)
        rows.append({"cells": [[para([run("V/v " + summary, T["summaryOfficialLetter"])], role="OfficialSummary", spacing_before_pt=6)], []]})
    return {"type": "grid", "name": "Header", "widthsPct": pct, "rows": rows}


def title_blocks(t, fields, d, text_mm):
    """Type name, summary, the subtitle lines of the form, and the rule under the last of them."""
    ph, T, R = d["placeholders"], d["typography"], d["ruleWidthMm"]
    blocks = [para([run(t["typeName"], T["typeName"], bold=True)], role="TypeName", spacing_before_pt=0 if t.get("noHeader") else 18)]
    last = t["typeName"]
    if not t.get("noSummary"):
        summary = t.get("summaryFixed") or value_of(fields, "summary", ph)
        if not re.match(r"(?i)(về việc|ban hành|phê duyệt)\b", summary):
            summary = t.get("summaryPrefix", "") + summary
        blocks.append(para([run(summary, T["summary"], bold=True)], role="Summary"))
        last = summary
    for line in t.get("subtitle", []):
        text, italic = line[0], line[1]
        bold = len(line) > 2 and line[2]
        blocks.append(para([run(text, T["summary"], bold=bool(bold), italic=bool(italic))], role="Subtitle"))
    fraction = R["titleFraction"]
    if fraction:
        blocks[-1]["rule_mm"] = rule_for(last, T["summary"], True, text_mm, fraction)
    blocks[-1]["spacing_after_pt"] = 6
    return blocks


def addressee_blocks(t, fields, d, text_mm):
    ph, T = d["placeholders"], d["typography"]
    targets = lines_of(fields.get("kinhGui"))
    size = T["kinhGui"]
    if len(targets) <= 1:
        return [para([run("Kính gửi: %s." % (targets[0] if targets else ph["kinhGui"]), size)], role="KinhGui", spacing_before_pt=12, spacing_after_pt=6)]
    # Annex I, II.9b: one recipient per line, the dashes aligned under the colon of "Kinh gui:".
    items = ["- %s%s" % (x, "." if i == len(targets) - 1 else ";") for i, x in enumerate(targets)]
    label_mm = text_width_mm("Kính gửi", size)
    widest = max(text_width_mm(x, size) for x in items)
    left_mm = round(max(0.0, min((text_mm - label_mm - widest) / 2, text_mm / 3)), 2)
    blocks = [para([run("Kính gửi:", size)], "left", role="KinhGui", spacing_before_pt=12, indent_left_mm=left_mm)]
    blocks += [para([run(x, size)], "left", role="KinhGui", indent_left_mm=round(left_mm + label_mm, 2)) for x in items]
    blocks[-1]["spacing_after_pt"] = 6
    return blocks


def esign_line(text="Số: [số, ký hiệu văn bản]; [ngày/tháng/năm]; [giờ: phút: giây]"):
    """Annex I, I.3 and form 2.2: signing information at the top right of the first page, size 10, upright, black."""
    return para([run(text, 10)], "right", role="EsignInfo", spacing_after_pt=6)


def annex_title(t, d, text_mm):
    """Forms 2.1, 2.2 and the annex rule of the other profiles: word and number, title, reference to the document."""
    T = d["typography"]
    number = "[số La Mã]" if d.get("annexNumbering", "roman") == "roman" else "[số]"
    ref = "(Kèm theo Văn bản số [số, ký hiệu] ngày [ngày] tháng [tháng] năm [năm] của [tên cơ quan, tổ chức])"
    title = "[Tiêu đề của Phụ lục]"
    blocks = [para([run("Phụ lục " + number, T["body"], bold=True)], role="AnnexTitle"),
              para([run(title, T["body"], bold=True)], role="Summary"),
              para([run(ref, T["body"], italic=True)], role="Subtitle", spacing_after_pt=6)]
    if d["ruleWidthMm"]["titleFraction"]:
        blocks[-1]["rule_mm"] = rule_for(title, T["body"], True, text_mm, d["ruleWidthMm"]["titleFraction"])
    return blocks
