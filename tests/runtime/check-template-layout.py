#!/usr/bin/env python3
# SPDX-License-Identifier: AGPL-3.0-only
"""Measure every Writer document type on multi-page content, from the .ott templates and from the wizard's renderer.

Usage (as root it runs the office as the build user; hold the shared build lock around it):
    python3 tests/runtime/check-template-layout.py --templates dist/templates [--instdir upstream/libreoffice/instdir]
        [--out tests/output/template-layout] [--port 2191] [--only cong-van,bien-ban] [--shots DIR]

For each type: the .ott with filler paragraphs, and the renderer with long names, several recipients and a two-line
signature, then a short variant. Each goes to PDF, DOCX and DOCX reopened to PDF. Body top, left, right, bottom, page
number (hidden on page 1, centred in the top margin), number/date baseline and rule lengths are read from the PDF.
Exit 1 on any failure; Times New Roman is reported when missing, because line breaks then come from its stand-in.
"""
import argparse
import json
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path[:0] = [HERE, os.path.join(os.path.dirname(os.path.dirname(HERE)), "extensions/hst-vietnamese-tools/python")]
import hst_gui  # noqa: E402
import template_layout_cases as cases  # noqa: E402
import template_layout_measure as measure  # noqa: E402
TOL = 0.15


def _expected_numbers(pages, numbers):
    """{page: number}: from 2 up; an attached document restarts at an unnumbered first page of its own."""
    expected, restart = {}, None
    for page in range(2, pages + 1):
        if page not in numbers and restart is None:
            restart = page
            continue
        expected[page] = str(page if restart is None else page - restart + 1)
    return expected


def checks(name, pdf, case, fails):
    profile, multipage = case["profile"], case["multipage"]
    m = measure.measure(pdf)
    if not case["paged"]:
        return m
    top_low, top_high = profile["bodyTopMm"]
    margins = profile["defaultMarginsMm"]
    page_width = profile["pageSizeMm"]["width"]
    tops = [t for t in m["bodyTop"] if t is not None]
    if any(t < top_low - TOL or t > top_high for t in tops):
        fails.append(f"{name}: body top {tops}")
    if m["left"] < margins["left"] - TOL or m["right"] > page_width - margins["right"] + TOL:
        fails.append(f"{name}: left/right {m['left']}/{m['right']}")
    if m["bottom"] > profile["pageSizeMm"]["height"] - margins["bottom"] + TOL:
        fails.append(f"{name}: bottom {m['bottom']}")
    if multipage and m["pages"] < 2:
        fails.append(f"{name}: expected several pages, got {m['pages']}")
    numbers = {page: (text, x, y) for page, text, x, y in m["pageNumbers"]}
    centre = margins["left"] + (page_width - margins["left"] - margins["right"]) / 2
    if 1 in numbers:
        fails.append(f"{name}: page number shown on page 1")
    restarts = case["type"].get("attached")
    expected = _expected_numbers(m["pages"], numbers) if restarts else {p: str(p) for p in range(2, m["pages"] + 1)}
    for page, value in expected.items():
        if page not in numbers or numbers[page][0] != value:
            fails.append(f"{name}: page {page} number, wanted {value}: {numbers.get(page)}")
        elif abs(numbers[page][1] - centre) > 1.0 or numbers[page][2] > margins["top"] + TOL:
            fails.append(f"{name}: page {page} number misplaced: {numbers[page]}")
    return m


def run_case(office, case, out, fails, rows):
    from com.sun.star.beans import PropertyValue

    def prop(name, value):
        p = PropertyValue()
        p.Name, p.Value = name, value
        return p
    desktop = office.service("com.sun.star.frame.Desktop")
    name = case["name"]
    doc = case["open"](desktop, prop)
    base = os.path.join(out, name)
    pdf, docx, again = base + ".pdf", base + ".docx", base + ".docx.pdf"
    try:
        doc.storeToURL("file://" + pdf, (prop("FilterName", "writer_pdf_Export"),))
        doc.storeToURL("file://" + docx, (prop("FilterName", "MS Word 2007 XML"),))
    finally:
        doc.close(True)
    reopened = desktop.loadComponentFromURL("file://" + docx, "_blank", 0, (prop("Hidden", True),))
    try:
        reopened.storeToURL("file://" + again, (prop("FilterName", "writer_pdf_Export"),))
    finally:
        reopened.close(True)
    row = {"case": name}
    for label, path in (("pdf", pdf), ("docx", again)):
        row[label] = checks(f"{name} {label}", path, case, fails)
    if case["checkNumberRow"]:
        for label, path in (("pdf", pdf), ("docx", again)):
            offset = measure.number_date_offset(path)
            row[label + "NumberDate"] = offset
            if offset is not None and offset > 0.3:
                fails.append(f"{name} {label}: number and date baselines differ by {offset} mm")
    for failure in cases.check_rules(case, pdf):
        fails.append(f"{name}: {failure}")
    rows.append(row)


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--templates", required=True)
    parser.add_argument("--instdir", default=os.path.join(hst_gui.ROOT, "upstream/libreoffice/instdir"))
    parser.add_argument("--out", default=os.path.join(hst_gui.ROOT, "tests/output/template-layout"))
    parser.add_argument("--port", type=int, default=2191)
    parser.add_argument("--only", default="")
    args = parser.parse_args()
    out = os.path.abspath(args.out)
    os.makedirs(out, exist_ok=True)
    os.environ.setdefault("HST_VCLPLUGIN", "svp")  # headless: no X display needed
    hst_gui.setup_uno(args.instdir)
    fonts = subprocess.run(["fc-match", "Times New Roman"], capture_output=True, text=True).stdout.strip()
    print("Times New Roman resolves to:", fonts, flush=True)
    only = set(filter(None, args.only.split(",")))
    office = hst_gui.Office(args.instdir, os.path.join(out, "office"), args.port, extra_args=["--headless"], display=os.environ.get("DISPLAY", ":97")).start()
    fails, rows = [], []
    try:
        for case in cases.all_cases(os.path.abspath(args.templates), only):
            try:
                run_case(office, case, out, fails, rows)
            except Exception as error:  # noqa: BLE001 - one broken case must not hide the others
                fails.append(f"{case['name']}: {error!r}")
    finally:
        office.stop()
    with open(os.path.join(out, "measurements.json"), "w", encoding="utf-8") as handle:
        json.dump({"font": fonts, "rows": rows, "failures": fails}, handle, ensure_ascii=False, indent=1)
    for row in rows:
        print(row["case"], "| PDF top", row["pdf"]["bodyTop"][:3], "L", row["pdf"]["left"], "R", row["pdf"]["right"], "B", row["pdf"]["bottom"],
              "| DOCX top", row["docx"]["bodyTop"][:3], "pages", row["pdf"]["pages"], "/", row["docx"]["pages"], "| S/N", row.get("pdfNumberDate"), row.get("docxNumberDate"))
    print("\n".join("FAIL " + f for f in fails) or "PASS", flush=True)
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
