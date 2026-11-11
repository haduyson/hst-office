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
    candidate, shift = aligned(reference, candidate)
    result = pdf_watermark_metrics.measure(reference, candidate, crop)
    result["alignment_shift"] = shift
    pixels = np.asarray(Image.open(candidate).convert("RGB"), dtype=np.int16)
    result["red_pixels"] = int(((pixels[:, :, 0] > 140) & (pixels[:, :, 0] > pixels[:, :, 1] * 1.5) &
                                (pixels[:, :, 0] > pixels[:, :, 2] * 1.5)).sum())
    return result


def aligned(reference, candidate):
    """The candidate shifted onto the reference by the red stamp's centroid. macOS "Lưu thành PDF" places the page
    about 25 px right and 21 px down at 96 dpi with the same scale (r1-auto macOS run 42902193858), so fixed watermark
    pixels landed on paper. A pure translation; the shift is reported with the measurement."""
    import numpy as np
    from PIL import Image, ImageChops
    size = Image.open(reference).size
    image = Image.open(candidate).convert("RGB")
    if image.size != size:  # a thumbnail: compare at the reference's size, as pdf_watermark_metrics.measure does
        image = image.resize(size)
    def centroid(source):
        rgb = np.asarray(source if isinstance(source, Image.Image) else Image.open(source).convert("RGB"),
                         dtype=np.int16)
        red = (rgb[..., 0] > 140) & (rgb[..., 0] > rgb[..., 1] * 1.5) & (rgb[..., 0] > rgb[..., 2] * 1.5)
        # Only the stamp's solid strokes: a red pixel whose four neighbours are red too. Windows' Draw export
        # fringes black glyph edges red (subpixel text); those 1 px fringes on the title moved the centroid by
        # (10, 23) px, the shift moved the watermark off the reference (r1-auto Windows run 42947181746, W13).
        solid = np.zeros_like(red)
        solid[1:-1, 1:-1] = (red[1:-1, 1:-1] & red[:-2, 1:-1] & red[2:, 1:-1] & red[1:-1, :-2] & red[1:-1, 2:])
        ys, xs = np.nonzero(solid)
        return (float(xs.mean()), float(ys.mean())) if len(xs) > 100 else None
    a, b = centroid(reference), centroid(image)
    if not a or not b:
        return candidate, None
    dx, dy = round(a[0] - b[0]), round(a[1] - b[1])
    if abs(dx) <= 1 and abs(dy) <= 1:
        return candidate, [0, 0]
    moved = ImageChops.offset(image, dx, dy)
    target = Path(candidate).with_name(Path(candidate).stem + "-aligned.png")
    moved.save(target)
    return target, [dx, dy]
