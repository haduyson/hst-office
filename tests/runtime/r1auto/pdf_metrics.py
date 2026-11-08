# SPDX-License-Identifier: AGPL-3.0-only
"""Pixel analysis runs in tooling Python; bundled pyuno needs no binary pip packages."""
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


def run(action, reference, candidate, crop=None):
    import numpy as np
    from PIL import Image
    import pdf_watermark_metrics
    if action == "text-band":
        def band(path):
            image = Image.open(path).convert("RGB").resize((595, 842))
            rgb = np.asarray(image, dtype=np.int16)[655:674, 340:490]
            return (rgb.mean(axis=2) < 100) & (rgb.max(axis=2) - rgb.min(axis=2) < 25)
        before, after = band(reference), band(candidate)
        if before.sum() < 40:
            raise ValueError("Thiếu chữ đối chiếu trên con dấu")
        return float((before & after).sum() / before.sum())
    result = pdf_watermark_metrics.measure(reference, candidate, crop)
    pixels = np.asarray(Image.open(candidate).convert("RGB"), dtype=np.int16)
    result["red_pixels"] = int(((pixels[:, :, 0] > 140) & (pixels[:, :, 0] > pixels[:, :, 1] * 1.5) &
                                (pixels[:, :, 0] > pixels[:, :, 2] * 1.5)).sum())
    return result
