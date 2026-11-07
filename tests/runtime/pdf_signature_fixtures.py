# SPDX-License-Identifier: AGPL-3.0-only
"""Signed PDFs for the signature-reason check, signed by pyHanko with a throw-away key: valid,
encrypted, three signatures in a row, then copies changed the way real files get broken (an update
after signing, rewrites, a truncated copy, a changed byte, a damaged CMS). Needs
python3-cryptography and pyHanko. Nothing is downloaded and no key leaves the work folder."""
import os
import random
import re
import shutil
import tempfile

# name -> (signature valid, problem that HST PDF reports: "" when valid)
SIGNATURE_FIXTURES = {
    "valid": (True, ""),
    "valid-encrypted": (True, ""),
    "valid-chain": (True, ""),  # three signatures, each appended as an incremental update
    "incremental-tamper": (False, "modified"),
    "rewritten-watermark": (False, "rewritten"),
    "range-past-eof": (False, "rewritten"),
    "truncated": (False, "incomplete"),
    "content-changed": (False, "content"),
    "broken-cms": (False, "broken"),
}
SIGNER_CN = "Nguyễn Văn Thử"


def _throwaway_signer(work):
    """A fresh self-signed RSA key and certificate (PEM files in `work`), for pyHanko."""
    import datetime
    from cryptography import x509
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import rsa
    from cryptography.x509.oid import NameOID
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, SIGNER_CN),
                      x509.NameAttribute(NameOID.ORGANIZATION_NAME, "HST Office kiểm thử")])
    now = datetime.datetime.now(datetime.timezone.utc)
    cert = (x509.CertificateBuilder().subject_name(name).issuer_name(name).public_key(key.public_key())
            .serial_number(x509.random_serial_number()).not_valid_before(now - datetime.timedelta(days=1))
            .not_valid_after(now + datetime.timedelta(days=30))
            .add_extension(x509.KeyUsage(True, True, False, False, False, False, False, False, False), True)
            .sign(key, hashes.SHA256()))
    key_pem, cert_pem = os.path.join(work, "throwaway-key.pem"), os.path.join(work, "throwaway-cert.pem")
    with open(key_pem, "wb") as handle:
        handle.write(key.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8,
                                       serialization.NoEncryption()))
    with open(cert_pem, "wb") as handle:
        handle.write(cert.public_bytes(serialization.Encoding.PEM))
    from pyhanko.sign import signers
    return signers.SimpleSigner.load(key_pem, cert_pem)


def _sign(signer, src, target, password=None, field="ChuKy1"):
    from pyhanko.pdf_utils.incremental_writer import IncrementalPdfFileWriter
    from pyhanko.sign import signers
    with open(src, "rb") as inf:
        writer = IncrementalPdfFileWriter(inf)
        if password is not None:
            writer.encrypt(password)
        meta = signers.PdfSignatureMetadata(field_name=field, reason="Kiểm thử ký số", location="Đà Nẵng")
        with open(target, "wb") as outf:
            signers.sign_pdf(writer, meta, signer=signer, output=outf)


def _add_page_content(writer, page_ref, data, font=False, gstate=None):
    """Append a content stream to a page; optional Helvetica /HSTF1 and a /HSTGS1 graphics state."""
    from pyhanko.pdf_utils import generic
    page = page_ref.get_object()
    if "/Resources" not in page:
        page["/Resources"] = generic.DictionaryObject()
    resources = page["/Resources"].get_object()
    if font:
        fonts = resources.setdefault("/Font", generic.DictionaryObject()).get_object()
        fonts["/HSTF1"] = writer.add_object(generic.DictionaryObject({
            generic.NameObject("/Type"): generic.NameObject("/Font"),
            generic.NameObject("/Subtype"): generic.NameObject("/Type1"),
            generic.NameObject("/BaseFont"): generic.NameObject("/Helvetica")}))
    if gstate is not None:
        states = resources.setdefault("/ExtGState", generic.DictionaryObject()).get_object()
        states["/HSTGS1"] = writer.add_object(generic.DictionaryObject({
            generic.NameObject("/Type"): generic.NameObject("/ExtGState"),
            generic.NameObject("/ca"): generic.FloatObject(gstate)}))
    stream = writer.add_object(generic.StreamObject(stream_data=data))
    contents = page.get("/Contents")
    if contents is None:
        page["/Contents"] = stream
    else:
        existing = contents.get_object()
        array = generic.ArrayObject(existing) if isinstance(existing, generic.ArrayObject) else generic.ArrayObject([contents])
        array.append(stream)
        page["/Contents"] = array
    writer.update_container(page)


def _first_page(writer):
    return writer.root["/Pages"].get_object()["/Kids"][0]


def _signed_range_end(path):
    data = open(path, "rb").read()
    match = re.search(rb"/ByteRange\s*\[\s*(\d+)\s+(\d+)\s+(\d+)\s+(\d+)\s*\]", data)
    if not match:
        raise RuntimeError("no /ByteRange in %s" % path)
    values = [int(v) for v in match.groups()]
    return data, values


