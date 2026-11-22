#!/usr/bin/env python3
# SPDX-License-Identifier: LicenseRef-HST-Proprietary
# Copyright (C) 2026 HASON TECH
"""Insert/delete row speed of HST Sheets on a ledger whose rows look up whole columns (Linux, Windows, macOS).

Usage: <python with uno> tests/runtime/check-sheets-insert-row-speed.py --soffice PATH/TO/soffice [--out DIR]
       [--rows 20000] [--limit 1.5]

Builds a ledger like many Vietnamese office workbooks (every row: VLOOKUP into a catalogue sheet by whole columns,
SUMIF and COUNTIF over whole columns), saves it as .xlsx and opens it again, so that the formulas are grouped and
listen as groups exactly like a user's file. Then inserts and deletes a row near the top several times through the
sheet API (the same ScDocFunc path as the menu) and checks:
- the slowest insert and the slowest delete stay under --limit seconds (1.0.2 took 2-7 s per operation here);
- whole-column lookups cost at most 3x the same lookups into a bounded range (the slot search of
  hst-calc-shift-rows-end-listening.patch made them about 10x slower);
- the results still follow a change of the catalogue afterwards.
Exit 1 when a check fails. Stops the office it started.
"""
import argparse
import os
import sys
import tempfile
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from headless_office import Office, props  # noqa: E402

PORT = 22431
CATALOGUE = 400
failures = []


def check(ok, text):
    print(("PASS  " if ok else "FAIL  ") + text, flush=True)
    if not ok:
        failures.append(text)


def build(office, path, rows, whole):
    """Ledger + catalogue, saved as .xlsx. `whole`: lookups by whole columns, else by the bounded catalogue."""
    doc = office.load("private:factory/scalc")
    doc.Sheets.insertNewByName("DanhMuc", 1)
    cat = doc.Sheets.getByName("DanhMuc")
    cat.getCellRangeByPosition(0, 0, 1, CATALOGUE - 1).setDataArray(
        tuple(("MH%04d" % i, float(1000 * (i % 97 + 1))) for i in range(CATALOGUE)))
    sheet = doc.Sheets.getByIndex(0)
    sheet.getCellRangeByPosition(0, 0, 1, rows - 1).setDataArray(
        tuple(("MH%04d" % (r * 7 % CATALOGUE), float(r % 50 + 1)) for r in range(rows)))
    ref = "$DanhMuc.$A:$B" if whole else "$DanhMuc.$A$1:$B$%d" % CATALOGUE
    keys = "$A:$A" if whole else "$A$1:$A$%d" % rows
    qty = "$B:$B" if whole else "$B$1:$B$%d" % rows
    sheet.getCellRangeByPosition(2, 0, 4, rows - 1).setFormulaArray(tuple(
        ("=VLOOKUP(A%d;%s;2;0)*B%d" % (r, ref, r), "=SUMIF(%s;A%d;%s)" % (keys, r, qty), "=COUNTIF(%s;A%d)" % (keys, r))
        for r in range(1, rows + 1)))
    doc.storeToURL(office.url(path), props(FilterName="Calc Office Open XML"))
    doc.close(True)


def shift_times(office, path, repeat=3):
    doc = office.load(office.url(path))
    try:
        sheet = doc.Sheets.getByIndex(0)
        inserts, deletes = [], []
        for _ in range(repeat):
            start = time.perf_counter()
            sheet.Rows.insertByIndex(10, 1)
            inserts.append(time.perf_counter() - start)
            start = time.perf_counter()
            sheet.Rows.removeByIndex(10, 1)
            deletes.append(time.perf_counter() - start)
        cat = doc.Sheets.getByName("DanhMuc")
        key = sheet.getCellByPosition(0, 100).getString()
        index = int(key[2:])
        cat.getCellByPosition(1, index).setValue(123456.0)
        qty = sheet.getCellByPosition(1, 100).getValue()
        follows = abs(sheet.getCellByPosition(2, 100).getValue() - 123456.0 * qty) < 1e-6
        return inserts, deletes, follows
    finally:
        doc.close(True)


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--soffice", required=True)
    parser.add_argument("--out", default=tempfile.mkdtemp(prefix="hst-insert-row-speed-"))
    parser.add_argument("--rows", type=int, default=20000)
    parser.add_argument("--limit", type=float, default=1.5, help="seconds allowed for one insert or delete")
    args = parser.parse_args()
    os.makedirs(args.out, exist_ok=True)
    office = Office(args.soffice, args.out, PORT)
    try:
        whole_path = os.path.join(args.out, "ledger-whole-columns.xlsx")
        bounded_path = os.path.join(args.out, "ledger-bounded.xlsx")
        build(office, whole_path, args.rows, True)
        build(office, bounded_path, args.rows, False)
        ins_w, del_w, follows_w = shift_times(office, whole_path)
        ins_b, del_b, follows_b = shift_times(office, bounded_path)
        print("whole columns: insert %s delete %s" % ([round(t, 2) for t in ins_w], [round(t, 2) for t in del_w]))
        print("bounded range: insert %s delete %s" % ([round(t, 2) for t in ins_b], [round(t, 2) for t in del_b]))
        check(max(ins_w) < args.limit and max(del_w) < args.limit,
              "insert/delete a row above %d whole-column lookups under %.1f s" % (args.rows, args.limit))
        check(min(ins_w) + min(del_w) < 3 * (min(ins_b) + min(del_b)) + 0.2,
              "whole-column lookups shift no slower than 3x bounded ones")
        check(follows_w and follows_b, "lookups follow a catalogue change after the row shifts")
    finally:
        office.stop()
    print(f"{len(failures)} failure(s); output in {args.out}")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
