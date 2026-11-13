#!/usr/bin/env python3
# SPDX-License-Identifier: AGPL-3.0-only
"""Print scaling of HST Sheets end to end through UNO (hst-sheets-print-scaling.patch), on Linux, Windows or macOS.

Usage: <python with uno> tests/runtime/check-sheets-print-scaling.py --soffice PATH/TO/soffice [--out DIR]

Starts a headless office with a fresh profile on a fixed port and checks: the page count of a wide sheet and of a tall
sheet exported to PDF after each scaling command; the print dialog list ("scalingbox" from getRenderer with
ExtraPrintUIOptions, the choice applied by getRendererCount, the custom entry restoring 75 %); undo; a sheet that
shares its page style gets its own; .xlsx (fitToPage, fitToWidth=1, fitToHeight=0) and .ods round trips.
Exit 1 when a check fails. Stops the office it started.
"""
import argparse
import os
import re
import sys
import tempfile
import zipfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from headless_office import Office, props  # noqa: E402

PORT = 22417
CHOICES = ("None", "FitSheet", "FitColumns", "FitRows")
SETTINGS = {"None": (100, 0, 0, 0), "FitSheet": (0, 0, 1, 1), "FitColumns": (0, 0, 1, 0), "FitRows": (0, 0, 0, 1)}
failures = []


def check(ok, text):
    print(("PASS  " if ok else "FAIL  ") + text, flush=True)
    if not ok:
        failures.append(text)


def new_sheet(office, columns, rows, sheets=1):
    doc = office.load("private:factory/scalc")
    while doc.Sheets.Count < sheets:
        doc.Sheets.insertNewByName("Sheet%d" % (doc.Sheets.Count + 1), doc.Sheets.Count)
    for index in range(sheets):
        sheet = doc.Sheets.getByIndex(index)
        sheet.getCellRangeByPosition(0, 0, columns - 1, rows - 1).setDataArray(
            tuple(tuple("R%dC%d" % (r, c) for c in range(columns)) for r in range(rows)))
        sheet.getCellRangeByPosition(0, 0, columns - 1, 0).Columns.Width = 2500
    return doc


def style_of(doc, index=0):
    return doc.StyleFamilies.getByName("PageStyles").getByName(doc.Sheets.getByIndex(index).PageStyle)


def settings(style):
    return (style.PageScale, style.ScaleToPages, style.ScaleToPagesX, style.ScaleToPagesY)


def pdf_pages(office, doc, path):
    doc.storeToURL(office.url(path), props(FilterName="calc_pdf_Export"))
    with open(path, "rb") as handle:
        return len(re.findall(rb"/Type\s*/Page[^s]", handle.read()))


def page_counts(office, out, name, columns, rows):
    doc = new_sheet(office, columns, rows)
    counts = {}
    for choice in CHOICES:
        office.dispatch(doc, ".uno:PrintScale" + choice)
        check(settings(style_of(doc)) == SETTINGS[choice], f"{name}: {choice} sets {SETTINGS[choice]}")
        counts[choice] = pdf_pages(office, doc, os.path.join(out, f"{name}-{choice}.pdf"))
    office.dispatch(doc, ".uno:PrintScaleNone")  # back from a fit choice: zoom 0 -> 100
    check(settings(style_of(doc)) == SETTINGS["None"], f"{name}: back to None")
    print(f"      {name} {columns}x{rows}: PDF pages {counts}", flush=True)
    doc.close(True)
    return counts


def ui_control(doc, controller):
    renderer = doc.getRenderer(0, doc, props(ExtraPrintUIOptions=None, View=controller, IsPrinter=True))
    for prop in renderer:
        if prop.Name == "ExtraPrintUIOptions":
            for control in prop.Value:
                entries = {p.Name: p.Value for p in control}
                if "scalingbox" in tuple(entries.get("ID", ())):
                    return entries["Choices"], entries["Property"].Value
    return None, None


