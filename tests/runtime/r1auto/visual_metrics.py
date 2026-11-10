# SPDX-License-Identifier: AGPL-3.0-only
"""Measure icon repaint in a stable toolbar, excluding the rotating banner."""
import json
import os


def icon_change(before, after, x, y, width, height):
    import numpy as np
    from PIL import Image
    scale = json.loads(os.environ.get("R1_SCALE_DETAIL", "{}")).get("scale", 1)
    x, y, width, height = [float(v) * scale for v in (x, y, width, height)]
    bounds = tuple(round(v) for v in (x, y, x + width, y + height))
    with Image.open(before) as first, Image.open(after) as second:
        if first.size != second.size or bounds[0] < 0 or bounds[1] < 0 or bounds[2] > first.width or bounds[3] > first.height:
            raise ValueError("Khung toolbar không nằm trong ảnh")
        left = np.asarray(first.convert("RGB").crop(bounds), dtype=np.int16)
        right = np.asarray(second.convert("RGB").crop(bounds), dtype=np.int16)
    return dict(changed_pixels=int((np.abs(left - right).max(axis=2) > 20).sum()), bounds=bounds)


def field_text(shot, x, y, width, height, area_width):
    """Rows of the typed text inside a field, in field pixels, from a screenshot: what the user sees.
    The 2 px inside the field's frame are skipped; ink touching the remaining edge means a clipped glyph."""
    import numpy as np
    from PIL import Image
    s = Image.open(shot).size[0] / float(area_width)  # screenshot pixels per toolkit unit (2 on HiDPI)
    left, top = int(round(float(x) * s)), int(round(float(y) * s))
    right, bottom = int(round((float(x) + float(width)) * s)), int(round((float(y) + float(height)) * s))
    inset = int(round(2 * s))
    luma = np.asarray(Image.open(shot).convert("L"), dtype=np.int16)[top + inset:bottom - inset, left + inset:right - inset]
    rows = np.where((luma < 110).sum(axis=1) > 0)[0]
    if not len(rows):
        return dict(ink=False, inner_height=int(luma.shape[0]))
    first, last, inner = int(rows[0]), int(rows[-1]), int(luma.shape[0])
    return dict(ink=True, inner_height=inner, top=first, bottom=last, above=first, below=inner - 1 - last,
                clipped=first == 0 or last == inner - 1, scale=s)
