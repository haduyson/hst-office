# SPDX-License-Identifier: AGPL-3.0-only
"""Check that the Writer style gallery on the Tabbed ribbon shows whole rows only.

Usage: python3 tests/runtime/check-style-gallery.py [--instdir upstream/libreoffice/instdir]
           [--out tests/output/style-gallery] [--shots tests/output/screenshots-tabs] [--display :97]
           [--image SCREENSHOT.png]   (analyse an existing screenshot instead of starting soffice)

Opens a Writer document with the default Tabbed UI, takes a screenshot and finds the gallery
frame in the ribbon (the widest box with a 1px border whose top and bottom edges have the same
horizontal extent). Asserts:
  - the frame fits in the ribbon height (40..70 px);
  - no preview is cut by the bottom edge: the band just above the bottom border has no text
    ink (a clipped second row leaves glyph pixels there);
  - several previews are shown (ink in at least 3 separate columns of items).
Exit 1 when a check fails.
"""
import argparse
import json
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import hst_gui  # noqa: E402

ROOT = hst_gui.ROOT
PORT = 21992


def luminance(pixel):
    r, g, b = pixel[:3]
    return (299 * r + 587 * g + 114 * b) // 1000


def horizontal_runs(img, y, x0, x1, min_len):
    """Runs of one identical, non-white colour on row y (candidate frame edges)."""
    runs, start = [], None
    px = img.load()
    for x in range(x0, x1 + 1):
        same = x < x1 and start is not None and px[x, y] == px[start, y]
        if start is not None and not same:
            if x - start >= min_len and 100 <= luminance(px[start, y]) < 235:
                runs.append((start, x - 1, px[start, y]))
            start = None
        if start is None and x < x1:
            start = x
    return runs


def light_inside(px, left, top, right, bottom):
    """The gallery is a list: a mostly white/light inside (not the grey ribbon chrome)."""
    samples = [px[x, y] for y in range(top + 2, bottom - 1, 3) for x in range(left + 2, right - 1, 7)]
    return bool(samples) and sum(luminance(p) > 240 for p in samples) > 0.6 * len(samples)


def find_gallery(img, region):
    """Return (left, top, right, bottom) of the gallery frame inside region, or None."""
    x0, y0, x1, y1 = region
    edges = {}
    for y in range(y0, y1):
        for run in horizontal_runs(img, y, x0, x1, 250):
            edges.setdefault((run[0], run[1], run[2]), []).append(y)
    best = None
    for (left, right, _colour), ys in edges.items():
        for top in ys:
            for bottom in ys:
                if 36 <= bottom - top <= 90:
                    px = img.load()
                    # vertical frame edges on both sides
                    if all(px[left, y] == px[left, top] for y in range(top, bottom)) and \
                       all(px[right, y] == px[right, top] for y in range(top, bottom)) and \
                       light_inside(px, left, top, right, bottom):
                        if best is None or right - left > best[2] - best[0]:
                            best = (left, top, right, bottom)
    return best


def analyse(path, region=None):
    from PIL import Image
    img = Image.open(path).convert("RGB")
    region = region or (0, 0, img.width - 1, min(img.height - 1, 260))
    frame = find_gallery(img, region)
    result = {"frame": frame}
    if not frame:
        return result
    left, top, right, bottom = frame
    px = img.load()
    inner_bottom = [px[x, y] for y in (bottom - 1, bottom - 2) for x in range(left + 2, right - 2)]
    result["height"] = bottom - top + 1
    result["ink_at_bottom_edge"] = sum(1 for p in inner_bottom if luminance(p) < 110)
    # count item columns that contain ink (text of the previews)
    columns, inked = [], False
    for x in range(left + 2, right - 2):
        has_ink = any(luminance(px[x, y]) < 110 for y in range(top + 2, bottom - 2))
        if has_ink and not inked:
            columns.append(x)
        inked = has_ink
    result["ink_columns"] = len(columns)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--instdir", default=os.path.join(ROOT, "upstream/libreoffice/instdir"))
    parser.add_argument("--out", default=os.path.join(ROOT, "tests/output/style-gallery"))
    parser.add_argument("--shots", default=os.path.join(ROOT, "tests/output/screenshots-tabs"))
    parser.add_argument("--display", default=":97")
    parser.add_argument("--image")
    parser.add_argument("--name", default="10-style-gallery-after.png")
    args = parser.parse_args()
    args.out = os.path.abspath(args.out)
    os.makedirs(args.out, exist_ok=True)

    if args.image:
        shot = args.image
    else:
        hst_gui.setup_uno(args.instdir)
        office = hst_gui.Office(args.instdir, args.out, PORT, display=args.display).start()
        try:
            office.load("private:factory/swriter")
            time.sleep(8)
            shot = office.screenshot(os.path.join(args.shots, args.name))
        finally:
            office.stop()

    result = analyse(shot)
    checks = []

    def check(name, ok, detail):
        checks.append({"check": name, "status": "PASS" if ok else "FAIL", "detail": detail})
        print(f"{'PASS' if ok else 'FAIL'}  {name}  {detail}")

    frame = result.get("frame")
    check("gallery frame found in the ribbon", frame is not None, repr(frame))
    if frame:
        check("gallery fits the ribbon (40..70 px)", 40 <= result["height"] <= 70, f"height={result['height']}")
        check("no clipped row at the bottom edge", result["ink_at_bottom_edge"] == 0,
              f"ink pixels={result['ink_at_bottom_edge']}")
        check("several style previews shown", result["ink_columns"] >= 3, f"columns={result['ink_columns']}")
    failed = sum(c["status"] == "FAIL" for c in checks)
    with open(os.path.join(args.out, "evidence.json"), "w", encoding="utf-8") as handle:
        json.dump({"screenshot": shot, "analysis": result, "failed": failed, "checks": checks},
                  handle, indent=2, ensure_ascii=False)
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
