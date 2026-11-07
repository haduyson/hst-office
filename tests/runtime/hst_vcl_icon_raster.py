# SPDX-License-Identifier: AGPL-3.0-only
"""Rasterise SVG icons through VCL's own pipeline and measure their sharpness.

VCL loads an SVG icon with vcl::bitmap::loadFromSvg (vcl/source/bitmap/BitmapTools.cxx): the SVG
is decomposed by com.sun.star.graphic.SvgTools and rasterised by
com.sun.star.graphic.Primitive2DTools at 96 DPI x scale over the primitives' range. This module
makes the same two UNO calls in a running HST Office, so the alpha values are VCL's, with its
device pixel-centre convention, not those of rsvg or a browser.

`fringe_share` is the sharpness metric of the blurry-icon investigation: the share of inked
pixels (alpha >= 8 %) that are only partly covered (alpha < 80 %). A crisp 1 px line has 0.
"""

INK = 0.08
SOLID = 0.80


def _service(ctx, name):
    return ctx.ServiceManager.createInstanceWithContext(name, ctx)


def rasterise(ctx, svg, scale=1.0, name="icon.svg", argb=False):
    """Return (width, height, rows) of `svg` (bytes) as VCL renders it at `scale`: alpha 0..1 per
    pixel, or (alpha, red, green, blue) 0..1 tuples with argb=True."""
    # Python-UNO comes from the instdir; hst_gui.setup_uno must have run before the first call.
    import uno
    from com.sun.star.geometry import IntegerRectangle2D, RealRectangle2D
    stream = ctx.ServiceManager.createInstanceWithArgumentsAndContext(
        "com.sun.star.io.SequenceInputStream", (uno.ByteSequence(bytes(svg) + b"\0"),), ctx)
    primitives = _service(ctx, "com.sun.star.graphic.SvgTools").getDecomposition(stream, name)
    if not primitives:
        raise ValueError(f"{name}: SVG decomposition is empty")
    x1 = y1 = float("inf")
    x2 = y2 = float("-inf")
    for primitive in primitives:
        box = primitive.getRange(())
        x1, y1, x2, y2 = min(x1, box.X1), min(y1, box.Y1), max(x2, box.X2), max(y2, box.Y2)
    dpi = 96.0 * scale
    bitmap = _service(ctx, "com.sun.star.graphic.Primitive2DTools").rasterize(
        primitives, (), dpi, dpi, RealRectangle2D(x1, y1, x2, y2), 256 * 256)
    if bitmap is None:
        raise ValueError(f"{name}: VCL returned no bitmap")
    size = bitmap.getSize()
    data, layout = bitmap.getData(None, IntegerRectangle2D(0, 0, size.Width, size.Height))
    colours = layout.ColorSpace.convertIntegerToARGB(data)
    if len(colours) != size.Width * size.Height:
        raise ValueError(f"{name}: unexpected pixel count {len(colours)}")
    pixels = [(c.Alpha, c.Red, c.Green, c.Blue) for c in colours] if argb else [c.Alpha for c in colours]
    return size.Width, size.Height, [pixels[row * size.Width:(row + 1) * size.Width] for row in range(size.Height)]


def fringe_share(rows):
    """Share of inked pixels that are only partly covered; None for an empty raster."""
    inked = [a for row in rows for a in row if a >= INK]
    if not inked:
        return None
    return sum(1 for a in inked if a < SOLID) / len(inked)


def png_alpha_rows(path):
    """Alpha rows (0..1) of a PNG written by VCL's icon cache. Needs Pillow."""
    from PIL import Image
    with Image.open(path) as image:
        rgba = image.convert("RGBA")
        width, height = rgba.size
        alpha = list(rgba.getchannel("A").getdata())
    return [[a / 255.0 for a in alpha[row * width:(row + 1) * width]] for row in range(height)]


LOGICAL = {"sc_": 16, "lc_": 24, "32/": 32}


def logical_size(name):
    """16/24/32 from a cmd resource name (cmd/sc_x.png, cmd/lc_x.png, cmd/32/x.png)."""
    base = name.split("cmd/", 1)[-1]
    for prefix, size in LOGICAL.items():
        if base.startswith(prefix):
            return size
    return None


def summarise(rows, limit, sizes=(16, 24)):
    """Median fringe share per logical size, with the failures against `limit`."""
    summary, failures = {}, []
    for size in (16, 24, 32):
        values = [r["fringe"] for r in rows if r["size"] == size and r["fringe"] is not None]
        if not values:
            continue
        middle = median(values)
        summary[str(size)] = {"count": len(values), "median_fringe": round(middle, 3),
                              "worst": sorted(((round(r["fringe"], 3), r["name"]) for r in rows
                                               if r["size"] == size and r["fringe"] is not None), reverse=True)[:5]}
        if size in sizes and middle > limit:
            failures.append(f"median fringe share {middle:.2f} at {size} px exceeds {limit:.2f}")
    return summary, failures


def median(values):
    ordered = sorted(values)
    if not ordered:
        return None
    middle = len(ordered) // 2
    return ordered[middle] if len(ordered) % 2 else (ordered[middle - 1] + ordered[middle]) / 2
