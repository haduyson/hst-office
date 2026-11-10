# SPDX-License-Identifier: AGPL-3.0-only
"""Text selection in HST PDF, shared by the Linux and the Windows checks: a synthetic text page and the screen measure.

sample() is a one-page PDF made by this code alone (base-14 Helvetica, black text lines from the top of the page to
the bottom), so a drag anywhere over the middle of the page view selects text. measure() compares two screenshots of
the same view, before and after the drag, as rows of luma (png_luma.read): the pixels the selection changed are the
highlight; the glyph pixels (dark before) under it must stay much darker than the highlight around them. A highlight
that hides the text (Windows with Skia before the fix: (20, 46, 83) bars, glyphs and background alike) fails, and so
does a selection that changed nothing.
"""
LINE = b"Kiem thu boi den van ban: chu duoc chon van phai doc duoc tren nen xanh nhat. 0123456789"
HIGHLIGHT_MIN = 150  # luma of the highlight over white paper; the intended light blue is about 205, the bug 42
GLYPH_MARGIN = 80  # selected glyphs at least this much darker than the highlight around them
MIN_GLYPH_PIXELS = 200


def _stream(data):
    return b"<< /Length %d >>\nstream\n" % len(data) + data + b"\nendstream"


def sample():
    """The PDF file as bytes: A4, 13 pt text lines every 18 pt from y=800 down to y=50."""
    lines = [b"BT /F1 13 Tf 1 0 0 1 50 %d Tm (%s %d) Tj ET" % (y, LINE, n) for n, y in enumerate(range(800, 40, -18))]
    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595.32 842.04] /Contents 4 0 R"
        b" /Resources << /Font << /F1 5 0 R >> >> >>",
        _stream(b"\n".join(lines)),
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica /Encoding /WinAnsiEncoding >>",
    ]
    out, offsets = bytearray(b"%PDF-1.7\n%\xe2\xe3\xcf\xd3\n"), []
    for number, body in enumerate(objects, 1):
        offsets.append(len(out))
        out += b"%d 0 obj\n" % number + body + b"\nendobj\n"
    xref = len(out)
    out += b"xref\n0 %d\n0000000000 65535 f \n" % (len(objects) + 1)
    out += b"".join(b"%010d 00000 n \n" % offset for offset in offsets)
    out += b"trailer\n<< /Size %d /Root 1 0 R >>\nstartxref\n%d\n%%%%EOF\n" % (len(objects) + 1, xref)
    return bytes(out)


def write(path):
    with open(path, "wb") as handle:
        handle.write(sample())
    return path


def _median(values):
    values = sorted(values)
    return values[len(values) // 2] if values else None


def measure(before, after, box):
    """Selection highlight in `box` (left, top, right, bottom screen pixels) of two luma screenshots.

    Returns {"highlight": median luma of paper pixels the selection tinted, "glyphs": median luma of the glyph pixels
    under the highlight, "tinted": count, "glyph_pixels": count, "readable": bool}."""
    left, top, right, bottom = box
    tinted, glyphs = [], []
    for y in range(top, bottom):
        row_b, row_a = before[y], after[y]
        changed = [row_b[x] > 225 and row_a[x] < row_b[x] - 15 for x in range(left, right)]
        for i, x in enumerate(range(left, right)):
            if changed[i]:
                tinted.append(row_a[x])
            elif row_b[x] < 90 and any(changed[max(0, i - 4):i + 5]):
                glyphs.append(row_a[x])  # ink before, next to tinted paper on the same row: a selected glyph
    highlight, glyph = _median(tinted), _median(glyphs)
    readable = (highlight is not None and glyph is not None and len(glyphs) >= MIN_GLYPH_PIXELS
                and highlight >= HIGHLIGHT_MIN and glyph <= highlight - GLYPH_MARGIN)
    return {"highlight": highlight, "glyphs": glyph, "tinted": len(tinted), "glyph_pixels": len(glyphs),
            "readable": readable}
