# SPDX-License-Identifier: LicenseRef-HST-Proprietary
"""Image loading and the pre-processing shared by every recogniser."""
from PIL import Image, ImageOps

from .protocol import OcrError

MAX_PIXELS = 60_000_000  # ~ A3 at 600 dpi; bigger images are refused instead of exhausting memory
MIN_SIDE = 8


def load(path):
    """Grayscale PIL image, EXIF orientation applied. Raises OcrError on unreadable or absurd images."""
    Image.MAX_IMAGE_PIXELS = MAX_PIXELS
    try:
        with Image.open(path) as img:
            img = ImageOps.exif_transpose(img)
            if img.mode in ("RGBA", "LA", "P"):
                img = img.convert("RGBA")
                bg = Image.new("RGBA", img.size, (255, 255, 255, 255))
                img = Image.alpha_composite(bg, img)
            gray = img.convert("L")
    except Image.DecompressionBombError as exc:
        raise OcrError("image-too-large", "image has more than %d pixels" % MAX_PIXELS) from exc
    except (OSError, ValueError, SyntaxError) as exc:
        raise OcrError("image-unreadable", "cannot read image: %s" % exc) from exc
    if min(gray.size) < MIN_SIDE:
        raise OcrError("image-unreadable", "image is too small")
    return gray


def normalise_scale(img, min_text_width=2000):
    """Upscale low-resolution page images (a phone photo or a 150 dpi scan) so Tesseract sees glyphs close to the
    300 dpi size it reads best. Returns (image, factor); bbox values must be divided by factor to map back."""
    if img.width >= min_text_width:
        return img, 1.0
    factor = min(3.0, min_text_width / img.width)
    return img.resize((round(img.width * factor), round(img.height * factor)), Image.LANCZOS), factor


def skew_angle(img, max_deg=3.0, step=0.1):
    """Skew of the text/ruling lines in degrees (positive = counter-clockwise), by maximising the variance of the
    horizontal ink projection over candidate angles on a downscaled copy. 0.0 when the page has no ink."""
    import numpy as np
    small = img.copy()
    small.thumbnail((800, 800))
    ink = Image.eval(small, lambda v: 255 if v < 128 else 0)
    if not ink.getbbox():
        return 0.0
    best, best_score = 0.0, -1.0
    for i in range(int(-max_deg / step), int(max_deg / step) + 1):
        angle = i * step
        rows = np.asarray(ink.rotate(angle, resample=Image.NEAREST, expand=False), dtype=np.float32).sum(axis=1)
        score = float(np.var(rows))
        if score > best_score:
            best, best_score = angle, score
    return best


def deskew(img, max_deg=3.0):
    """(straightened image, angle). Small angles below 0.15° are left alone to avoid resampling blur."""
    angle = skew_angle(img, max_deg)
    if abs(angle) < 0.15:
        return img, 0.0
    return img.rotate(angle, resample=Image.BICUBIC, expand=True, fillcolor=255), angle
