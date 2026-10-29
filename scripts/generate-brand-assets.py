"""Generate HST Office brand assets from the owner-provided HASON TECH logo.

The blue "HS" triangle mark is copied pixel-for-pixel from the source; only the
"HASON TECH" wordmark is replaced by "HST OFFICE". Icons are downscaled from the
mark. Output PNGs carry no timestamps so runs are byte-identical.

Usage:
  python3 scripts/generate-brand-assets.py          # write outputs
  python3 scripts/generate-brand-assets.py --check  # render to temp, compare, exit 1 on drift
"""
import argparse
import hashlib
import io
import json
import os
import sys

from PIL import Image, ImageDraw, ImageFont

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
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


def build_assets(spec):
    source_path = os.path.join(ROOT, spec["source"]["path"])
    actual = sha256_file(source_path)
    if actual != spec["source"]["sha256"]:
        raise SystemExit(f"Source logo hash mismatch: {actual}")
    source = Image.open(source_path).convert("RGBA")
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
    return outputs


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--check", action="store_true", help="verify committed outputs are current")
    args = parser.parse_args()
    with open(SPEC_PATH, encoding="utf-8") as handle:
        spec = json.load(handle)
    outputs = build_assets(spec)

    drift = []
    for rel_path, data in sorted(outputs.items()):
        path = os.path.join(ROOT, rel_path)
        if args.check:
            if not os.path.exists(path) or open(path, "rb").read() != data:
                drift.append(rel_path)
            continue
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "wb") as handle:
            handle.write(data)
        print(f"wrote {rel_path} {hashlib.sha256(data).hexdigest()[:16]}")
    if drift:
        print("Brand assets out of date:", ", ".join(drift), file=sys.stderr)
        return 1
    if args.check:
        print(f"brand assets up to date ({len(outputs)} files)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
