#!/usr/bin/env python3
# SPDX-License-Identifier: AGPL-3.0-only
"""Build the Vietnamese/HST tip-of-the-day images from the upstream SVG sources.

Usage: python3 scripts/l10n/build-tip-images.py [--tree upstream/libreoffice] [--out l10n/vi-tipoftheday]

The tip images in extras/source/tipoftheday show English UI words (and one upstream application icon
and an upstream web address). For each image listed in TEXT this script replaces the English strings with
the Vietnamese UI labels of HST Office, swaps the upstream Calc icon for the HST Sheets icon, renders the
SVG with rsvg-convert at the upstream pixel size and writes <name>.svg and <name>.png to --out.
The default bulb overlays (icon-themes/*/res/tipoftheday_{w,c,i,d}.png, which carry upstream application
icons) are recomposed per theme with the HST application icons. scripts/l10n/apply-overrides.py copies the results into the tree.
Images without words (icon_sets.png, marchingants.gif) are kept.
"""
import argparse
import base64
import glob
import io
import os
import re
import subprocess
import sys

from PIL import Image

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
FONT = "'Liberation Sans', 'DejaVu Sans', sans-serif"
# image -> [(english tspan text, vietnamese text, font scale)]
TEXT = {
    "expand_formula_bar": [("Cannot see all the", "Không thấy hết chữ", 0.95), ("text in a cell?", "trong một ô?", 1),
                           ("Expand the input", "Mở rộng dòng", 1), ("line in the formula", "nhập trên thanh", 1),
                           ("bar and you can", "công thức để", 1), ("scroll", "cuộn xem", 1)],
    "formdocuments": [("PDF Form", "Biểu mẫu PDF", 0.9), ("Text Box", "Hộp văn bản", 1), ("Checkbox", "Hộp chọn", 1),
                      ("Radio Button", "Nút tùy chọn", 1)],
    "fraction": [("Fraction", "Phân số", 1), ("0.125  =  1/8", "0,125  =  1/8", 1)],
    "hybrid_pdf": [("PDF + ODF", "PDF + ODF", 1), ("PDF Export", "Xuất PDF", 1), ("Hybrid PDF", "PDF lai", 1)],
    "masterdocument": [("Thesis", "Luận văn", 1), ("Introduction", "Mở đầu", 1), ("Methodology.odt", "Phuong-phap.odt", 0.95),
                       ("Results", "Kết quả", 1)],
    "printnote": [("General", "Chung", 1), ("Impress", "Trình chiếu", 0.8), ("Slides", "Trang chiếu", 0.85),
                  ("Handout", "Bản phát", 0.9), ("Notes", "Ghi chú", 0.9), ("Outline", "Dàn ý", 0.9),
                  ("Document", "Tài liệu", 1), ("Type :", "Kiểu :", 1)],
    "remove_hyperlink": [("Hyperlink", "Siêu liên kết", 0.85), ("www.libreoffice.org", "www.hasontech.vn", 1),
                         ("Remove", "Bỏ siêu", 1)],
    "statusbar": [("Average: 20 / Sum: 60", "Trung bình: 20 / Tổng: 60", 0.85), ("Average", "Trung bình", 1),
                  ("Count", "Đếm", 1), ("Maximum", "Tối đa", 1), ("Minimum", "Tối thiểu", 1), ("Sum", "Tổng", 1)],
    "sum_sheets": [("Sum (A1:A3)", "Tổng (A1:A3)", 0.95), ("Sheet1", "Trang 1", 0.9), ("Sheet2", "Trang 2", 0.9)],
    "toolbarmode": [("File", "Tập tin", 0.7), ("Edit", "Sửa", 0.8), ("View", "Xem", 0.8), ("Styles", "Kiểu", 1),
                    ("Home", "Trang đầu", 0.62), ("Inser", "Chèn", 0.8), ("Cut", "Cắt", 1), ("Copy", "Chép", 1),
                    ("Paste", "Dán", 1)],
}
# Second line of remove_hyperlink ("Remove / Hyperlink" -> "Bỏ siêu / liên kết"): only the tspan without own font.
SECOND_LINE = {"remove_hyperlink": ("Hyperlink", "liên kết")}
CALC_ICON = re.compile(r'<g fill-rule="evenodd" stroke-linecap="square" transform="matrix\(\.52916666 0 0 \.52916666 25\.4 24\.341667\)">.*?</g>', re.S)
OVERLAYS = {"w": "hst-writer-64.png", "c": "hst-sheets-64.png", "i": "hst-slides-64.png", "d": "hst-draw-64.png"}


def png_data_uri(path, size):
    image = Image.open(path).convert("RGBA").resize((size, size), Image.LANCZOS)
    buffer = io.BytesIO()
    image.save(buffer, "PNG", optimize=True)
    return "data:image/png;base64," + base64.b64encode(buffer.getvalue()).decode("ascii")


