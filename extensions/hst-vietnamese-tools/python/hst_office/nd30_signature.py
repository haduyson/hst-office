# SPDX-License-Identifier: AGPL-3.0-only
"""Signature part of a document (pure logic): recipients and signer, or the two signers of minutes (form 1.9)."""
import re

from .nd30_blocks import lines_of, para, run


def recipient_items(t, fields, d):
    """Recipient lines: 'Như trên' after a Kính gửi (Annex I, II.9b, form 1.5), then the rest, then the archive line."""
    ph = d["placeholders"]
    items = [re.sub(r"[;.]$", "", re.sub(r"^[-–]\s*", "", x)) for x in lines_of(fields.get("recipients"))]
    if not items:
        items = [ph["recipients"]]
    if t.get("asAbove") and not any(re.match(r"Như trên\b", x, re.I) for x in items):
        items.insert(0, "Như trên")
    if not any(re.match(r"Lưu\b", x, re.I) for x in items):
        items.append(d["layoutRules"]["recipientsAppendLuuIfMissing"])
    return items


def recipients_cell(t, fields, d):
    T = d["typography"]
    items = recipient_items(t, fields, d)
    cell = [para([run("Nơi nhận:", T["recipientsHeading"], bold=True, italic=True)], "left", role="RecipientsHeading")]
    return cell + [para([run("- %s%s" % (x, "." if i == len(items) - 1 else ";"), T["recipientsList"])], "left", role="RecipientsList")
                   for i, x in enumerate(items)]


def signer_cell(authority, name, d, title=""):
    """Authority, title, room for the signature and the stamp, name; the gap is the same in both creation paths."""
    T = d["typography"]
    cell = [para([run(authority.upper(), T["signerAuthority"], bold=True)], role="Authority")]
    if title.strip():
        cell.append(para([run(title.strip().upper(), T["signerAuthority"], bold=True)], role="Authority"))
    cell.append(para([run("", T["signerName"])], role="SignatureSpace", spacing_after_pt=d["signatureGapPt"]))
    cell.append(para([run(name, T["signerName"], bold=True)], role="Signer"))
    return cell


def _value(fields, key, ph):
    return str(fields.get(key) or "").strip() or ph[key]


def _contact(fields, d, template):
    """Form 1.5, box 13: contact details under a full-width rule, only when wanted (the template shows where they go)."""
    text = str(fields.get("contact") or "").strip() or (d["placeholders"]["contact"] if template else "")
    if not text:
        return []
    return [para([run(text, d["typography"]["contact"])], "left", role="Contact", top_rule=True, spacing_before_pt=12)]


def signature_blocks(t, fields, d, text_mm):
    ph, pct = d["placeholders"], d["layoutRules"]["signatureWidthsPct"]
    template = "_template" in fields
    if t.get("structure") == "minutes":
        secretary = signer_cell("THƯ KÝ", _value(fields, "secretaryName", ph), d)
        chair = signer_cell(_value(fields, "signerAuthority", {"signerAuthority": "CHỦ TỌA"}), _value(fields, "signerName", ph), d,
                            str(fields.get("signerTitle") or ""))
        grid = {"type": "grid", "name": "Signature", "widthsPct": pct, "spacing_before_pt": 12, "rows": [{"cells": [secretary, chair]}]}
        return [grid] + recipients_cell(t, fields, d)
    authority = _value(fields, "signerAuthority", ph)
    right = signer_cell(authority, _value(fields, "signerName", ph), d, str(fields.get("signerTitle") or ""))
    grid = {"type": "grid", "name": "Signature", "widthsPct": pct, "spacing_before_pt": 12, "rows": [{"cells": [recipients_cell(t, fields, d), right]}]}
    return [grid] + (_contact(fields, d, template) if t.get("officialLetter") else [])
