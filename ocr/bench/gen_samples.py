# SPDX-License-Identifier: LicenseRef-HST-Proprietary
"""Render the synthetic OCR benchmark: text pages, formula crops and table crops, each clean and "scanned".

Usage: python3 gen_samples.py OUT_DIR
Writes OUT_DIR/{text,formula,table}/<id>-<variant>.png and OUT_DIR/truth.json. Needs Pillow, numpy and matplotlib.
Variants: clean (300 dpi), scan (300 dpi, 0.6° skew, blur, noise, JPEG 55), low (150 dpi, more blur and noise).
"""
import io
import json
import os
import sys

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from sample_content import FORMULAS, PARAGRAPHS, TABLES  # noqa: E402

FONTS = {"serif": "/usr/share/fonts/truetype/liberation/LiberationSerif-Regular.ttf",
         "dejavu": "/usr/share/fonts/truetype/dejavu/DejaVuSerif.ttf"}
PAGE_W, MARGIN, PT = 2480, 236, 300 / 72  # A4 width at 300 dpi, 2 cm margin


def wrap(draw, text, font, width):
    lines, line = [], ""
    for word in text.split(" "):
        probe = (line + " " + word) if line else word
        if draw.textlength(probe, font=font) <= width or not line:
            line = probe
        else:
            lines.append(line)
            line = word
    return lines + [line]


def render_page(paragraphs, font_path, size_pt):
    font = ImageFont.truetype(font_path, round(size_pt * PT))
    probe = ImageDraw.Draw(Image.new("L", (1, 1)))
    step = round(size_pt * PT * 1.45)
    lines = [ln for p in paragraphs for ln in wrap(probe, p, font, PAGE_W - 2 * MARGIN) + [None]]
    img = Image.new("L", (PAGE_W, 2 * MARGIN + step * len(lines)), 255)
    draw = ImageDraw.Draw(img)
    y = MARGIN
    for ln in lines:
        if ln:
            draw.text((MARGIN, y), ln, font=font, fill=0)
        y += step if ln else step // 2
    return img.crop((0, 0, PAGE_W, y + MARGIN))


def render_formula(latex, dpi=300, size=16):
    import matplotlib
    matplotlib.use("Agg")
    from matplotlib import pyplot as plt
    fig = plt.figure(figsize=(0.01, 0.01))
    fig.text(0, 0, "$%s$" % latex, fontsize=size, math_fontfamily="cm")
    buf = io.BytesIO()
    fig.savefig(buf, dpi=dpi, format="png", bbox_inches="tight", pad_inches=0.12, facecolor="white")
    plt.close(fig)
    return Image.open(io.BytesIO(buf.getvalue())).convert("L")


def render_table(rows, font_path, size_pt=12):
    font = ImageFont.truetype(font_path, round(size_pt * PT))
    probe = ImageDraw.Draw(Image.new("L", (1, 1)))
    pad, h = 28, round(size_pt * PT * 1.9)
    widths = [max(probe.textlength(r[c], font=font) for r in rows) + 2 * pad for c in range(len(rows[0]))]
    w = int(sum(widths)) + 2 * pad
    img = Image.new("L", (w + 2 * pad, h * len(rows) + 4 * pad), 255)
    draw = ImageDraw.Draw(img)
    x0, y0 = 2 * pad, 2 * pad
    for r, row in enumerate(rows):
        x = x0
        for c, text in enumerate(row):
            draw.rectangle((x, y0 + r * h, x + widths[c], y0 + (r + 1) * h), outline=0, width=3)
            draw.text((x + pad, y0 + r * h + h * 0.2), text, font=font, fill=0)
            x += widths[c]
    return img


MIXED_PAGES = [
    ("m1", [("p", PARAGRAPHS[3]), ("f", FORMULAS[8]), ("p", PARAGRAPHS[5]), ("f", FORMULAS[4]), ("t", TABLES[1]),
            ("p", PARAGRAPHS[12])]),
    ("m2", [("p", PARAGRAPHS[2]), ("p", PARAGRAPHS[6]), ("f", FORMULAS[28]), ("t", TABLES[3]), ("p", PARAGRAPHS[7]),
            ("f", FORMULAS[17])]),
]