def make_signature_fixtures(src_pdf, outdir):
    """Writes the SIGNATURE_FIXTURES files (name.pdf) into outdir; returns {name: path}."""
    from pyhanko.pdf_utils import writer as pdf_writer
    from pyhanko.pdf_utils.incremental_writer import IncrementalPdfFileWriter
    from pyhanko.pdf_utils.reader import PdfFileReader
    outdir = os.path.abspath(outdir)
    os.makedirs(outdir, exist_ok=True)
    work = tempfile.mkdtemp(prefix="hstpdf-sigfix-")
    paths = {name: os.path.join(outdir, name + ".pdf") for name in SIGNATURE_FIXTURES}
    try:
        signer = _throwaway_signer(work)
        _sign(signer, src_pdf, paths["valid"])
        chain = os.path.join(work, "chain2.pdf")
        _sign(signer, paths["valid"], chain, field="ChuKy2")
        _sign(signer, chain, paths["valid-chain"], field="ChuKy3")

        # owner password only, like the e-office files; then signed incrementally
        with open(src_pdf, "rb") as inf:
            enc = pdf_writer.copy_into_new_writer(PdfFileReader(inf))
            enc.encrypt("hst-owner-pass", "")
            encrypted = os.path.join(work, "encrypted.pdf")
            with open(encrypted, "wb") as outf:
                enc.write(outf)
        _sign(signer, encrypted, paths["valid-encrypted"], password="hst-owner-pass")

        # an update appended after signing that draws on page 1
        with open(paths["valid"], "rb") as inf:
            inc = IncrementalPdfFileWriter(inf)
            _add_page_content(inc, _first_page(inc), b"q 1 0 0 rg 60 60 200 80 re f Q")
            with open(paths["incremental-tamper"], "wb") as outf:
                inc.write(outf)

        # a document system adds a per-download watermark and writes the whole file again; the
        # stale /ByteRange then points into other objects (with extra data the file stays longer
        # than the signed range, as in files that also carry the system's own data)
        from pyhanko.pdf_utils import generic

        def rewrite(src, target, extra=b""):
            with open(src, "rb") as inf:
                new = pdf_writer.copy_into_new_writer(PdfFileReader(inf))
                page = _first_page(new)
                _add_page_content(new, page,
                                  b"q /HSTGS1 gs 0 0 0 rg BT /HSTF1 22 Tf 0.7071 0.7071 -0.7071 0.7071 150 300 Tm "
                                  b"(thaint - 20/10/2026 15:48:24) Tj ET Q", font=True, gstate=0.1)
                if extra:
                    page.get_object()["/HSTDownloadData"] = new.add_object(generic.StreamObject(stream_data=extra))
                    new.update_container(page.get_object())
                with open(target, "wb") as outf:
                    new.write(outf)
        rewrite(paths["valid"], paths["rewritten-watermark"], extra=random.Random(5).randbytes(40000))
        _data, values = _signed_range_end(paths["rewritten-watermark"])
        if values[2] + values[3] > os.path.getsize(paths["rewritten-watermark"]):
            raise RuntimeError("rewritten-watermark: the file is shorter than the signed range")

        # signed with a large unused object that the rewrite drops: the signed range then ends
        # past the end of the rewritten file
        padded, padded_signed = os.path.join(work, "padded.pdf"), os.path.join(work, "padded-signed.pdf")
        with open(src_pdf, "rb") as inf:
            pad = IncrementalPdfFileWriter(inf)
            pad.add_object(generic.StreamObject(stream_data=random.Random(3).randbytes(300000)))
            with open(padded, "wb") as outf:
                pad.write(outf)
        _sign(signer, padded, padded_signed)
        rewrite(padded_signed, paths["range-past-eof"])
        _data, values = _signed_range_end(paths["range-past-eof"])
        if values[2] + values[3] <= os.path.getsize(paths["range-past-eof"]):
            raise RuntimeError("range-past-eof: the signed range still fits in the file")

        # a copy that stops before the end of the signed data (a download that did not finish)
        open(paths["truncated"], "wb").write(open(paths["valid"], "rb").read()[:-1])
        # one signed byte changed in place (the version digit of the header)
        data = bytearray(open(paths["valid"], "rb").read())
        if not data.startswith(b"%PDF-1."):
            raise RuntimeError("unexpected header in the signed sample")
        data[7] = ord("6") if data[7] == ord("7") else ord("7")
        open(paths["content-changed"], "wb").write(bytes(data))

        # the CMS is damaged: its DER header in /Contents is overwritten
        data, values = _signed_range_end(paths["valid"])
        data = bytearray(data)
        gap = values[0] + values[1]
        if data[gap:gap + 1] != b"<":
            raise RuntimeError("no hex string between the signed ranges")
        data[gap + 1:gap + 9] = b"00000000"
        open(paths["broken-cms"], "wb").write(bytes(data))
    finally:
        shutil.rmtree(work, ignore_errors=True)
    return paths