def localise(name, svg):
    if name in SECOND_LINE:  # before TEXT: the same English word is also the bold title
        english, vietnamese = SECOND_LINE[name]
        svg = re.sub(r'(<tspan x="[\d.]+" y="[\d.]+">)' + re.escape(english) + "(</tspan>)", r"\g<1>" + vietnamese + r"\2", svg)
    for english, vietnamese, scale in TEXT[name]:
        pattern = re.compile(r"(<tspan[^>]*>)" + re.escape(english) + r"(</tspan>)")
        if not pattern.search(svg):
            raise SystemExit("%s.svg: no text %r (upstream changed?)" % (name, english))

        def swap(match):
            tag = match.group(1)
            size = re.search(r'font-size="([\d.]+)"', tag)
            if size and scale != 1:
                tag = tag.replace(size.group(0), 'font-size="%.5f"' % (float(size.group(1)) * scale))
            elif scale != 1:
                tag = tag[:-1] + ' style="font-size:%.0f%%">' % (scale * 100)
            return tag + vietnamese + "</tspan>"
        svg = pattern.sub(swap, svg)
    return svg.replace('font-family="Inter"', 'font-family="%s"' % FONT)


def swap_calc_icon(svg):
    icon = os.path.join(ROOT, "assets", "brand", "icons", "hst-sheets-64.png")
    replacement = '<image x="25.4" y="24.341667" width="12.7" height="12.7" xlink:href="%s"/>' % png_data_uri(icon, 96)
    svg, count = CALC_ICON.subn(replacement, svg)
    if count != 1:
        raise SystemExit("fraction.svg: upstream Calc icon not found")
    return svg


def render(svg_path, png_path, width, height):
    subprocess.run(["rsvg-convert", "-w", str(width), "-h", str(height), "-o", png_path, svg_path], check=True)
    Image.open(png_path).save(png_path, optimize=True)


def overlays(tree, out):
    """Each theme's bulb with the HST application icon in the lower right corner (upstream draws its own app
    icons there). Written to <out>/icon-themes/<theme>/tipoftheday_<w|c|i|d>.png."""
    icons = {}
    for key, icon_name in OVERLAYS.items():
        icon_path = os.path.join(ROOT, "assets", "brand", "icons", icon_name)
        if not os.path.isfile(icon_path):
            raise SystemExit("missing %s" % icon_path)
        icons[key] = Image.open(icon_path).convert("RGBA").resize((50, 50), Image.LANCZOS)
    for bulb_path in sorted(glob.glob(os.path.join(tree, "icon-themes", "*", "res", "tipoftheday.png"))):
        theme = bulb_path.split(os.sep)[-3]
        bulb = Image.open(bulb_path).convert("RGBA")
        os.makedirs(os.path.join(out, "icon-themes", theme), exist_ok=True)
        for key, icon in icons.items():
            canvas = bulb.copy()
            canvas.alpha_composite(icon, (bulb.width - 50 - 4, bulb.height - 50 - 4))
            target = os.path.join(out, "icon-themes", theme, "tipoftheday_%s.png" % key)
            canvas.save(target, optimize=True)
            svg_theme = os.path.join(tree, "icon-themes", theme + "_svg", "res", "tipoftheday_%s.svg" % key)
            if os.path.isfile(svg_theme):  # SVG icon themes: the same picture as an embedded PNG
                os.makedirs(os.path.join(out, "icon-themes", theme + "_svg"), exist_ok=True)
                data = base64.b64encode(open(target, "rb").read()).decode("ascii")
                with open(os.path.join(out, "icon-themes", theme + "_svg", "tipoftheday_%s.svg" % key), "w") as handle:
                    handle.write('<svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink" '
                                 'width="%d" height="%d"><image width="%d" height="%d" xlink:href="data:image/png;base64,%s"/></svg>\n'
                                 % (bulb.width, bulb.height, bulb.width, bulb.height, data))


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--tree", default=os.path.join(ROOT, "upstream", "libreoffice"))
    ap.add_argument("--out", default=os.path.join(ROOT, "l10n", "vi-tipoftheday"))
    args = ap.parse_args()
    src = os.path.join(args.tree, "extras", "source", "tipoftheday")
    os.makedirs(args.out, exist_ok=True)
    for name in sorted(TEXT):
        svg = open(os.path.join(src, name + ".svg"), encoding="utf-8").read()
        upstream_png = Image.open(os.path.join(src, name + ".png"))
        svg = localise(name, svg)
        if name == "fraction":
            svg = swap_calc_icon(svg)
        svg_out = os.path.join(args.out, name + ".svg")
        with open(svg_out, "w", encoding="utf-8") as handle:
            handle.write(svg)
        render(svg_out, os.path.join(args.out, name + ".png"), *upstream_png.size)
        print("built %s.png %dx%d" % (name, *upstream_png.size))
    overlays(args.tree, args.out)
    print("built tipoftheday_{%s}.png" % ",".join(OVERLAYS))
    return 0


if __name__ == "__main__":
    sys.exit(main())