def render_mixed(layout):
    """A page of paragraphs, centred display formulas and tables: (image, truth blocks in reading order)."""
    font = ImageFont.truetype(FONTS["serif"], round(13 * PT))
    probe = ImageDraw.Draw(Image.new("L", (1, 1)))
    step = round(13 * PT * 1.45)
    parts = []
    for kind, value in layout:
        if kind == "p":
            lines = wrap(probe, value, font, PAGE_W - 2 * MARGIN)
            img = Image.new("L", (PAGE_W - 2 * MARGIN, step * len(lines)), 255)
            draw = ImageDraw.Draw(img)
            for i, ln in enumerate(lines):
                draw.text((0, i * step), ln, font=font, fill=0)
            parts.append((img, False, {"type": "paragraph", "text": value}))
        elif kind == "f":
            parts.append((render_formula(value, size=15), True, {"type": "formula", "latex": value}))
        else:
            parts.append((render_table(value, FONTS["serif"]), True, {"type": "table", "rows": value}))
    height = 2 * MARGIN + sum(p[0].height + step // 2 for p in parts)
    page = Image.new("L", (PAGE_W, height), 255)
    y = MARGIN
    for img, centred, _ in parts:
        x = (PAGE_W - img.width) // 2 if centred else MARGIN
        page.paste(img, (x, y))
        y += img.height + step // 2
    return page, [p[2] for p in parts]


def degrade(img, variant, seed):
    if variant == "clean":
        return img
    rng = np.random.default_rng(seed)
    low = variant == "low"
    if low:
        img = img.resize((img.width // 2, img.height // 2), Image.LANCZOS)
    img = img.rotate(0.6 if not low else -0.9, resample=Image.BICUBIC, expand=True, fillcolor=255)
    img = img.filter(ImageFilter.GaussianBlur(0.9 if not low else 0.8))
    arr = np.asarray(img, dtype=np.float32)
    arr = arr * rng.uniform(0.92, 0.98) + rng.normal(0, 10 if not low else 14, arr.shape) + 6
    img = Image.fromarray(np.clip(arr, 0, 255).astype(np.uint8))
    buf = io.BytesIO()
    img.save(buf, "JPEG", quality=55 if not low else 40)
    return Image.open(io.BytesIO(buf.getvalue())).convert("L")


def main(out):
    truth = {"text": {}, "formula": {}, "table": {}}
    for kind in truth:
        os.makedirs(os.path.join(out, kind), exist_ok=True)
    pages = [("p1-serif13", PARAGRAPHS[:9], "serif", 13), ("p2-serif12", PARAGRAPHS[9:], "serif", 12),
             ("p3-dejavu12", PARAGRAPHS[3:12], "dejavu", 12)]
    variants = ("clean", "scan", "low")
    for n, (pid, paras, font, size) in enumerate(pages):
        page = render_page(paras, FONTS[font], size)
        truth["text"][pid] = "\n".join(paras)
        for v in variants:
            degrade(page, v, n).save(os.path.join(out, "text", "%s-%s.png" % (pid, v)))
    for n, latex in enumerate(FORMULAS):
        fid = "f%02d" % n
        truth["formula"][fid] = latex
        img = render_formula(latex)
        for v in ("clean", "scan"):
            degrade(img, v, 100 + n).save(os.path.join(out, "formula", "%s-%s.png" % (fid, v)))
    for n, rows in enumerate(TABLES):
        tid = "t%02d" % n
        truth["table"][tid] = rows
        img = render_table(rows, FONTS["serif"])
        for v in ("clean", "scan"):
            degrade(img, v, 200 + n).save(os.path.join(out, "table", "%s-%s.png" % (tid, v)))
    os.makedirs(os.path.join(out, "page"), exist_ok=True)
    for n, (pid, layout) in enumerate(MIXED_PAGES):
        page, blocks = render_mixed(layout)
        truth.setdefault("page", {})[pid] = blocks
        for v in ("clean", "scan"):
            degrade(page, v, 300 + n).save(os.path.join(out, "page", "%s-%s.png" % (pid, v)))
    with open(os.path.join(out, "truth.json"), "w", encoding="utf-8") as fh:
        json.dump(truth, fh, ensure_ascii=False, indent=1)


if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    main(sys.argv[1])
