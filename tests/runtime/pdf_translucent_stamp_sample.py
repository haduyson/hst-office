# SPDX-License-Identifier: AGPL-3.0-only
"""A synthetic one-page PDF shaped like a signed administrative document: a few text lines, two signature widgets
(/FT /Sig with a small appearance) and a diagonal stamp line of black text drawn under an ExtGState with /ca 0.1 on a
page with a transparency group, the way signing software draws its faint "copy" line. Made from nothing but this code
(no real document is used), with the base-14 Helvetica fonts.

The stamp lies alone in the middle band of the page (STAMP_BAND, fractions of the page height), so a renderer that
honours /ca draws it faint there and one that drops it draws it black.
"""
STAMP_BAND = (0.30, 0.70)  # top and bottom of the band holding only the stamp, as fractions of the page height
STAMP_ALPHA = 0.1


def _stream(data):
    return b"<< /Length %d >>\nstream\n" % len(data) + data + b"\nendstream"


def build():
    """The PDF file as bytes."""
    text = [b"BT /F1 13 Tf 1 0 0 1 72 790 Tm (CO QUAN THU NGHIEM HST) Tj ET",
            b"BT /F1 11 Tf 1 0 0 1 72 770 Tm (So: 01/TN-HST) Tj ET",
            b"BT /F2 15 Tf 1 0 0 1 190 735 Tm (VAN BAN MAU DE KIEM THU) Tj ET",
            b"BT /F1 11 Tf 1 0 0 1 72 160 Tm (Noi dung chi dung cho kiem thu tu dong.) Tj ET",
            b"0.737 w 0 G 343.8 755.5 m 497.8 755.5 l S 128.9 753.3 m 208.4 753.3 l S"]
    # the stamp: rotated 54.7 degrees about the page centre, black fill at /ca 0.1 (structure of signing stamps)
    stamp = (b"q /gs1 gs /DeviceRGB cs 0 0 0 sc BT /F1 22 Tf 0.57729 0.81654 -0.81654 0.57729 297.66 421.02 Tm "
             b"-200 0 Td (BAN SAO DIEN TU - KIEM THU - KHONG CO GIA TRI) Tj ET Q")
    content = b"\n".join(text + [stamp])
    appearance = b"q 0 0 1 RG 1 w 1 1 36 13 re S Q"
    objects = [
        b"<< /Type /Catalog /Pages 2 0 R /AcroForm << /Fields [6 0 R 8 0 R] /SigFlags 3 >> >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595.32 842.04] /Contents 4 0 R /Annots [6 0 R 8 0 R]"
        b" /Group << /Type /Group /S /Transparency /CS /DeviceRGB >> /Tabs /S"
        b" /Resources << /Font << /F1 5 0 R /F2 10 0 R >> /ExtGState << /gs1 << /Type /ExtGState /ca %s >> >> >> >>"
        % (b"%.1f" % STAMP_ALPHA),
        _stream(content),
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica /Encoding /WinAnsiEncoding >>",
        b"<< /Type /Annot /Subtype /Widget /FT /Sig /T (Signature1) /F 132 /Rect [118 734 156 749] /P 3 0 R"
        b" /AP << /N 7 0 R >> >>",
        b"<< /Type /XObject /Subtype /Form /BBox [0 0 38 15] /Length %d >>\nstream\n" % len(appearance) + appearance
        + b"\nendstream",
        b"<< /Type /Annot /Subtype /Widget /FT /Sig /T (Signature2) /F 132 /Rect [393 734 417 749] /P 3 0 R"
        b" /AP << /N 9 0 R >> >>",
        b"<< /Type /XObject /Subtype /Form /BBox [0 0 24 15] /Length %d >>\nstream\n" % len(appearance) + appearance
        + b"\nendstream",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica-Bold /Encoding /WinAnsiEncoding >>",
    ]
    out = bytearray(b"%PDF-1.7\n%\xe2\xe3\xcf\xd3\n")
    offsets = []
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
        handle.write(build())
    return path
