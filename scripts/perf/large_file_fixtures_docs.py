# SPDX-License-Identifier: AGPL-3.0-only
"""Pictures, .docx, .pptx and .pdf fixtures of scripts/perf/large_file_fixtures.py (Pillow, python-docx, python-pptx)."""
import io
import random

from large_file_fixture_words import sentence


def noise_jpeg(rnd, w, h, quality=85):
    from PIL import Image, ImageFilter
    img = Image.frombytes("RGB", (w // 4, h // 4), rnd.randbytes((w // 4) * (h // 4) * 3))
    img = img.resize((w, h), Image.BILINEAR).filter(ImageFilter.GaussianBlur(1))
    buf = io.BytesIO()
    img.save(buf, "JPEG", quality=quality)
    return buf.getvalue()


def write_docx(path, pages, images):
    import docx
    from docx.shared import Cm
    rnd = random.Random(11)
    doc = docx.Document()
    pics = [noise_jpeg(rnd, 1800, 1200, 80) for _ in range(8)] if images else []
    for p in range(pages):
        doc.add_heading("Mục %d. %s" % (p + 1, sentence(rnd, 4)), level=1 + p % 2)
        if images:
            doc.add_picture(io.BytesIO(rnd.choice(pics) + rnd.randbytes(64)), width=Cm(15))
            doc.add_paragraph(sentence(rnd, 30))
            doc.add_page_break()
            continue
        for _ in range(5):
            doc.add_paragraph(sentence(rnd, 60))
        if p % 4 == 0:
            t = doc.add_table(rows=8, cols=5)
            t.style = "Table Grid"
            for row in t.rows:
                for cell in row.cells:
                    cell.text = sentence(rnd, 2)
    doc.save(path)


def write_pptx(path, slides):
    from pptx import Presentation
    from pptx.util import Inches
    rnd = random.Random(13)
    prs = Presentation()
    prs.slide_width, prs.slide_height = Inches(13.333), Inches(7.5)
    for i in range(slides):
        slide = prs.slides.add_slide(prs.slide_layouts[5])
        slide.shapes.title.text = "Trang %d: %s" % (i + 1, sentence(rnd, 4))
        slide.shapes.add_picture(io.BytesIO(noise_jpeg(rnd, 2400, 1400, 80)), Inches(1), Inches(1.5), width=Inches(11))
    prs.save(path)


def write_pdf(path, pages):
    rnd = random.Random(17)
    objs = []  # (number, bytes)

    def obj(body):
        objs.append(body)
        return len(objs)

    font = obj(b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica /Encoding /WinAnsiEncoding >>")
    pics = []
    for _ in range(6):
        jpg = noise_jpeg(rnd, 2000, 1400)
        pics.append(obj(b"<< /Type /XObject /Subtype /Image /Width 2000 /Height 1400 /ColorSpace /DeviceRGB "
                        b"/BitsPerComponent 8 /Filter /DCTDecode /Length %d >>\nstream\n" % len(jpg) + jpg
                        + b"\nendstream"))
    pages_id = len(objs) + 2 * pages + 1  # filled in after the pages
    kids = []
    for p in range(pages):
        lines = [b"BT /F1 10 Tf 50 800 Td 12 TL"]
        for _ in range(55):
            text = sentence(rnd, 12).encode("cp1252", "replace").replace(b"(", b"").replace(b")", b"")
            lines.append(b"(" + text + b") '")
        lines.append(b"ET")
        res = b"/Font << /F1 %d 0 R >>" % font
        if p % 5 == 0:
            pic = rnd.choice(pics)
            lines.append(b"q 495 0 0 346 50 50 cm /Im1 Do Q")
            res += b" /XObject << /Im1 %d 0 R >>" % pic
        stream = b"\n".join(lines)
        content = obj(b"<< /Length %d >>\nstream\n" % len(stream) + stream + b"\nendstream")
        kids.append(obj(b"<< /Type /Page /Parent %d 0 R /MediaBox [0 0 595 842] /Resources << %s >> /Contents %d 0 R >>"
                        % (pages_id, res, content)))
    assert len(objs) + 1 == pages_id
    obj(b"<< /Type /Pages /Count %d /Kids [%s] >>" % (pages, b" ".join(b"%d 0 R" % k for k in kids)))
    root = obj(b"<< /Type /Catalog /Pages %d 0 R >>" % pages_id)
    out = bytearray(b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n")
    offsets = []
    for i, body in enumerate(objs, start=1):
        offsets.append(len(out))
        out += b"%d 0 obj\n" % i + body + b"\nendobj\n"
    xref = len(out)
    out += b"xref\n0 %d\n0000000000 65535 f \n" % (len(objs) + 1)
    out += b"".join(b"%010d 00000 n \n" % o for o in offsets)
    out += b"trailer\n<< /Size %d /Root %d 0 R >>\nstartxref\n%d\n%%%%EOF\n" % (len(objs) + 1, root, xref)
    with open(path, "wb") as f:
        f.write(out)
