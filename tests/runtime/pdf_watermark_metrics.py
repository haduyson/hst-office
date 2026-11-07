# SPDX-License-Identifier: AGPL-3.0-only
"""Is a translucent watermark still faint? Pixel measurement against a reference render.

The reference is poppler (pdftoppm) on the original file. Watermark pixels are the light, neutral
grey pixels of the reference that have no dark pixel within 3 px (so anti-aliased edges of the
normal black text are left out). A candidate render of the same page at the same resolution is
compared on those pixels after a 3x3 minimum filter on both images, which tolerates a shift of
one pixel: a faint watermark keeps about the reference grey, a solid one turns them dark.
"""
import os
import subprocess

LIGHT = (200, 250)  # grey levels of a translucent watermark over white paper
DARK = 170  # darker than this is normal text, or a watermark rendered solid
MIN_PIXELS = 200
MEAN_TOLERANCE = 15  # grey levels
MAX_SOLID_SHARE = 0.05


def render(pdf, page, dpi, prefix):
    """pdftoppm of one page; returns the PNG path."""
    os.makedirs(os.path.dirname(str(prefix)), exist_ok=True)
    subprocess.run(["pdftoppm", "-r", str(dpi), "-f", str(page), "-l", str(page), "-singlefile", "-png",
                    str(pdf), str(prefix)], check=True)
    return str(prefix) + ".png"


def _grey(png, size=None):
    import numpy
    from PIL import Image
    image = Image.open(png).convert("RGB")
    if size and image.size != size:
        image = image.resize(size)  # a page size differing by rounding only
    rgb = numpy.asarray(image, dtype=numpy.int16)
    return rgb, image


def watermark_mask(reference_png):
    """(mask, reference image) or (None, image) when the page has no translucent watermark."""
    import numpy
    from PIL import ImageFilter
    rgb, image = _grey(reference_png)
    grey = rgb.mean(axis=2)
    neutral = (rgb.max(axis=2) - rgb.min(axis=2)) < 12
    near_dark = numpy.asarray(image.convert("L").filter(ImageFilter.MinFilter(7))) < DARK
    mask = (grey >= LIGHT[0]) & (grey <= LIGHT[1]) & neutral & ~near_dark
    return (mask if mask.sum() >= MIN_PIXELS else None), image


def measure(reference_png, candidate_png, crop_png=None):
    """{"pixels", "reference_mean", "mean", "solid_share", "faint"} for the watermark pixels."""
    import numpy
    from PIL import Image, ImageFilter
    mask, ref_image = watermark_mask(reference_png)
    if mask is None:
        raise ValueError("no translucent watermark in %s" % reference_png)
    candidate = Image.open(candidate_png).convert("L")
    if candidate.size != ref_image.size:
        candidate = candidate.resize(ref_image.size)
    ref_min = numpy.asarray(ref_image.convert("L").filter(ImageFilter.MinFilter(3)), dtype=float)
    cand_min = numpy.asarray(candidate.filter(ImageFilter.MinFilter(3)), dtype=float)
    result = {"pixels": int(mask.sum()), "reference_mean": round(float(ref_min[mask].mean()), 1),
              "mean": round(float(cand_min[mask].mean()), 1),
              "solid_share": round(float((cand_min[mask] < DARK).mean()), 3)}
    result["faint"] = (abs(result["mean"] - result["reference_mean"]) <= MEAN_TOLERANCE
                       and result["solid_share"] <= MAX_SOLID_SHARE)
    if crop_png:
        ys, xs = numpy.nonzero(mask)
        box = (int(xs.min()), int(ys.min()), int(xs.max()) + 1, int(ys.max()) + 1)
        pair = Image.new("RGB", ((box[2] - box[0]) * 2 + 10, box[3] - box[1]), "white")
        pair.paste(ref_image.crop(box), (0, 0))
        pair.paste(candidate.convert("RGB").crop(box), (box[2] - box[0] + 10, 0))
        os.makedirs(os.path.dirname(crop_png), exist_ok=True)
        pair.save(crop_png)
    return result


def watermark_page(pdf, dpi, workdir):
    """First page of `pdf` that has a translucent watermark in the reference render, or None."""
    out = subprocess.run(["pdfinfo", str(pdf)], capture_output=True, text=True).stdout
    pages = int(next(line.split()[-1] for line in out.splitlines() if line.startswith("Pages:")))
    for page in range(1, pages + 1):
        png = render(pdf, page, dpi, os.path.join(workdir, "reference-p%d" % page))
        if watermark_mask(png)[0] is not None:
            return page, png
    return None, None
