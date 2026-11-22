# SPDX-License-Identifier: AGPL-3.0-only
"""Find the default (Save) button of the "Save Document?" dialog in a screenshot and measure its label.

  save-dialog-measure.py <png> <x> <y> <w> <h> <scale>

x, y, w, h: the dialog window in screen points; scale: image pixels per point. The default button is the
box of the HST accent border (light #1A56C8, dark #8AB4F8) in the dialog's lower half. Prints JSON: the
button's centre in points, its fill (most common interior colour), the label colour (the interior colour
furthest from the fill in contrast) and the WCAG contrast ratio of the two. Crops the dialog next to the png.
"""
import collections
import json
import sys

from PIL import Image

ACCENTS = [(0x1A, 0x56, 0xC8), (0x8A, 0xB4, 0xF8)]


def luminance(c):
    def ch(v):
        f = v / 255.0
        return f / 12.92 if f <= 0.04045 else ((f + 0.055) / 1.055) ** 2.4
    return 0.2126 * ch(c[0]) + 0.7152 * ch(c[1]) + 0.0722 * ch(c[2])


def contrast(a, b):
    la, lb = luminance(a), luminance(b)
    return (max(la, lb) + 0.05) / (min(la, lb) + 0.05)


def main():
    path = sys.argv[1]
    x, y, w, h, scale = (float(v) for v in sys.argv[2:7])
    img = Image.open(path).convert("RGB")
    box = tuple(int(round(v * scale)) for v in (x, y, x + w, y + h))
    dlg = img.crop(box)
    dlg.save(path.replace(".png", "-dialog.png"))
    px = dlg.load()
    hits = [(i, j) for j in range(dlg.height // 2, dlg.height) for i in range(dlg.width)
            if any(sum(abs(px[i, j][k] - a[k]) for k in range(3)) < 45 for a in ACCENTS)]
    if not hits:
        print(json.dumps({"png": path, "error": "no accent border in the dialog"}))
        return
    # the right-most cluster of accent pixels (the default button sits at the right on macOS)
    hits.sort()
    right = hits[-1][0]
    cluster = [p for p in hits if right - p[0] < 260 * scale]
    left = min(p[0] for p in cluster)
    cluster = [p for p in hits if p[0] >= left]
    l, r = left, max(p[0] for p in cluster)
    t, b = min(p[1] for p in cluster), max(p[1] for p in cluster)
    inner = [px[i, j] for j in range(t + 3, b - 2) for i in range(l + 3, r - 2)]
    fill = collections.Counter(inner).most_common(1)[0][0]
    label = max(inner, key=lambda c: contrast(c, fill))
    dlg.crop((max(0, l - 8), max(0, t - 8), min(dlg.width, r + 8), min(dlg.height, b + 8))).save(
        path.replace(".png", "-button.png"))
    print(json.dumps({"png": path, "button_px": [l, t, r, b],
                      "centre_pt": [round(x + (l + r) / 2 / scale), round(y + (t + b) / 2 / scale)],
                      "fill": "#%02X%02X%02X" % fill, "label": "#%02X%02X%02X" % label,
                      "contrast": round(contrast(fill, label), 2)}))


if __name__ == "__main__":
    main()
