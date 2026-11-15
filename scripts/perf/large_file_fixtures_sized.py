# SPDX-License-Identifier: AGPL-3.0-only
"""Office fixtures at target file sizes (5/10/20/30/50 MB by default) for scripts/perf/large-file-open.py.

    python large_file_fixtures_sized.py <out-dir> [--sizes 50,30,20,10,5] [--only docx-images,xlsx-pivot,...]

Writes <kind>-<size>mb.<ext> for every kind below. The content of each kind scales with one number (pictures, sections,
rows, sheets, slides, clips); it is fitted to the target size from two small samples and corrected once, so files land
within about 10 % of the target. Kinds are the common real-world reasons a document is big:
- docx-images / docx-text / docx-review / docx-styles   (large_file_fixtures_docx.py)
- xlsx-formulas (SUMIF/VLOOKUP/COUNTIF columns with cached results), xlsx-formats (thousands of cell formats,
  conditional formatting), xlsx-pivot (two pivot tables over the data), xlsx-sheets (many monthly sheets and a summary),
  xlsx-images (a data sheet with a photo catalogue)
- pptx-images / pptx-media / pptx-shapes   (large_file_fixtures_pptx.py)
Binary .ppt copies are converted from the pptx kinds separately (docs/PERFORMANCE_LARGE_FILES.md). Needs Pillow,
python-pptx and ffmpeg; every picture, clip and text is generated.
"""
import argparse
import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from large_file_fixtures_xlsx import write_xlsx, write_xlsx_sheets  # noqa: E402

EXCEL = "Microsoft Excel"


def docx(kind):
    def build(path, units):
        from large_file_fixtures_docx import write_docx_kind
        write_docx_kind(path, kind, units)
    return build


def pptx(kind):
    def build(path, units):
        from large_file_fixtures_pptx import write_pptx_kind
        write_pptx_kind(path, kind, units)
    return build


def xlsx_with(add, rows):
    def build(path, units):
        import large_file_fixtures_xlsx_extra as extra
        fd, base = tempfile.mkstemp(suffix=".xlsx", dir=os.path.dirname(path))
        os.close(fd)
        try:
            if add == "pivot":
                write_xlsx(base, units, True, EXCEL)
                extra.add_pivots(base, path, units)
            else:
                write_xlsx(base, rows, True, EXCEL)
                extra.add_pictures(base, path, units)
        finally:
            os.remove(base)
    return build


# kind: (extension, builder(path, units), two small calibration sizes in units)
KINDS = {
    "docx-images": ("docx", docx("images"), (3, 6)),
    "docx-text": ("docx", docx("text"), (400, 800)),
    "docx-review": ("docx", docx("review"), (400, 800)),
    "docx-styles": ("docx", docx("styles"), (400, 800)),
    "xlsx-formulas": ("xlsx", lambda p, u: write_xlsx(p, u, True, EXCEL, countif=True), (5000, 10000)),
    "xlsx-formats": ("xlsx", lambda p, u: write_xlsx(p, u, True, EXCEL, many_styles=True), (5000, 10000)),
    "xlsx-pivot": ("xlsx", xlsx_with("pivot", 0), (5000, 10000)),
    "xlsx-sheets": ("xlsx", lambda p, u: write_xlsx_sheets(p, u, 4000), (4, 8)),
    "xlsx-images": ("xlsx", xlsx_with("images", 20000), (2, 4)),
    "pptx-images": ("pptx", pptx("images"), (2, 4)),
    "pptx-media": ("pptx", pptx("media"), (1, 2)),
    "pptx-shapes": ("pptx", pptx("shapes"), (5, 10)),
}


def sized(path, build, calib, target):
    """Fit size = a + b * units from two samples, build at the fitted units, correct once (secant) if >10 % off."""
    pts = []
    for u in calib:
        build(path, u)
        pts.append((u, os.path.getsize(path)))
    (u1, s1), (u2, s2) = pts
    b = max((s2 - s1) / (u2 - u1), 1.0)
    units = max(1, round(u2 + (target - s2) / b))
    build(path, units)
    size = os.path.getsize(path)
    if abs(size - target) > 0.1 * target:
        b = max((size - s2) / max(units - u2, 1), 1.0)
        units = max(1, round(units + (target - size) / b))
        build(path, units)
        size = os.path.getsize(path)
    return units, size


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("out")
    ap.add_argument("--sizes", default="50,30,20,10,5")
    ap.add_argument("--only", default="", help="comma list of kinds (default: all)")
    a = ap.parse_args()
    os.makedirs(a.out, exist_ok=True)
    only = set(filter(None, a.only.split(",")))
    for kind, (ext, build, calib) in KINDS.items():
        if only and kind not in only:
            continue
        for mb in (int(x) for x in a.sizes.split(",")):
            path = os.path.join(a.out, "%s-%dmb.%s" % (kind, mb, ext))
            if os.path.exists(path):
                continue
            units, size = sized(path + ".tmp", build, calib, mb * 1_000_000)
            os.replace(path + ".tmp", path)
            print("%-26s %7.1f MB  units=%d" % (os.path.basename(path), size / 1e6, units), flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
