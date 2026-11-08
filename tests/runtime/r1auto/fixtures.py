# SPDX-License-Identifier: AGPL-3.0-only
"""Only synthetic PDF inputs; reuse stamp, signature and restricted-permission generators."""
from pathlib import Path
import random
import sys
import tempfile

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


def generate(out):
    import pikepdf as p
    from PIL import Image
    from pdf_stamp_samples import _stamp_layer
    from pdf_signature_fixtures import make_signature_fixtures
    from pdf_encrypted_samples import make
    out = Path(out)
    out.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="r1-pdf-") as private:
        private = Path(private)
        stamp = Image.new("RGB", (300, 300), "white")
        layer = _stamp_layer(300, random.Random(7))
        stamp.paste(layer, mask=layer.getchannel("A"))
        pdf = p.new()
        page = pdf.add_blank_page(page_size=(595, 842))
        image = pdf.make_stream(stamp.tobytes())
        image.Type, image.Subtype = p.Name.XObject, p.Name.Image
        image.Width, image.Height = stamp.size
        image.ColorSpace, image.BitsPerComponent = p.Name.DeviceRGB, 8
        font = pdf.make_indirect(p.Dictionary(Type=p.Name.Font, Subtype=p.Name.Type1, BaseFont=p.Name.Helvetica))
        page.obj.Resources = p.Dictionary(Font=p.Dictionary(F1=font), XObject=p.Dictionary(Stamp=image))
        # Dark text over the image exercises draw/import paint order independently of faintness.
        page.obj.Contents = pdf.make_stream(b"q 150 0 0 150 340 100 cm /Stamp Do Q\n"
                                       b"BT /F1 20 Tf 60 760 Td (HST - Tai lieu kiem thu tong hop) Tj ET\n"
                                       b"BT /F1 12 Tf 340 172 Td (CHU TREN HINH - HST) Tj ET\n")
        base = private / "base.pdf"
        pdf.save(base)
        generated = make_signature_fixtures(str(base), str(private / "signed"))
        (out / "signed-watermark.pdf").write_bytes(Path(generated["rewritten-watermark"]).read_bytes())
        # make_signature_fixtures adds /ca 0.1 and a real signature, then rewrites it.
        make("perm-none", out / "restricted.pdf")
    return out


if __name__ == "__main__":
    generate(sys.argv[1])
