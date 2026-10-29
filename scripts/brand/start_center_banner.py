# SPDX-License-Identifier: AGPL-3.0-only
"""Deterministic, opaque Start Center card with exact Vietnamese campaign copy."""
from PIL import Image, ImageDraw, ImageFont

from .common import find_font, png_bytes


def render_banner(spec, mark):
    """Render at 2× the asset size for smooth corners, then downscale the mark once."""
    cfg = spec["startCenterBanner"]
    width, height = cfg["size"]
    scale = 2
    canvas = Image.new("RGBA", (width * scale, height * scale), (0, 0, 0, 0))
    draw = ImageDraw.Draw(canvas)
    palette = cfg["palette"]
    blue, ink = spec["mark"]["color"], spec["newText"]["color"]
    fonts = {name: find_font(font) for name, font in cfg["fonts"].items()}

    def font(name, size):
        return ImageFont.truetype(fonts[name], size * scale,
                                  layout_engine=ImageFont.Layout.BASIC)

    def rounded(box, radius, fill, outline=None):
        draw.rounded_rectangle(tuple(v * scale for v in box), radius * scale,
                               fill=fill, outline=outline, width=2 * scale)

    def text(position, value, face, color, anchor="ls"):
        draw.text(tuple(v * scale for v in position), value,
                  font=face, fill=color, anchor=anchor)

    rounded((2, 2, width - 3, height - 3), 24, palette["card"], palette["border"])
    headline = font("bold", 32)
    prefix, brand = cfg["leadText"].rsplit("HASON TECH", 1)
    text((156, 64), prefix, headline, ink)
    text((156 + draw.textlength(prefix, font=headline) / scale, 64),
         "HASON TECH" + brand, headline, blue)

    label = font("regular", 24)
    x = 156
    for solution in cfg["solutions"]:
        chip_width = round(draw.textlength(solution, font=label) / scale) + 20
        rounded((x, 88, x + chip_width, 128), 10, palette["chip"])
        text((x + 10, 116), solution, label, ink)
        x += chip_width + 8
    if x - 8 > 992:
        raise ValueError("Solution labels exceed the banner content area")

    rounded((1024, 52, 1248, 108), 12, blue)
    text((1136, 80), cfg["callToAction"], font("bold", 24), palette["card"], "mm")
    banner = canvas.resize((width, height), Image.Resampling.LANCZOS)
    mark_width = 90
    mark_height = round(mark.height * mark_width / mark.width)
    if mark_width > mark.width or mark_height > mark.height:
        raise ValueError("Start Center mark must only be scaled down")
    banner.alpha_composite(mark.resize((mark_width, mark_height), Image.Resampling.LANCZOS),
                           (34, (height - mark_height) // 2))
    return banner


def build_start_center_banner(spec, mark):
    """Return the HiDPI PNG and opaque previews at the actual logical display size."""
    cfg = spec["startCenterBanner"]
    banner = render_banner(spec, mark)
    outputs = {cfg["path"]: png_bytes(banner)}
    displayed = banner.resize(tuple(cfg["logicalSize"]), Image.Resampling.LANCZOS)
    for name, color in cfg["previewBackgrounds"].items():
        preview = Image.new("RGBA", displayed.size, color)
        preview.alpha_composite(displayed)
        outputs[cfg["previewPattern"].format(theme=name)] = png_bytes(preview)
    return outputs
