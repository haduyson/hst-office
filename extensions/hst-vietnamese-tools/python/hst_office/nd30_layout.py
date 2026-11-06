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


def _shift(block, key, pt):
    return {**block, key: block.get(key, 0) + pt}


def _cells_edge(grid, pt, first):
    """Add `pt` before the first (or after the last) paragraph of every cell of the first (or last) row."""
    rows = [dict(r) for r in grid["rows"]]
    index, key = (0, "spacing_before_pt") if first else (-1, "spacing_after_pt")
    cells = []
    for cell in rows[index]["cells"]:
        if not cell:
            cells.append(cell)
            continue
        cell = list(cell)
        cell[0 if first else -1] = _shift(cell[0 if first else -1], key, pt)
        cells.append(cell)
    rows[index] = {**rows[index], "cells": cells}
    return {**grid, "rows": rows}


def portable_blocks(layout):
    """The blocks as both renderers write them, so a DOCX or DOC copy lays out like the original:

    - a table carries no space above or below (Word has no such property, the space was lost on export): the space goes to
      the paragraph next to it, or into the first/last paragraph of the cells of a borderless table;
    - a page break that starts an attached document sits on a 1 pt paragraph, not on a table (the DOC filter drops a
      page break carried by a table);
    - a closing table keeps with the empty paragraph Writer adds after it (no blank last page);
    Returns (blocks, first_page_footer_blocks); no type has a first-page footer yet."""
    footer = []
    blocks = []
    for b in layout["blocks"]:
        if b["type"] == "grid" and b.get("new_section"):
            blocks.append({"type": "paragraph", "align": "left", "runs": [{"text": "", "size": 1, "bold": False, "italic": False}],
                           "role": "SectionStart", "line_spacing": 1.0, "new_section": True})
            b = {k: v for k, v in b.items() if k != "new_section"}
        blocks.append(b)
    out = []
    for i, b in enumerate(blocks):
        if b["type"] != "grid":
            out.append(b)
            continue
        before, after = b.get("spacing_before_pt", 0), b.get("spacing_after_pt", 0)
        b = {k: v for k, v in b.items() if k not in ("spacing_before_pt", "spacing_after_pt")}
        if before:
            if out and out[-1]["type"] == "paragraph" and b.get("borders"):
                out[-1] = _shift(out[-1], "spacing_after_pt", before)
            else:
                b = _cells_edge(b, before, True)
        if after:
            nxt = blocks[i + 1] if i + 1 < len(blocks) else None
            if nxt is not None and nxt["type"] == "paragraph":
                blocks[i + 1] = _shift(nxt, "spacing_before_pt", after)
            elif not b.get("borders"):
                b = _cells_edge(b, after, False)
        out.append(b)
    if out and out[-1]["type"] == "grid" and out[-1].get("name") == "Signature":
        # Writer keeps an empty paragraph after a closing table: the signature block (never split) goes with it, so it
        # cannot leave that paragraph alone on a blank page. Not for a register table: the DOCX filter writes a table's
        # keep-with-next on every row, which glues a long register into one block that can no longer split.
        out[-1] = {**out[-1], "keep_with_next": True}
    # Word has no table property for it: it keeps a table with the next paragraph when its last row keeps with next
    return [_keep_last_row(b) if b["type"] == "grid" and b.get("keep_with_next") else b for b in out], footer


def _keep_last_row(grid):
    rows = list(grid["rows"])
    rows[-1] = {**rows[-1], "cells": [[{**p, "keep_with_next": True} for p in cell] for cell in rows[-1]["cells"]]}
    return {**grid, "rows": rows}
    return out, footer


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
