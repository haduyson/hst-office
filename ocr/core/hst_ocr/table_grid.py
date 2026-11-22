# SPDX-License-Identifier: LicenseRef-HST-Proprietary
"""Bordered-table structure from ruling lines (OpenCV morphology, no model), cell text with Tesseract.

Exam papers and administrative forms in Vietnam almost always draw every cell border, so the grid is read from the
lines themselves: long horizontal and vertical strokes are kept by morphological opening, their projections give
row and column boundaries, and a missing border segment between two grid cells marks a merged cell. Borderless
tables return None so the caller can fall back to a model (see the report: TATR, MIT, is the candidate).
"""
import numpy as np

from . import text_tesseract

MIN_LINE_FRACTION = 0.5   # a border must span at least half the table's width/height to count as a grid line
PSM = 11                  # Tesseract "sparse text": cells are islands of text, no column layout to infer
BORDER_COVERAGE = 0.6     # a cell edge "exists" when this share of its length is covered by line pixels


def _lines(binary, horizontal, length):
    import cv2
    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (length, 1) if horizontal else (1, length))
    return cv2.morphologyEx(binary, cv2.MORPH_OPEN, kernel)


def _positions(mask, axis, min_fraction):
    """Centres of runs of rows (axis=1) or columns (axis=0) whose line coverage passes min_fraction."""
    coverage = (mask > 0).sum(axis=axis) / mask.shape[axis]
    hits = np.nonzero(coverage >= min_fraction)[0]
    if not len(hits):
        return []
    groups, start, prev = [], hits[0], hits[0]
    for idx in hits[1:]:
        if idx > prev + 2:
            groups.append((start + prev) // 2)
            start = idx
        prev = idx
    groups.append((start + prev) // 2)
    return [int(g) for g in groups]


def _median_glyph_height(binary):
    import cv2
    _, _, stats, _ = cv2.connectedComponentsWithStats(binary)
    heights = [st[3] for st in stats[1:] if 12 <= st[4] and st[3] < binary.shape[0] / 4 and st[2] < binary.shape[1] / 4]
    return float(np.median(heights)) if heights else 20.0


def detect_grid(gray):
    """(row_ys, col_xs, horizontal_mask, vertical_mask) or None when no bordered grid is found."""
    import cv2
    arr = np.asarray(gray, dtype=np.uint8)
    binary = cv2.adaptiveThreshold(255 - arr, 255, cv2.ADAPTIVE_THRESH_MEAN_C, cv2.THRESH_BINARY, 15, -10)
    glyph = _median_glyph_height(binary)
    # Kernels well above a glyph's height: letter stems (l, h, đ) must not pass for cell borders.
    h_mask = _lines(binary, True, max(40, int(4 * glyph)))
    v_mask = _lines(binary, False, max(30, int(2.2 * glyph)))
    pts = np.nonzero((h_mask > 0) | (v_mask > 0))
    if not len(pts[0]):
        return None
    box = (slice(pts[0].min(), pts[0].max() + 1), slice(pts[1].min(), pts[1].max() + 1))  # the ruled area
    ys = [int(y + box[0].start) for y in _positions(h_mask[box], 1, MIN_LINE_FRACTION)]
    xs = [int(x + box[1].start) for x in _positions(v_mask[box], 0, MIN_LINE_FRACTION)]
    if len(ys) < 2 or len(xs) < 2:
        return None
    return ys, xs, h_mask, v_mask


def _edge(mask, fixed, a, b, horizontal, band=4):
    """True when the border segment between a and b at coordinate fixed is drawn."""
    if horizontal:
        strip = mask[max(0, fixed - band):fixed + band + 1, a:b]
        covered = (strip > 0).any(axis=0)
    else:
        strip = mask[a:b, max(0, fixed - band):fixed + band + 1]
        covered = (strip > 0).any(axis=1)
    return covered.size and covered.mean() >= BORDER_COVERAGE


def cells(gray, lang="vie", threads=2):
    """{"rows": [[text]], "cells": [{"r", "c", "rowspan", "colspan", "text"}]} or None when not a bordered table.
    The image is straightened first: on a 0.6° skewed scan a long border drifts several pixels and the line
    kernels would break it into pieces."""
    from .imaging import deskew
    gray, _ = deskew(gray)
    grid = detect_grid(gray)
    if grid is None:
        return None
    ys, xs, h_mask, v_mask = grid
    n_rows, n_cols = len(ys) - 1, len(xs) - 1
    owner = [[None] * n_cols for _ in range(n_rows)]
    found = []
    for r in range(n_rows):
        for c in range(n_cols):
            if owner[r][c] is not None:
                continue
            cs = 1
            while c + cs < n_cols and not _edge(v_mask, xs[c + cs], ys[r], ys[r + 1], False):
                cs += 1
            rs = 1
            while r + rs < n_rows and not _edge(h_mask, ys[r + rs], xs[c], xs[c + cs], True):
                rs += 1
            for rr in range(r, r + rs):
                for cc in range(c, c + cs):
                    owner[rr][cc] = len(found)
            found.append({"r": r, "c": c, "rowspan": rs, "colspan": cs,
                          "box": (xs[c], ys[r], xs[c + cs], ys[r + rs])})
    rows = [[""] * n_cols for _ in range(n_rows)]
    words = _words_without_rules(gray, h_mask, v_mask, lang, threads)
    for cell in found:
        x0, y0, x1, y1 = cell.pop("box")
        inside = [w for w in words if x0 <= w[0] < x1 and y0 <= w[1] < y1]
        cell["text"] = " ".join(w[4] for w in _reading_order(inside))
        rows[cell["r"]][cell["c"]] = cell["text"]
    return {"rows": rows, "cells": found, "bbox": [xs[0], ys[0], xs[-1] - xs[0], ys[-1] - ys[0]]}


def _reading_order(words):
    """Words grouped into lines (centres within half a median word height), lines top to bottom, words left to right."""
    if not words:
        return []
    tol = 0.5 * float(np.median([w[3] for w in words]))
    lines = []
    for word in sorted(words, key=lambda w: w[1]):
        if lines and abs(word[1] - lines[-1][0]) <= tol:
            lines[-1][1].append(word)
        else:
            lines.append([word[1], [word]])
    return [w for _, line in lines for w in sorted(line, key=lambda w: w[0])]


def _words_without_rules(gray, h_mask, v_mask, lang, threads):
    """[(centre_x, centre_y, width, height, text)] of every word, read once for the whole table after the ruling
    lines are painted white (lines confuse Tesseract's layout analysis; one run instead of one per cell is ~10x
    faster because each Tesseract start loads the language model)."""
    from PIL import Image
    arr = np.asarray(gray, dtype=np.uint8).copy()
    import cv2
    rules = cv2.dilate(((h_mask > 0) | (v_mask > 0)).astype(np.uint8), np.ones((5, 5), np.uint8))
    arr[rules > 0] = 255
    tsv = text_tesseract.run_tsv(Image.fromarray(arr), lang, threads, psm=PSM)
    words = []
    for row in tsv.splitlines()[1:]:
        cols = row.split("\t")
        if len(cols) == 12 and cols[0] == "5" and cols[11].strip():
            x, y, w, h = (int(c) for c in cols[6:10])
            words.append((x + w // 2, y + h // 2, w, h, cols[11].strip()))
    return words
