# SPDX-License-Identifier: AGPL-3.0-only
"""Encrypted PDFs as document systems write them, for the signing tests (needs pikepdf/qpdf).

Each sample is one page of text with an Info title, a catalog /Lang and, for the permission
cases, an empty signature field ("KyTen") the sender prepared. Owner password "chu", user
password "mo" for the "user-password" sample only. Kinds:
  aes128-objstm  AES-128 (R4), objects in object streams, xref stream (like iText downloads)
  aes256         AES-256 (R6), object streams
  rc4-128        RC4 128 bit (R3), classic xref table
  rc4-40         RC4 40 bit (R2)
  perm-<bits>    AES-128 with only these of bits 4 (modify), 6 (annotations), 9 (fill forms):
                 perm-4-6, perm-6, perm-9, perm-4, perm-none
  locked-<cipher>  rc4-40, rc4-128 or aes256 with no permission, for the owner password
  user-password  AES-256 that needs the user password to open
The CppUnit fixtures of the signing patch are these files in base64:
  python3 pdf_encrypted_samples.py OUTDIR [--base64]
"""
import base64
import sys
from pathlib import Path

OWNER = "chu"
USER = "mo"
KINDS = ("aes128-objstm", "aes256", "rc4-128", "rc4-40", "perm-4-6", "perm-6", "perm-9",
         "perm-4", "perm-none", "locked-rc4-40", "locked-rc4-128", "locked-aes256",
         "user-password")


def _pikepdf():
    import pikepdf
    return pikepdf


def _document(pikepdf, with_field):
    pdf = pikepdf.new()
    pdf.add_blank_page(page_size=(595, 842))
    page = pdf.pages[0]
    font = pdf.make_indirect(pikepdf.Dictionary(Type=pikepdf.Name.Font, Subtype=pikepdf.Name.Type1,
                                                BaseFont=pikepdf.Name.Helvetica))
    page.obj.Resources = pikepdf.Dictionary(Font=pikepdf.Dictionary(F1=font))
    page.obj.Contents = pdf.make_stream(b"BT /F1 18 Tf 72 760 Td (Cong van ma hoa - HST) Tj ET\n"
                                        b"0 0 0.8 rg 72 600 200 60 re f\n")
    pdf.Root.Lang = pikepdf.String("vi-VN")
    pdf.docinfo.Title = pikepdf.String("Mẫu mã hóa")
    if with_field:
        widget = pdf.make_indirect(pikepdf.Dictionary(
            Type=pikepdf.Name.Annot, Subtype=pikepdf.Name.Widget, FT=pikepdf.Name.Sig,
            T=pikepdf.String("KyTen"), F=4, Rect=[360, 80, 540, 140], P=page.obj))
        page.obj.Annots = pdf.make_indirect(pikepdf.Array([widget]))
        pdf.Root.AcroForm = pikepdf.Dictionary(Fields=[widget], DA=pikepdf.String("/Helv 0 Tf 0 g"),
                                               SigFlags=3)
    return pdf


def _permissions(pikepdf, kind):
    if kind.startswith("locked-"):
        return pikepdf.Permissions(accessibility=False, extract=False, modify_annotation=False,
                                   modify_assembly=False, modify_form=False, modify_other=False,
                                   print_lowres=False, print_highres=False)
    if not kind.startswith("perm-"):
        # every permission, spelled out: the R2 default leaves "modify" off
        return pikepdf.Permissions(modify_other=True, modify_annotation=True, modify_form=True,
                                   modify_assembly=True)
    bits = set(kind[len("perm-"):].split("-"))
    return pikepdf.Permissions(modify_other="4" in bits, modify_annotation="6" in bits,
                               modify_form="9" in bits, modify_assembly=False)


def make(kind, target):
    """Writes the sample `kind` to target; returns its path."""
    if kind not in KINDS:
        raise ValueError("unknown sample kind: %s" % kind)
    pikepdf = _pikepdf()
    pdf = _document(pikepdf, kind.startswith(("perm-", "locked-")))
    cipher = kind[len("locked-"):] if kind.startswith("locked-") else kind
    user = USER if kind == "user-password" else ""
    perms = _permissions(pikepdf, kind)
    if cipher in ("aes256", "user-password"):
        encryption = pikepdf.Encryption(owner=OWNER, user=user, R=6, allow=perms)
    elif cipher == "rc4-128":
        encryption = pikepdf.Encryption(owner=OWNER, user=user, R=3, allow=perms,
                                        aes=False, metadata=False)
    elif cipher == "rc4-40":
        encryption = pikepdf.Encryption(owner=OWNER, user=user, R=2, allow=perms,
                                        aes=False, metadata=False)
    else:
        encryption = pikepdf.Encryption(owner=OWNER, user=user, R=4, aes=True, allow=perms)
    streams = pikepdf.ObjectStreamMode.preserve if cipher.startswith("rc4") \
        else pikepdf.ObjectStreamMode.generate
    pdf.save(str(target), encryption=encryption, object_stream_mode=streams)
    return Path(target)


def main(argv):
    if not argv or argv[0].startswith("-"):
        print(__doc__)
        return 2
    out = Path(argv[0])
    out.mkdir(parents=True, exist_ok=True)
    for kind in KINDS:
        path = make(kind, out / ("hst-encrypted-%s.pdf" % kind))
        if "--base64" in argv:
            data = base64.encodebytes(path.read_bytes()).decode("ascii")
            path.with_name(path.name + ".b64").write_text(data)
        print(path)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
