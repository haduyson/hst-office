# SPDX-License-Identifier: AGPL-3.0-only
"""RIS import ("TY  - JOUR" … "ER  - "), as exported by Scopus, Web of Science, Google Scholar, Zotero, Mendeley,
EndNote, doi.org and VJOL. Unknown tags are kept in the note with a warning; continuation lines are joined.
Returns citation_import_common.ImportResult. Pure Python (no uno)."""
import re

from .citation_import_common import ImportResult, ItemBuilder
from .citation_ris_map import DATE_TAGS, NAME_TAGS, TEXT_TAGS, TYPE_TO_CSL

_LINE = re.compile(r"^([A-Z][A-Z0-9])\s{1,2}-(?:\s(.*))?$")
_SERIES_TYPES = ("book", "thesis", "report")  # their T2 is a series, not a container
_MULTI = {"keyword": "; ", "abstract": " ", "note": "\n"}


def _record_start(value, line, result):
    kind = TYPE_TO_CSL.get(value.strip().upper())
    if kind is None:
        result.warnings.append("Dòng %d: kiểu RIS “%s” không hỗ trợ, nhập như “Tài liệu khác”" % (line, value.strip()))
        kind = "document"
    return ItemBuilder(kind, line), {"pages": ["", ""], "last": None}


def _apply(builder, state, tag, value):
    kind = builder.raw["type"]
    if tag in NAME_TAGS:
        builder.add_name(NAME_TAGS[tag], value)
    elif tag in DATE_TAGS:
        builder.set_date("issued", value)
    elif tag == "Y2":
        builder.set_date("accessed", value)
    elif tag == "SP":
        state["pages"][0] = value
    elif tag == "EP":
        state["pages"][1] = value
    elif tag == "SN":
        builder.set_identifier(value)
    elif tag == "N1":
        builder.add_note(value)
    elif tag == "BT" and kind in ("chapter", "paper-conference"):
        builder.set("container-title", value)
    elif tag == "T2" and kind in _SERIES_TYPES:
        builder.set("collection-title", value)
    elif tag in TEXT_TAGS:
        var = TEXT_TAGS[tag]
        if var in _MULTI and builder.raw.get(var):
            builder.raw[var] += _MULTI[var] + value.strip()
        elif var:
            builder.set(var, value)
    else:
        builder.add_note("%s: %s" % (tag, value.strip()))
        builder.mark_unknown(tag)
        return
    state["last"] = tag


_CONTINUED = ("AB", "N2", "N1", "TI", "T1", "T2")


def _continue(builder, tag, text):
    """A line without a tag continues the previous field (long abstracts, titles wrapped by some exporters)."""
    if tag == "N1" and builder.notes:
        builder.notes[-1] += " " + text
    elif TEXT_TAGS.get(tag) and builder.raw.get(TEXT_TAGS[tag]):
        builder.raw[TEXT_TAGS[tag]] += " " + text


def parse(text):
    """ImportResult of RIS text (already decoded by citation_text_io)."""
    result = ImportResult(fmt="ris")
    builder, state = None, None

    def close():
        item, warnings = builder.finish()
        result.items.append(item)
        result.warnings.extend(warnings)

    for number, raw in enumerate(text.split("\n"), 1):
        line = raw.rstrip()
        match = _LINE.match(line)
        if not match:
            if line.strip() and builder is not None and state["last"] in ("AB", "N2", "N1", "TI", "T1"):
                tag = state["last"]
                _apply(builder, state, tag, line.strip()) if tag in ("N1",) else \
                    builder.raw.__setitem__(TEXT_TAGS[tag], builder.raw.get(TEXT_TAGS[tag], "") + " " + line.strip())
            elif line.strip() and builder is None and line.strip() not in ("﻿",):
                result.warnings.append("Dòng %d: bỏ qua dòng ngoài bản ghi RIS" % number)
            continue
        tag, value = match.group(1), (match.group(2) or "").strip()
        if tag == "TY":
            if builder is not None:
                result.warnings.append("Dòng %d: bản ghi trước thiếu “ER”, đã đóng lại" % number)
                builder.set_pages(*state["pages"])
                close()
            builder, state = _record_start(value, number, result)
        elif tag == "ER":
            if builder is None:
                continue
            builder.set_pages(*state["pages"])
            close()
            builder = None
        elif builder is None:
            result.warnings.append("Dòng %d: thẻ %s nằm ngoài bản ghi (thiếu “TY”)" % (number, tag))
        else:
            _apply(builder, state, tag, value)
    if builder is not None:
        result.warnings.append("Bản ghi cuối thiếu “ER”, đã nhập phần đã đọc")
        builder.set_pages(*state["pages"])
        close()
    if not result.items:
        result.warnings.append("Không tìm thấy bản ghi RIS nào (mỗi bản ghi bắt đầu bằng “TY  - ”)")
    return result
