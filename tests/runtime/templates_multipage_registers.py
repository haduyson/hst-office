# SPDX-License-Identifier: AGPL-3.0-only
"""Registers (Decree 30, Annex IV) run to several pages: 120 entries typed downward as a clerk does must all print, with
the header rows on every page, from the template and from its XLSX copy."""
import os
import re

import templates_multipage_fill as F
import templates_multipage_measure as M


def register_case(desktop, rules, entry, out):
    base = os.path.join(out, "registers", entry["id"])
    os.makedirs(base, exist_ok=True)
    doc = desktop.loadComponentFromURL(F.url(os.path.join(out, "templates", entry["output"])), "_blank", 0, F.props(Hidden=True, AsTemplate=True))
    count = rules["registerRows"]
    try:
        sheet = doc.Sheets.getByName("Sổ")
        cols = len([c for c in range(30) if sheet.getCellByPosition(c, 0).getString()])
        data = tuple(tuple("Mục %d dòng %d" % (c + 1, r + 1) for c in range(cols)) for r in range(count))
        sheet.getCellRangeByPosition(0, 2, cols - 1, count + 1).setDataArray(data)
        heading = sheet.getCellByPosition(0, 1).getString()
        doc.storeToURL(F.url(os.path.join(base, "doc.pdf")), F.props(FilterName="calc_pdf_Export"))
        doc.storeToURL(F.url(os.path.join(base, "doc.xlsx")), F.props(FilterName="Calc MS Excel 2007 XML", Overwrite=True))
    finally:
        doc.close(True)
    copy = desktop.loadComponentFromURL(F.url(os.path.join(base, "doc.xlsx")), "_blank", 0, F.props(Hidden=True))
    try:
        copy.storeToURL(F.url(os.path.join(base, "xlsx.pdf")), F.props(FilterName="calc_pdf_Export"))
    finally:
        copy.close(True)
    problems = []
    for name in ("doc.pdf", "xlsx.pdf"):
        pages = M.pdf_lines(os.path.join(base, name))
        text = ["\n".join(ln["text"] for ln in p) for p in pages]
        printed = {int(x) for t in text for x in re.findall(r"dòng\s+(\d+)", t)}
        if len(printed) != count:
            problems.append("%s: %d of %d entries printed" % (name, len(printed), count))
        for k, t in enumerate(text, 1):
            if "dòng" in t and heading not in t:
                problems.append("%s: p%d has entries without the header rows" % (name, k))
    return {"problems": problems}
