# SPDX-License-Identifier: AGPL-3.0-only
"""Red-stamp sample PDFs for the HST PDF colour check, made locally (PIL and HST Office).

The workflows users have: a .docx with pure red text, a photo-like scanned JPG stamp and a PNG
stamp with alpha (one per page), exported to PDF by HST Office, and a fully scanned page saved as
a one-image PDF the way a scanner does. Nothing is downloaded.
"""
import base64
import os
import random
import shutil
import tempfile

from pdf_samples import convert

PAPER = (246, 242, 230)  # off-white scanned paper
INK = (214, 32, 48)  # typical red stamp ink
# page of each workflow in the .docx export (the scanned page is a PDF of its own)
STAMP_PAGES = {"red-text": 1, "jpg-stamp": 2, "png-stamp": 3}


def _stamp_layer(size, rng):
    """RGBA red stamp: ink where the stamp is, transparent elsewhere, uneven ink density."""
    from PIL import Image, ImageDraw, ImageFilter, ImageFont
    mask = Image.new("L", (size, size), 0)
    draw = ImageDraw.Draw(mask)
    draw.ellipse((8, 8, size - 8, size - 8), outline=255, width=size // 28)
    draw.ellipse((size // 7, size // 7, size - size // 7, size - size // 7), outline=255, width=size // 70)
    draw.regular_polygon((size // 2, size // 2, size // 10), 5, fill=255)
    try:
        font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", size // 14)
    except OSError:
        font = ImageFont.load_default()
    draw.text((size // 2, size * 0.30), "CÔNG TY HST", font=font, anchor="mm", fill=255)
    draw.text((size // 2, size * 0.72), "ĐÀ NẴNG", font=font, anchor="mm", fill=255)
    mask = mask.filter(ImageFilter.GaussianBlur(1.2))
    mask = mask.point(lambda v: int(v * rng.uniform(0.55, 1.0)) if v else 0)  # patchy ink
    layer = Image.new("RGBA", (size, size), INK + (0,))
    layer.putalpha(mask)
    return layer


def _paper(width, height):
    from PIL import Image
    paper = Image.new("RGB", (width, height), PAPER)
    noise = Image.effect_noise((width, height), 6).convert("L")
    return Image.blend(paper, Image.merge("RGB", (noise,) * 3), 0.06)


def _stamp_docx_fodt(jpg, png):
    def frame(name, path, mime):
        data = base64.b64encode(open(path, "rb").read()).decode()
        return ('<text:p text:style-name="PB"><draw:frame draw:name="%s" text:anchor-type="as-char" '
                'svg:width="4.5cm" svg:height="4.5cm"><draw:image draw:mime-type="%s"><office:binary-data>%s'
                '</office:binary-data></draw:image></draw:frame></text:p>' % (name, mime, data))
    return """<?xml version="1.0" encoding="UTF-8"?>
<office:document xmlns:office="urn:oasis:names:tc:opendocument:xmlns:office:1.0"
 xmlns:text="urn:oasis:names:tc:opendocument:xmlns:text:1.0" xmlns:style="urn:oasis:names:tc:opendocument:xmlns:style:1.0"
 xmlns:fo="urn:oasis:names:tc:opendocument:xmlns:xsl-fo-compatible:1.0"
 xmlns:draw="urn:oasis:names:tc:opendocument:xmlns:drawing:1.0"
 xmlns:svg="urn:oasis:names:tc:opendocument:xmlns:svg-compatible:1.0" office:version="1.3"
 office:mimetype="application/vnd.oasis.opendocument.text">
 <office:automatic-styles>
  <style:style style:name="R" style:family="text"><style:text-properties fo:color="#ff0000" fo:font-size="40pt" fo:font-weight="bold"/></style:style>
  <style:style style:name="PB" style:family="paragraph"><style:paragraph-properties fo:break-before="page"/></style:style>
 </office:automatic-styles>
 <office:body><office:text>
  <text:p><text:span text:style-name="R">CHỮ ĐỎ THUẦN</text:span></text:p>
  <text:p><text:span text:style-name="R">ĐÃ PHÊ DUYỆT</text:span></text:p>
  %s%s
 </office:text></office:body></office:document>
""" % (frame("jpg", jpg, "image/jpeg"), frame("png", png, "image/png"))


def make_stamp_workflows(instdir, outdir):
    """{"docx": .docx, "docx_pdf": its PDF export (pages: STAMP_PAGES), "scanned_page": PDF}.
    Reuses existing files."""
    outdir = os.path.abspath(outdir)
    out = {"docx": os.path.join(outdir, "con-dau.docx"), "docx_pdf": os.path.join(outdir, "con-dau.pdf"),
           "scanned_page": os.path.join(outdir, "trang-quet.pdf")}
    if all(os.path.exists(p) for p in out.values()):
        return out
    os.makedirs(outdir, exist_ok=True)
    rng = random.Random(7)
    work = tempfile.mkdtemp(prefix="hstpdf-stamps-")
    try:
        layer = _stamp_layer(600, rng)
        scan = _paper(600, 600)
        scan.paste(layer, (0, 0), layer)
        jpg, png = os.path.join(work, "con-dau-quet.jpg"), os.path.join(work, "con-dau.png")
        scan.save(jpg, quality=88)  # a scanned stamp: no alpha, JPEG noise on paper
        layer.save(png)  # the stamp cut out: alpha channel
        page = _paper(1240, 1754)  # A4 at 150 dpi, grey text lines and the stamp
        from PIL import ImageDraw
        draw = ImageDraw.Draw(page)
        for i in range(30):
            draw.rectangle((150, 200 + i * 38, 1090 - (i % 4) * 90, 214 + i * 38), fill=(60, 60, 60))
        small = layer.resize((420, 420))
        page.paste(small, (700, 1250), small)
        page.save(out["scanned_page"], "PDF", resolution=150.0)  # one DCT image per page, like a scanner
        src = os.path.join(work, "con-dau.fodt")
        with open(src, "w", encoding="utf-8") as handle:
            handle.write(_stamp_docx_fodt(jpg, png))
        docx = convert(instdir, work, src, 'docx:MS Word 2007 XML')
        shutil.copyfile(docx, out["docx"])
        shutil.copyfile(convert(instdir, work, docx, "pdf"), out["docx_pdf"])
    finally:
        shutil.rmtree(work, ignore_errors=True)
    return out


def red_blue_pixels(png):
    """(red, blue): pixels that are clearly red or clearly blue, the same rule as HSTPdfInfo."""
    from PIL import Image
    red = blue = 0
    for r, g, b in Image.open(png).convert("RGB").getdata():
        if r > 140 and r - g > 60 and r - b > 60:
            red += 1
        elif b > 140 and b - r > 60 and b - g > 60:
            blue += 1
    return red, blue
