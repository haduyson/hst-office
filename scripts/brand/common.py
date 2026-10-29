# SPDX-License-Identifier: AGPL-3.0-only
"""Shared helpers: hashing, deterministic PNG encoding, pinned font, text raster."""
import base64
import hashlib
import io
import os

from PIL import Image, ImageDraw, ImageFont

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
SPEC_PATH = os.path.join(ROOT, "assets", "brand", "brand-spec.json")


def sha256_file(path):
    with open(path, "rb") as handle:
        return hashlib.sha256(handle.read()).hexdigest()


def png_bytes(image):
    """Encode PNG deterministically (Pillow writes no time chunk by default)."""
    buffer = io.BytesIO()
    image.save(buffer, format="PNG", optimize=False, compress_level=9)
    return buffer.getvalue()


def find_font(spec):
    """Return the pinned font file; refuse a different build of the font."""
    for path in spec["fontCandidates"]:
        if os.path.exists(path):
            if sha256_file(path) != spec["fontSha256"]:
                raise SystemExit(f"Font {path} does not match pinned sha256 ({spec['fontPackage']})")
            return path
    raise SystemExit(f"Pinned font not found; install {spec['fontPackage']}")


def render_text(spec, text, color, height):
    """Tight RGBA raster of `text` in the pinned font, natural aspect, given pixel height."""
    font = ImageFont.truetype(find_font(spec), 240)
    probe = Image.new("L", (6000, 600), 0)
    ImageDraw.Draw(probe).text((50, 50), text, font=font, fill=255)
    mask = probe.crop(probe.getbbox())
    width = max(1, round(mask.width * height / mask.height))
    mask = mask.resize((width, height), Image.LANCZOS)
    layer = Image.new("RGBA", mask.size, color)
    layer.putalpha(mask)
    return layer


def svg_with_raster(png, width, height, title):
    """SVG wrapper embedding our own generated raster (pixel units; no external refs)."""
    data = base64.b64encode(png).decode("ascii")
    return (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        f'<svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink" '
        f'width="{width}" height="{height}" viewBox="0 0 {width} {height}">\n'
        f"<title>{title}</title>\n"
        f'<image x="0" y="0" width="{width}" height="{height}" '
        f'xlink:href="data:image/png;base64,{data}"/>\n</svg>\n'
    ).encode("utf-8")