def print_dialog_path(office):
    doc = new_sheet(office, 40, 50)
    controller = doc.getCurrentController()
    choices, initial = ui_control(doc, controller)
    check(choices is not None and len(choices) == 4 and initial == 0, f"dialog list: {choices} initial {initial}")
    count = doc.getRendererCount(doc, props(View=controller, PrintContent=1, PrintScaling=0))
    check(settings(style_of(doc)) == SETTINGS["None"], f"opening the dialog changes nothing ({count} pages)")
    count = doc.getRendererCount(doc, props(View=controller, PrintContent=1, PrintScaling=2))
    check(settings(style_of(doc)) == SETTINGS["FitColumns"] and count == 1, f"dialog Fit All Columns: {count} page")
    office.dispatch(doc, ".uno:Undo")
    check(settings(style_of(doc)) == SETTINGS["None"], "undo restores actual size")
    office.dispatch(doc, ".uno:Redo")
    check(settings(style_of(doc)) == SETTINGS["FitColumns"], "redo applies Fit All Columns again")
    office.dispatch(doc, ".uno:Undo")
    style_of(doc).PageScale = 75
    choices, initial = ui_control(doc, controller)
    check(choices is not None and len(choices) == 5 and initial == 4 and "75" in choices[4], f"custom entry {choices}")
    doc.getRendererCount(doc, props(View=controller, PrintContent=1, PrintScaling=1))
    fit = settings(style_of(doc))
    doc.getRendererCount(doc, props(View=controller, PrintContent=1, PrintScaling=4))
    check(fit == SETTINGS["FitSheet"] and style_of(doc).PageScale == 75, "custom entry restores 75 %")
    doc.close(True)


def shared_style(office):
    doc = new_sheet(office, 40, 50, sheets=2)
    doc.getCurrentController().setActiveSheet(doc.Sheets.getByIndex(0))
    office.dispatch(doc, ".uno:PrintScaleFitColumns")
    names = (doc.Sheets.getByIndex(0).PageStyle, doc.Sheets.getByIndex(1).PageStyle)
    check(names[0] == "PageStyle_Sheet1" and names[1] == "Default" and settings(style_of(doc, 1)) == SETTINGS["None"],
          f"shared style split per sheet: {names}")
    office.dispatch(doc, ".uno:Undo")
    check(doc.Sheets.getByIndex(0).PageStyle == "Default"
          and not doc.StyleFamilies.getByName("PageStyles").hasByName("PageStyle_Sheet1"), "undo removes the copy")
    doc.close(True)


def round_trips(office, out):
    for filter_name, ext in (("Calc Office Open XML", "xlsx"), ("calc8", "ods")):
        doc = new_sheet(office, 40, 50)
        office.dispatch(doc, ".uno:PrintScaleFitColumns")
        path = os.path.join(out, "fit-columns." + ext)
        doc.storeToURL(office.url(path), props(FilterName=filter_name))
        doc.close(True)
        doc = office.load(office.url(path))
        check(settings(style_of(doc)) == SETTINGS["FitColumns"], f".{ext} keeps Fit All Columns {settings(style_of(doc))}")
        doc.close(True)
        if ext == "xlsx":
            with zipfile.ZipFile(path) as package:
                xml = package.read("xl/worksheets/sheet1.xml").decode("utf-8")
            check(re.search(r'fitToPage="(true|1)"', xml) and 'fitToWidth="1"' in xml and 'fitToHeight="0"' in xml,
                  ".xlsx pageSetup fitToWidth=1 fitToHeight=0 with fitToPage")


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--soffice", required=True)
    parser.add_argument("--out", default=tempfile.mkdtemp(prefix="hst-print-scaling-"))
    args = parser.parse_args()
    os.makedirs(args.out, exist_ok=True)
    office = Office(args.soffice, args.out, PORT)
    try:
        wide = page_counts(office, args.out, "wide", 40, 50)
        check(wide["None"] > 1 and wide["FitSheet"] == 1 and wide["FitColumns"] == 1 and wide["FitRows"] == wide["None"],
              "wide sheet: only fitting the columns or the sheet makes one page")
        tall = page_counts(office, args.out, "tall", 5, 400)
        check(tall["None"] > 1 and tall["FitSheet"] == 1 and tall["FitRows"] == 1 and tall["FitColumns"] == tall["None"],
              "tall sheet: only fitting the rows or the sheet makes one page")
        both = page_counts(office, args.out, "wide-and-tall", 40, 400)
        check(1 < both["FitColumns"] < both["None"], "wide and tall sheet: all columns on one page width, rows go on")
        print_dialog_path(office)
        shared_style(office)
        round_trips(office, args.out)
    finally:
        office.stop()
    print(f"{len(failures)} failure(s); output in {args.out}")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
