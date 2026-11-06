# SPDX-License-Identifier: AGPL-3.0-only
"""One layout for both creation paths (pure logic, no `uno`): the installed .ott templates and the wizard render the
blocks built here, so they cannot drift apart. Blocks are paragraphs and grids (borderless or ruled tables).

Provenance: ported from archive/onlyoffice-plugin-first@e0517d71c813535087c401b2683bec0784d71fd8
extensions/vn-admin-documents/logic/nd30-layout.js and re-validated against the annexes named in docs/TEMPLATES.md.
"""
from . import nd30_forms, nd30_heading, nd30_party, nd30_signature
from .data_files import load_data
from .nd30 import get_type, profile_rules
from .nd30_blocks import body_blocks, lines_of
from .nd30_portable import portable_blocks  # noqa: F401  (the renderers import it from here)

ATTACHED = {"qd": ("[TÊN LOẠI VĂN BẢN]", "(Kèm theo Quyết định số [số]/QĐ-[viết tắt CQ] ngày [ngày] tháng [tháng] năm [năm] của [cơ quan])"),
            "tt": ("QUY ĐỊNH/QUY CHẾ/ĐIỀU LỆ/DANH MỤC", "(Kèm theo Thông tư số [số]/[năm]/TT-[viết tắt bộ])")}


def skeleton(t):
    """Placeholder paragraphs of a type."""
    return load_data("skeletons-%s.json" % t["group"])[t["id"]]


def _body(t, fields, d):
    return body_blocks(lines_of(fields.get("body")) or skeleton(t), d)


def _attached(t, fields, d, text_mm):
    """The document issued with a decision or circular (forms 1.3, 15): new page, its own page numbers from 1."""
    title, reference = ATTACHED[t["attached"]]
    head = {**t, "noNumber": True, "noDate": True}
    sub = {**t, "typeName": title, "noSummary": False, "summaryFixed": "[Tên văn bản]", "subtitle": [[reference, True]]}
    grid = nd30_heading.header_grid(head, fields, d, text_mm)
    grid["new_section"] = True
    if t["attached"] == "qd":
        lines = skeleton({"group": t["group"], "id": "van-ban-kem-theo-qd-dien-tu"})
    else:
        lines = [x for x in skeleton({"group": t["group"], "id": "thong-tu"}) if not x.startswith(("Căn cứ", "Theo đề nghị", "@basis"))]
    return [grid] + nd30_heading.title_blocks(sub, fields, d, text_mm) + body_blocks(lines, d)


def _state_blocks(t, fields, d, text_mm):
    H = nd30_heading
    structure = t.get("structure")
    blocks = []
    if t.get("esign"):
        blocks.append(H.esign_line())
    if structure == "annex":
        return blocks + H.annex_title(t, d, text_mm) + _body(t, fields, d)
    if structure == "copy":
        return _body(t, fields, d) + nd30_forms.copy_blocks(t, fields, d, text_mm)
    if structure == "esign-copy":
        return [nd30_forms.copy_esign_line()] + _body(t, fields, d)
    if structure == "envelope":
        return nd30_forms.envelope_blocks(fields, d)
    if structure == "stamp":
        return nd30_forms.stamp_blocks(fields, d)
    if not t.get("noHeader"):
        blocks.append(H.header_grid(t, fields, d, text_mm))
    if not t.get("officialLetter") and not t.get("noTitle"):
        blocks += H.title_blocks(t, fields, d, text_mm)
    if t.get("kinhGui"):
        blocks += H.addressee_blocks(t, fields, d, text_mm)
    blocks += _body(t, fields, d)
    if structure in ("form", "attached-only"):
        return blocks
    blocks += nd30_signature.signature_blocks(t, fields, d)
    if t.get("attached"):
        blocks += _attached(t, fields, d, text_mm)
    return blocks


def _party_blocks(t, fields, d, text_mm):
    P = nd30_party
    if t["structure"] == "annex":
        return nd30_heading.annex_title(t, d, text_mm) + _body(t, fields, d)
    if t["structure"] == "dang-copy":
        return _body(t, fields, d) + P.copy_blocks(t, fields, d)
    blocks = [P.header_grid(t, fields, d, text_mm)]
    if not t.get("officialLetter"):
        blocks += P.title_blocks(t, fields, d)
    if t.get("kinhGui"):
        blocks += P.addressee_blocks(t, fields, d)
    return blocks + _body(t, fields, d) + P.signature_blocks(t, fields, d)


def build_layout(type_id, fields=None, margins_mm=None, data=None, template=False):
    """{'typeId', 'profile', 'textWidthMm', 'blocks', ...}; `template` keeps every optional placeholder for the .ott."""
    t = get_type(type_id, data)
    if t is None:
        raise ValueError("unknown-type")
    if t.get("module") == "sheets":
        raise ValueError("register-opens-as-sheet")
    d = profile_rules(t["profile"])
    fields = dict(fields or {})
    page = nd30_forms.ENVELOPE if t["structure"] == "envelope" else None
    m = margins_mm or page or d["defaultMarginsMm"]
    width = page["width"] if page else d["pageSizeMm"]["width"]
    text_mm = width - float(m["left"]) - float(m["right"])
    if template:
        fields = {"kinhGui": "[Cơ quan, tổ chức nhận văn bản 1]\n[Cơ quan, tổ chức nhận văn bản 2]"} if t.get("officialLetter") and t["profile"] == "nd30" else {}
        fields["_template"] = "1"
    build = _party_blocks if t["profile"] == "dang" else _state_blocks
    result = {"typeId": type_id, "profile": t["profile"], "textWidthMm": text_mm, "blocks": build(t, fields, d, text_mm)}
    if page:
        result["page"] = page
    if t["structure"] in ("copy", "dang-copy"):
        result["flow"] = "append"  # a copy block goes under the document being copied
    if t["structure"] == "esign-copy":
        result["flow"] = "prepend"
    return result


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
