# SPDX-License-Identifier: AGPL-3.0-only
"""Copies and the office forms that are not ordinary documents (pure logic): forms 3.1, 3.2, the envelope and the ĐẾN stamp."""
from .nd30_blocks import para, run
from .nd30_heading import agency_cell, date_para, esign_line, value_of
from .nd30_signature import recipients_cell, signer_cell, value

ENVELOPE = {"width": 220, "height": 110, "top": 10, "bottom": 10, "left": 12, "right": 12}


def _spaced(cell):
    """Room between the number row and the recipients and signer of a copy."""
    return [{**cell[0], "spacing_before_pt": 12}] + cell[1:]


def copy_blocks(t, fields, d, text_mm):
    """Form 3.1, Annex I, II.II.2.a: under a full-width rule, agency | form of copy, number | date, recipients | signer."""
    ph, T, pct = d["placeholders"], d["typography"], d["layoutRules"]["headerWidthsPct"]
    agency = str(fields.get("agency") or "").strip() or "[CƠ QUAN, TỔ CHỨC SAO]"
    left_mm = text_mm * pct[0] / 100
    rows = [{"cells": [agency_cell({**t, "noParent": True}, {"agency": agency}, d, left_mm),
                       [para([run(t["copyForm"], T["typeName"], bold=True)], role="CopyForm")]]},
            {"cells": [[para([run("Số: %s/%s-%s" % (fields.get("number") or ph["number"], t["abbr"], ph["symbolAgency"]), T["number"])], role="Number", spacing_before_pt=6.89)],
                       [date_para(fields, d)]]},
            {"cells": [_spaced(recipients_cell(t, fields, d)), _spaced(signer_cell(value(fields, "signerAuthority", ph), value(fields, "signerName", ph), d, str(fields.get("signerTitle") or "")))]}]
    return [para([run("", 1)], role="CopyRule", top_rule=True, spacing_before_pt=12),
            {"type": "grid", "name": "Signature", "widthsPct": pct, "rows": rows}]


def copy_esign_line(fields=None):
    """Form 3.2: 'SAO Y; cơ quan sao; thời gian ký' at the top right of the first page."""
    return esign_line("[SAO Y, SAO LỤC hoặc TRÍCH SAO]; [Tên cơ quan, tổ chức sao]; [ngày/tháng/năm; giờ: phút: giây]")


def envelope_blocks(fields, d):
    """Annex IV.II. The decree gives the content, not a size; a DL envelope is HST's choice (ENVELOPE, in mm)."""
    ph, T = d["placeholders"], d["typography"]
    agency = value_of(fields, "agency", ph).upper()
    logo = [para([run("Biểu tượng của cơ quan (Nếu có)", 10)], role="EnvelopeLogo")]
    info = [para([run(agency, T["agency"], bold=True)], "left", role="EnvelopeAgency")]
    for label in ("Địa chỉ: [địa chỉ]", "Điện thoại: [số điện thoại]    Fax: [số fax]", "E-Mail: [thư điện tử]    Website: [trang thông tin điện tử]"):
        info.append(para([run(label, 11)], "left", role="EnvelopeLine"))
    number = para([run("Số/ký hiệu văn bản: [số, ký hiệu]", T["number"])], "left", role="EnvelopeNumber", spacing_before_pt=6)
    addressee = para([run("Kính gửi: ", T["kinhGui"], bold=True, italic=True), run("[Tên, địa chỉ cơ quan, tổ chức, cá nhân nhận văn bản]", T["kinhGui"])], "left",
                     role="EnvelopeTo", spacing_before_pt=18, indent_left_mm=60)
    return [{"type": "grid", "name": "Header", "widthsPct": [20, 80], "rows": [{"cells": [logo, info]}]}, number, addressee]


def stamp_blocks(fields, d):
    """Annex IV.V: a rectangle of 35 x 50 mm."""
    ph = d["placeholders"]
    agency = value_of(fields, "agency", {"agency": "[TÊN CƠ QUAN, TỔ CHỨC]"}).upper()
    line = lambda text, **k: [para([run(text, 11, **k)], "left", role="StampText")]
    rows = [{"cells": [line(agency, bold=True)], "merged": True, "heightMm": 8},
            {"cells": [[para([run("ĐẾN", 13, bold=True)], role="StampTitle")], line("Số: [số]") + line("Ngày: [ngày]")], "heightMm": 13},
            {"cells": [line("Chuyển: [đơn vị, cá nhân]")], "merged": True, "heightMm": 7},
            {"cells": [line("Số và ký hiệu HS: [số]")], "merged": True, "heightMm": 7}]
    return [{"type": "grid", "name": "Form", "widthsPct": [30, 70], "widthMm": 50, "rows": rows, "borders": True}]
