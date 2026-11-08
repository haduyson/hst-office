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
