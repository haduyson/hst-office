# SPDX-License-Identifier: LicenseRef-HST-Proprietary
"""The core's blocks → what Writer inserts (no UNO here).

A paragraph block becomes one paragraph; a formula becomes its own paragraph "$$…$$", which HST's
"Chuyển TeX ⇄ công thức" (org.hst.office.vi:TexToggle) then turns into a centred Công thức; a table becomes a
Writer table. Blocks of an unknown type, empty text and malformed fields are dropped, never inserted half-way.
"""
from collections import namedtuple

Item = namedtuple("Item", "kind value")  # kind: "text" (str) | "table" (list of rows of str)


def _clean(text):
    # Control characters other than tab would break the paragraph structure in Writer.
    return "".join(ch for ch in text if ch == "\t" or ch >= " ").strip()


def to_items(blocks):
    items = []
    for block in blocks:
        if not isinstance(block, dict):
            continue
        kind = block.get("type")
        if kind == "paragraph" and isinstance(block.get("text"), str):
            text = _clean(block["text"])
            if text:
                items.append(Item("text", text))
        elif kind == "formula" and isinstance(block.get("latex"), str):
            latex = _clean(block["latex"]).replace("$", r"\$")
            if latex:
                items.append(Item("text", "$$%s$$" % latex))
        elif kind == "table" and _is_grid(block.get("rows")):
            rows = [[_clean(c) for c in row] for row in block["rows"]]
            width = max(len(r) for r in rows)
            items.append(Item("table", [r + [""] * (width - len(r)) for r in rows]))
    return items


def _is_grid(rows):
    return (isinstance(rows, list) and rows and all(isinstance(r, list) and r for r in rows)
            and all(isinstance(c, str) for r in rows for c in r))


def has_formula(items):
    return any(i.kind == "text" and i.value.startswith("$$") for i in items)
