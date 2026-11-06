# SPDX-License-Identifier: AGPL-3.0-only
"""Signature part of a document (pure logic): recipients and signer, two signers of minutes and contracts, the copy block."""
import re

from .nd30_blocks import lines_of, para, run


def recipient_items(t, fields, d):
    """Recipient lines: 'Như trên' after a Kính gửi (Annex I, II.9b, form 1.5), then the rest, then the archive line."""
    ph = d["placeholders"]
    items = [re.sub(r"[;.]$", "", re.sub(r"^[-–]\s*", "", x)) for x in lines_of(fields.get("recipients"))]
    if not items and "recipientsDefault" not in t:
        items = [ph["recipients"]]
    if t.get("asAbove") and not any(re.match(r"Như trên\b", x, re.I) for x in items):
        items.insert(0, "Như trên")
    if not any(re.match(r"Lưu\b", x, re.I) for x in items):
        items.append("Lưu: VT" if "recipientsDefault" in t else d["layoutRules"]["recipientsAppendLuuIfMissing"])
    return items


def recipients_cell(t, fields, d):
    T = d["typography"]
    items = recipient_items(t, fields, d)
    cell = [para([run("Nơi nhận:", T["recipientsHeading"], bold=True, italic=True)], "left", role="RecipientsHeading")]
    return cell + [para([run("- %s%s" % (x, "." if i == len(items) - 1 else ";"), T["recipientsList"])], "left", role="RecipientsList")
                   for i, x in enumerate(items)]


def signer_cell(authority, name, d, title="", hint=""):
    """Authority, title, room for the signature and the stamp, name; the gap is the same in both creation paths."""
    T = d["typography"]
    cell = [para([run(authority.upper(), T["signerAuthority"], bold=True)], role="Authority")]
    if title.strip():
        cell.append(para([run(title.strip().upper(), T.get("signerTitle", T["signerAuthority"]), bold=not T.get("signerTitle"))], role="Authority"))
    if hint:
        cell.append(para([run(hint, T["signerName"], italic=True)], role="SignerHint"))
    cell.append(para([run("", T["signerName"])], role="SignatureSpace", spacing_after_pt=d["signatureGapPt"]))
    cell.append(para([run(name, T["signerName"], bold=True)], role="Signer"))
    return cell


def value(fields, key, ph):
    return str(fields.get(key) or "").strip() or ph[key]


def _grid(name, pct, cells):
    return {"type": "grid", "name": name, "widthsPct": pct, "spacing_before_pt": 12, "rows": [{"cells": c} for c in cells]}


def _contact(fields, d, template):
    """Form 1.5, box 13: contact details under a full-width rule, only when wanted (the template shows where they go)."""
    text = str(fields.get("contact") or "").strip() or (d["placeholders"].get("contact", "") if template else "")
    if not text:
        return []
    return [para([run(text, d["typography"]["contact"])], "left", role="Contact", top_rule=True, spacing_before_pt=12)]


def _leave_confirmation(d):
    """Form 1.10: confirmation of the place of leave, under the recipients."""
    T = d["typography"]
    lines = ["Xác nhận của cơ quan (tổ chức) hoặc chính quyền địa phương nơi nghỉ phép (nếu cần)", "(Chữ ký, dấu)"]
    cell = [para([run(x, T["recipientsHeading"], italic=True)], role="SignerHint") for x in lines]
    cell.append(para([run("", T["signerName"])], role="SignatureSpace", spacing_after_pt=d["signatureGapPt"]))
    cell.append(para([run("[Họ và tên]", T["signerName"], bold=True)], role="Signer"))
    return cell


def signature_blocks(t, fields, d):
    ph, pct = d["placeholders"], d["layoutRules"]["signatureWidthsPct"]
    template = "_template" in fields
    structure = t.get("structure")
    title = str(fields.get("signerTitle") or "")
    if structure == "minutes":
        secretary = signer_cell("THƯ KÝ", value(fields, "secretaryName", ph), d)
        chair = signer_cell(value(fields, "signerAuthority", {"signerAuthority": "CHỦ TỌA"}), value(fields, "signerName", ph), d, title)
        # the recipients follow the two signatures: they stay on the signatures' page, the heading with its list
        received = recipients_cell(t, fields, d)
        received = [{**p, "keep_with_next": True} for p in received[:-1]] + received[-1:]
        return [{**_grid("Signature", pct, [[secretary, chair]]), "keep_with_next": True}] + received
    if structure == "parties":
        left, right = t["signers"]
        hint = t.get("signerHint", "")
        return [_grid("Signature", pct, [[signer_cell(left, value(fields, "secretaryName", ph), d, hint=hint), signer_cell(right, value(fields, "signerName", ph), d, hint=hint)]])]
    right = signer_cell(value(fields, "signerAuthority", ph), value(fields, "signerName", ph), d, title)
    cells = [[recipients_cell(t, fields, d), right]]
    if structure == "leave":
        cells.append([_leave_confirmation(d), []])
    return [_grid("Signature", pct, cells)] + (_contact(fields, d, template) if t.get("officialLetter") else [])
