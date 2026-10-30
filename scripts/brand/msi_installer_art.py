#!/usr/bin/env python3
# SPDX-License-Identifier: AGPL-3.0-only
"""Compose the HST Office Windows installer (MSI wizard) artwork.

  .venv/bin/python scripts/brand/msi_installer_art.py [--out branding/windows/installer] [--preview DIR]

Designed with Codex CLI (model gpt-6-astra): the two background illustrations in
branding/windows/installer/source/ came from its image generator (prompts in prompts.json),
this composition script was written by it and adapted here (repo paths, 24-bit BMP).
The real HST mark pixels are pasted (never redrawn); text uses Liberation Sans.
Outputs: Image.bmp (162x312, Welcome/Completed side panel) and Banner.bmp (632x57, inner
page banner) at the exact pixel sizes of the upstream bitmaps they replace, plus PNG masters.
scripts/windows/trial-build.sh --patch copies the BMPs into
instsetoo_native/inc_common/windows/msi_templates/Binary/. No network access.
"""

import argparse
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont, ImageOps


REPO = Path(__file__).resolve().parents[2]
ART_DIR = REPO / "branding" / "windows" / "installer"
DEFAULT_MARK = REPO / "assets" / "brand" / "hst-office-mark.png"
DEFAULT_FONTS = Path("/usr/share/fonts/truetype/liberation")
SIDE_SIZE = (162, 312)
BANNER_SIZE = (632, 57)
PAGE_SIZE = (632, 358)
WHITE = (255, 255, 255)
DIALOG_GREY = (240, 240, 240)
BRAND_BLUE = (0, 114, 187)


def load_rgb(path):
    with Image.open(path) as image:
        return image.convert("RGB")


def font(font_dir, size, bold=False):
    weight = "Bold" if bold else "Regular"
    return ImageFont.truetype(
        str(font_dir / f"LiberationSans-{weight}.ttf"),
        size,
        layout_engine=ImageFont.Layout.BASIC,
    )


def paste_mark(canvas, mark, height, xy):
    """Resample the supplied RGBA pixels without recoloring or redrawing."""
    width = round(mark.width * height / mark.height)
    scaled = mark.resize((width, height), Image.Resampling.LANCZOS)
    canvas.paste(scaled, xy, scaled.getchannel("A"))


def make_side(background, mark, font_dir):
    # Crop the larger portrait at its top to leave breathing room above the papers.
    side = ImageOps.fit(
        background, (162, 344), method=Image.Resampling.LANCZOS
    ).crop((0, 0, *SIDE_SIZE))
    # Calm the generated blues toward the brand color while retaining detail.
    side = Image.blend(side, Image.new("RGB", SIDE_SIZE, BRAND_BLUE), 0.18)

    # Supersample just the tile so its rounded edges remain clean at native DPI.
    tile = Image.new("RGBA", (82 * 4, 82 * 4))
    ImageDraw.Draw(tile).rounded_rectangle(
        (0, 0, tile.width - 1, tile.height - 1), radius=12 * 4, fill=WHITE
    )
    tile = tile.resize((82, 82), Image.Resampling.LANCZOS)
    side.paste(tile, (40, 30), tile.getchannel("A"))
    paste_mark(side, mark, height=57, xy=(48, 42))

    draw = ImageDraw.Draw(side)
    draw.text(
        (81, 132), "HST Office", font=font(font_dir, 23, bold=True),
        fill=WHITE, anchor="mt",
    )
    draw.text(
        (81, 164), "Văn phòng cho người Việt", font=font(font_dir, 12),
        fill=WHITE, anchor="mt",
    )
    return side


def make_banner(background, mark):
    banner = Image.new("RGB", BANNER_SIZE, WHITE)
    accent = ImageOps.fit(background, (180, 57), method=Image.Resampling.LANCZOS)

    # Fade the accent in; x=0..451 stays exactly white for Windows-owned copy.
    fade = Image.new("L", accent.size)
    fade.putdata([min(255, x * 255 // 48) for y in range(57) for x in range(180)])
    # Lighten the wave beneath the original blue mark to preserve contrast.
    accent = Image.blend(Image.new("RGB", accent.size, WHITE), accent, 0.42)
    banner.paste(accent, (452, 0), fade)
    paste_mark(banner, mark, height=40, xy=(567, 8))
    return banner


def save_asset(image, out, stem, bmp_name):
    """PNG master plus the MSI bitmap: uncompressed 24-bit BMP (BITMAPINFOHEADER).

    24-bit instead of the upstream 8-bit palette: Windows Installer Bitmap controls load
    24-bit BMPs, and an adaptive 256-colour palette left visible dither noise on the
    gradients of this artwork.
    """
    image.save(out / f"{stem}.png", format="PNG", compress_level=9)
    image.save(out / bmp_name, format="BMP")
    with Image.open(out / bmp_name) as bitmap:
        return bitmap.convert("RGB")


def save_png(image, path):
    image.save(path, format="PNG", compress_level=9)


def save_3x(image, path):
    save_png(
        image.resize((image.width * 3, image.height * 3), Image.Resampling.NEAREST),
        path,
    )


def make_previews(side, banner, font_dir):
    welcome = Image.new("RGB", PAGE_SIZE, DIALOG_GREY)
    welcome.paste(side, (0, 0))
    draw = ImageDraw.Draw(welcome)
    title_face = font(font_dir, 18, bold=True)
    title = ("Chào mừng bạn đến với", "Trình cài đặt HST Office 1.0.0")
    for index, line in enumerate(title):
        draw.text((180, 26 + index * 25), line, font=title_face, fill="black", anchor="lt")

    inner = Image.new("RGB", PAGE_SIZE, DIALOG_GREY)
    inner.paste(banner, (0, 0))
    draw = ImageDraw.Draw(inner)
    draw.text(
        (15, 10), "Kiểu cài đặt", font=font(font_dir, 14, bold=True),
        fill="black", anchor="lt",
    )
    draw.text(
        (25, 30), "Chọn kiểu cài đặt phù hợp nhất.", font=font(font_dir, 12),
        fill="black", anchor="lt",
    )
    return welcome, inner


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[1])
    parser.add_argument("--out", type=Path, default=ART_DIR, help="output directory")
    parser.add_argument("--preview", type=Path, help="also write dialog mock-ups here")
    parser.add_argument("--generated", type=Path, default=ART_DIR / "source")
    parser.add_argument("--mark", type=Path, default=DEFAULT_MARK)
    parser.add_argument("--fonts", type=Path, default=DEFAULT_FONTS)
    args = parser.parse_args()

    side_background = load_rgb(args.generated / "side-background.png")
    banner_background = load_rgb(args.generated / "banner-background.png")
    with Image.open(args.mark) as source:
        mark = source.convert("RGBA")
    side = make_side(side_background, mark, args.fonts)
    banner = make_banner(banner_background, mark)

    args.out.mkdir(parents=True, exist_ok=True)
    side_bmp = save_asset(side, args.out, "hst-installer-side", "Image.bmp")
    banner_bmp = save_asset(banner, args.out, "hst-installer-banner", "Banner.bmp")
    if args.preview:
        args.preview.mkdir(parents=True, exist_ok=True)
        welcome, inner = make_previews(side_bmp, banner_bmp, args.fonts)
        save_png(welcome, args.preview / "preview-welcome.png")
        save_png(inner, args.preview / "preview-inner.png")
        for name, image in (("welcome", welcome), ("inner", inner)):
            save_3x(image, args.preview / f"preview-{name}-3x.png")
    print(f"wrote Image.bmp, Banner.bmp and PNG masters to {args.out}")


if __name__ == "__main__":
    main()
