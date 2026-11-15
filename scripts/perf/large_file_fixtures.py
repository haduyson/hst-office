# SPDX-License-Identifier: AGPL-3.0-only
"""Synthetic large documents for open-time measurements (scripts/perf/large-file-open.py).

    python large_file_fixtures.py <out-dir> [--rows N] [--pages N] [--slides N] [--pdf-pages N] [--only a,b] [--skip a,b]

Writes, all synthetic (random numbers, generated Vietnamese-like text, noise pictures):
- calc-values.xlsx      one big sheet of numbers, text and dates with a handful of cell styles (no formulas)
- calc-formulas.xlsx    the same rows plus formula columns with cached results (shared formulas, IF, VLOOKUP into a
                        lookup sheet, SUMIF over whole columns), written as by the common spreadsheet application
- calc-formulas-plain.xlsx  the same workbook with every formula written out per cell instead of shared formulas
- calc-formulas-other.xlsx  byte-identical sheets, but docProps/app.xml names another generator: the importer then
                        treats cached text results as untrusted (as for files exported by accounting software)
- calc-formulas-noresults.xlsx  the same formulas without any cached result, another generator: everything is
                        calculated while loading (the longest open; it used to abort the office after 10 minutes)
- calc-styles.xlsx      formula rows with ~4000 distinct cell formats scattered over the cells, conditional formatting
                        rules over whole columns and data validation lists (style-heavy workbooks)
- calc-sheets.xlsx      60 sheets of 4000 rows each, every sheet summing into a summary sheet (many-sheet workbooks)
- writer-text.docx / writer-images.docx / slides-images.pptx / pdf-mixed.pdf
- text-*.txt            plain text for Writer (large_file_fixtures_text.py)
Needs Pillow, python-docx and python-pptx for the document fixtures only. Sizes are printed; nothing here reads a
user file.
"""
import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from large_file_fixtures_text import TEXT_JOBS  # noqa: E402
from large_file_fixtures_xlsx import retarget_generator, write_xlsx, write_xlsx_sheets  # noqa: E402

EXCEL = "Microsoft Excel"  # docProps/app.xml generator the importer trusts (not shown to users)


def jobs(a):
    def docs(name, *args):
        def run(p):
            import large_file_fixtures_docs as d
            return getattr(d, name)(p, *args)
        return run
    out = {
        "calc-values.xlsx": lambda p: write_xlsx(p, a.rows, False, EXCEL),
        "calc-formulas.xlsx": lambda p: write_xlsx(p, a.rows, True, EXCEL),
        "calc-formulas-plain.xlsx": lambda p: write_xlsx(p, a.rows, True, EXCEL, shared=False),
        "calc-formulas-other.xlsx": lambda p: retarget_generator(os.path.join(a.out, "calc-formulas.xlsx"), p,
                                                                 "SyntheticExport"),
        "calc-formulas-noresults.xlsx": lambda p: write_xlsx(p, a.rows, True, "SyntheticExport", results=False),
        "calc-styles.xlsx": lambda p: write_xlsx(p, a.rows // 2, True, EXCEL, many_styles=True),
        "calc-sheets.xlsx": lambda p: write_xlsx_sheets(p, 60, 4000),
        "writer-text.docx": docs("write_docx", a.pages, False),
        "writer-images.docx": docs("write_docx", a.image_pages, True),
        "slides-images.pptx": docs("write_pptx", a.slides),
        "pdf-mixed.pdf": docs("write_pdf", a.pdf_pages),
    }
    out.update(TEXT_JOBS)
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("out")
    ap.add_argument("--rows", type=int, default=200000)
    ap.add_argument("--pages", type=int, default=1500)
    ap.add_argument("--image-pages", type=int, default=40)
    ap.add_argument("--slides", type=int, default=30)
    ap.add_argument("--pdf-pages", type=int, default=1500)
    ap.add_argument("--skip", default="", help="comma list of fixture names not to write")
    ap.add_argument("--only", default="", help="comma list of the fixture names to write (default: all)")
    a = ap.parse_args()
    os.makedirs(a.out, exist_ok=True)
    only = set(filter(None, a.only.split(",")))
    skip = set(filter(None, a.skip.split(",")))
    for name, job in jobs(a).items():
        if (only and name not in only) or name in skip:
            continue
        path = os.path.join(a.out, name)
        if name == "calc-formulas-other.xlsx" and not os.path.exists(os.path.join(a.out, "calc-formulas.xlsx")):
            write_xlsx(os.path.join(a.out, "calc-formulas.xlsx"), a.rows, True, EXCEL)
        job(path)
        print("%-30s %8.1f MB" % (name, os.path.getsize(path) / 1e6), flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
