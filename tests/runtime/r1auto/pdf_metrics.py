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
        # Dark glyph pixels that are not stamp red, counted (not overlapped) in a band 4 px taller than the
        # reference text: Draw's export shifts glyphs 1-2 px and fringes them bluish, which an exact neutral-grey
        # overlap read as covered (r1-auto Windows run 42471627670, W13: 0.09 for visibly intact text).
        # Intact Draw text measures about 0.77, half covered 0.43, covered 0.
        def ink(path, top, bottom):
            image = Image.open(path).convert("RGB").resize((595, 842))
            rgb = np.asarray(image, dtype=np.int16)[top:bottom, 340:490]
            r, g, b = rgb[..., 0], rgb[..., 1], rgb[..., 2]
            red = (r > 120) & (r > g * 1.6) & (r > b * 1.6)
            return int(((rgb.mean(axis=2) < 120) & ~red).sum())
        before, after = ink(reference, 655, 674), ink(candidate, 651, 678)
        if before < 40:
            raise ValueError("Thiếu chữ đối chiếu trên con dấu")
        return min(1.0, after / before)
    result = pdf_watermark_metrics.measure(reference, candidate, crop)
    pixels = np.asarray(Image.open(candidate).convert("RGB"), dtype=np.int16)
    result["red_pixels"] = int(((pixels[:, :, 0] > 140) & (pixels[:, :, 0] > pixels[:, :, 1] * 1.5) &
                                (pixels[:, :, 0] > pixels[:, :, 2] * 1.5)).sum())
    return result
