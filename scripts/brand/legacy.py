# SPDX-License-Identifier: AGPL-3.0-only
"""Original outputs: logo, mark and plugin icon set (kept byte-stable)."""
import os

from PIL import Image, ImageDraw, ImageFont

from .common import ROOT, find_font, png_bytes, sha256_file


def render_wordmark(spec, size):
    """Draw the new text so it fills the old wordmark box (same width/height)."""
    left, top, right, bottom = spec["fitBox"]
    box_w, box_h = right - left, bottom - top
    font = ImageFont.truetype(find_font(spec), 200)
    probe = Image.new("L", (4000, 400), 0)
    ImageDraw.Draw(probe).text((50, 50), spec["text"], font=font, fill=255)
    text_img = probe.crop(probe.getbbox()).resize((box_w, box_h), Image.LANCZOS)
    layer = Image.new("RGBA", size, (0, 0, 0, 0))
    color = Image.new("RGBA", (box_w, box_h), spec["color"])
    layer.paste(color, (left, top), text_img)
    return layer


def load_source(spec):
    source_path = os.path.join(ROOT, spec["source"]["path"])
    actual = sha256_file(source_path)
    if actual != spec["source"]["sha256"]:
        raise SystemExit(f"Source logo hash mismatch: {actual}")
    return Image.open(source_path).convert("RGBA")


def build_core(spec, source):
    """Return (outputs, logo, mark)."""
    mark_box = tuple(spec["mark"]["box"])
    # Full logo: start transparent, paste the untouched mark, then the new text.
    logo = Image.new("RGBA", source.size, (0, 0, 0, 0))
    logo.paste(source.crop(mark_box), mark_box[:2])
    logo.alpha_composite(render_wordmark(spec["newText"], source.size))
    mark = source.crop(mark_box)
    outputs = {spec["outputs"]["logo"]: png_bytes(logo), spec["outputs"]["mark"]: png_bytes(mark)}

    side = max(mark.size)
    square = Image.new("RGBA", (side, side), (0, 0, 0, 0))
    square.paste(mark, ((side - mark.width) // 2, (side - mark.height) // 2))
    for size in spec["outputs"]["iconSizes"]:
        inner = max(1, round(size * (1 - 2 * spec["outputs"]["iconPadding"])))
        icon = Image.new("RGBA", (size, size), (0, 0, 0, 0))
        scaled = square.resize((inner, inner), Image.LANCZOS)
        icon.paste(scaled, ((size - inner) // 2, (size - inner) // 2))
        outputs[spec["outputs"]["iconPattern"].format(size=size)] = png_bytes(icon)
    return outputs, logo, mark, square
