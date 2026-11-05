# SPDX-License-Identifier: AGPL-3.0-only
"""Party documents (pure logic), a profile of its own: Quy định 399-QĐ/TW and Hướng dẫn 05-HD/VPTW (2026), Phụ lục 1-3.

They share nothing with the state forms but the renderer: heading "ĐẢNG CỘNG SẢN VIỆT NAM", a star under the agency, number
as "Số 05-QĐ/TU", five dashes under the summary, an underlined "Nơi nhận:", line spacing fixed in points.
"""
import re

from .nd30 import format_issue_date, format_number, format_symbol
from .nd30_blocks import lines_of, para, run
from .nd30_metrics import text_width_mm
from .nd30_signature import signer_cell, value


def number_text(t, fields, d):
    """Guide 05, II.3.2.2: a hyphen after the number, a slash between the type and the agency."""
    number = format_number(fields.get("number")) or d["placeholders"]["number"]
    agency = str(fields.get("symbol") or "").strip().split("/")[-1]
    agency = format_symbol(agency) if agency else d["placeholders"]["symbolAgency"]
    return "Số %s-%s/%s" % (number, t["abbr"], agency) if t.get("abbr") else "Số %s/%s" % (number, agency)


def date_para(fields, d):
    ph, T = d["placeholders"], d["typography"]
    date = format_issue_date(fields.get("date")) or ph["date"]
    return para([run("%s, %s" % (value(fields, "place", ph), date), T["placeDate"], italic=True)], role="PlaceDate")


def header_grid(t, fields, d, text_mm):
    ph, T = d["placeholders"], d["typography"]
    pct = d["layoutRules"]["headerWidthsPct"]
    left = []
    parent = str(fields.get("parentAgency") or "").strip()
    if parent or "_template" in fields:
        left.append(para([run((parent or ph["parentAgency"]).upper(), T["parentAgency"])], role="ParentAgency"))
    left.append(para([run(value(fields, "agency", ph).upper(), T["agency"], bold=True)], role="Agency"))
    left.append(para([run("*", T["agency"])], role="AgencyStar"))
    title = d["nationalTitle"]
    right = [para([run(title, T["nationalTitle"], bold=True)], role="NationalTitle",
                  rule_mm=round(min(text_width_mm(title, T["nationalTitle"], True), text_mm * pct[1] / 100), 2))]
    rows = [{"cells": [left, right]}, {"cells": [[para([run(number_text(t, fields, d), T["number"])], role="Number")], [date_para(fields, d)]]}]
    if t.get("officialLetter"):
        summary = re.sub(r"^\s*(?:v/v|về việc)\s*:?\s*", "", value(fields, "summary", ph), flags=re.I)
        rows.append({"cells": [[para([run("về việc " + summary, T["summaryOfficialLetter"], italic=True)], role="OfficialSummary")], []]})
    return {"type": "grid", "name": "Header", "widthsPct": pct, "rows": rows}


def title_blocks(t, fields, d):
    ph, T = d["placeholders"], d["typography"]
    blocks = [para([run(t["typeName"], T["typeName"], bold=True)], role="TypeName", spacing_before_pt=18)]
    if not t.get("noSummary"):
        blocks.append(para([run(value(fields, "summary", ph), T["summary"], bold=True)], role="Summary"))
    blocks.append(para([run("-----", T["summary"])], role="TitleDashes", spacing_after_pt=6))
    return blocks


def addressee_blocks(t, fields, d):
    """Guide 05, II.9.2: 'Kính gửi:' or 'Kính trình:' in italics, then the recipients, one per line, in the middle."""
    ph, T = d["placeholders"], d["typography"]
    targets = lines_of(fields.get("kinhGui")) or [ph["kinhGui"]]
    blocks = [para([run(t.get("addresseeLabel", "Kính gửi:"), T["kinhGui"], italic=True)], "center", role="KinhGui", spacing_before_pt=12)]
    for i, target in enumerate(targets):
        blocks.append(para([run("- %s%s" % (target, "." if i == len(targets) - 1 else ";"), T["kinhGuiList"])], "center", role="KinhGuiList"))
    blocks[-1]["spacing_after_pt"] = 6
    return blocks


def recipients_cell(t, fields, d):
    T = d["typography"]
    items = [re.sub(r"[;.]$", "", re.sub(r"^[-–]\s*", "", x)) for x in lines_of(fields.get("recipients"))] or [d["placeholders"]["recipients"]]
    if t.get("asAbove") and not any(re.match(r"Như trên\b", x, re.I) for x in items):
        items.insert(0, "Như trên")
    if not any(re.match(r"Lưu\b", x, re.I) for x in items):
        items.append(d["layoutRules"]["recipientsAppendLuuIfMissing"])
    cell = [para([run("Nơi nhận:", T["recipientsHeading"], underline=True)], "left", role="RecipientsHeading")]
    return cell + [para([run("- %s%s" % (x, "." if i == len(items) - 1 else ";"), T["recipientsList"])], "left", role="RecipientsList") for i, x in enumerate(items)]


def signature_blocks(t, fields, d):
    ph, pct = d["placeholders"], d["layoutRules"]["signatureWidthsPct"]
    title = str(fields.get("signerTitle") or "").strip() or ("" if "signerAuthority" in fields else ph["signerTitle"])
    if t.get("structure") == "dang-minutes":  # II.7.2.4: the person responsible on the right
        left = signer_cell("NGƯỜI GHI BIÊN BẢN", value(fields, "secretaryName", ph), d)
        right = signer_cell(value(fields, "signerAuthority", {"signerAuthority": "CHỦ TRÌ HỘI NGHỊ"}), value(fields, "signerName", ph), d)
        return [{"type": "grid", "name": "Signature", "widthsPct": pct, "spacing_before_pt": 12, "rows": [{"cells": [left, right]}]}]
    right = signer_cell(value(fields, "signerAuthority", ph), value(fields, "signerName", ph), d, title)
    return [{"type": "grid", "name": "Signature", "widthsPct": pct, "spacing_before_pt": 12, "rows": [{"cells": [recipients_cell(t, fields, d), right]}]}]


def copy_stamp_rows(fields, d):
    """Guide 05, Phụ lục 3: the 'BẢN SAO VĂN BẢN' stamp, 80 x 50 mm, red when stamped; here its fields to fill."""
    T = d["typography"]
    head = [para([run("BẢN SAO VĂN BẢN", 13, bold=True)], role="StampTitle")]
    labels = ["(1) Cơ quan sao: [tên cơ quan]", "(2) Số, ký hiệu bản sao: [số]-BS/[viết tắt CQ]", "(3) Hình thức sao: [sao y, sao lục, trích sao]",
              "(4) Địa danh và ngày tháng năm sao: [địa danh, ngày tháng năm]", "(5) Nơi nhận bản sao: [cơ quan, đơn vị, cá nhân]"]
    return head + [para([run(x, min(T["recipientsList"], 12))], "left", role="StampText") for x in labels]


def copy_blocks(t, fields, d):
    """Guide 05, II.III.2.2: under a full-width rule, the stamp on the left and whoever signs the copy on the right."""
    ph, pct = d["placeholders"], d["layoutRules"]["signatureWidthsPct"]
    right = signer_cell(value(fields, "signerAuthority", ph), value(fields, "signerName", ph), d, str(fields.get("signerTitle") or ""))
    stamp = {"type": "grid", "name": "Signature", "widthsPct": pct, "spacing_before_pt": 6, "rows": [{"cells": [copy_stamp_rows(fields, d), right]}]}
    return [para([run("", 1)], role="CopyRule", top_rule=True, spacing_before_pt=12), stamp]
