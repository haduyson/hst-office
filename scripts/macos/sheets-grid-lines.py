#!/usr/bin/env python3
# SPDX-License-Identifier: LicenseRef-HST-Proprietary
# Copyright (C) 2026 HASON TECH
"""Fill grid_line_rows of the sheets-grid-probe JSON files in a directory from their screenshots.

  sheets-grid-lines.py <out-dir>

Horizontal grid lines show as screenshot rows darker than their neighbours (median of seven rows, by at least six
grey levels) in a strip across the middle 30 % of the width. A blank white grid gives a count near zero.
"""
import glob
import json
import os
import sys

from PIL import Image

out = sys.argv[1]
for jf in sorted(glob.glob(os.path.join(out, "*-zoom*.json"))):
    with open(jf, encoding="utf-8") as f:
        rec = json.load(f)
    path = os.path.join(out, rec.get("screenshot", ""))
    if not os.path.exists(path):
        rec["grid_line_rows"] = None
    else:
        im = Image.open(path).convert("L")
        w, h = im.size
        px = im.load()
        xs = list(range(int(w * 0.35), int(w * 0.65), 4))
        means = [sum(px[x, y] for x in xs) / len(xs) for y in range(h)]
        count = 0
        for y in range(3, h - 3):
            local = sorted(means[y - 3:y + 4])[3]
            if means[y] < local - 6:
                count += 1
        rec["grid_line_rows"] = count
        rec["screen_rows"] = h
    with open(jf, "w", encoding="utf-8") as f:
        json.dump(rec, f, indent=1, ensure_ascii=False)
    print(json.dumps({k: rec.get(k) for k in ("label", "zoom_target", "zoom_read", "a1", "b2", "grid_line_rows")}, ensure_ascii=False))
