# SPDX-License-Identifier: AGPL-3.0-only
"""Document side of check-digital-signature.py: the test documents, loading them in a window, the signature state
HST shows and its API verification, signed PDF export, the token certificate and a tampered copy."""
import os
import time
import zipfile

import signature_pki
from signature_dialogs import props

FORMATS = (("odt", "swriter", "writer8"), ("docx", "swriter", "MS Word 2007 XML"),
           ("ods", "scalc", "calc8"), ("xlsx", "scalc", "Calc MS Excel 2007 XML"),
           ("odp", "simpress", "impress8"), ("pptx", "simpress", "Impress MS PowerPoint 2007 XML"))
SIGNATURE_STATE = {0: "NOSIGNATURES", 1: "OK", 2: "BROKEN", 3: "INVALID", 4: "NOTVALIDATED", 5: "PARTIAL_OK"}


def load_visible(office, url):
    """loadComponentFromURL can return None right after a signed document was closed (the
    document still opens, e.g. as a tab): find it among the desktop components then."""
    doc = office.load(url)
    deadline = time.time() + 30
    while doc is None and time.time() < deadline:
        time.sleep(1)
        components = office.desktop().getComponents().createEnumeration()
        while components.hasMoreElements():
            candidate = components.nextElement()
            if getattr(candidate, "URL", None) == url or (hasattr(candidate, "getURL") and candidate.getURL() == url):
                doc = candidate
    if doc is not None and not hasattr(doc, "getCurrentController"):
        # not a document model: e.g. the HST PDF viewer's window, opened when OpenPdfInViewer is on
        print("not a document: %s opened %s" % (url, getattr(doc, "ImplementationName", doc)), flush=True)
        try:
            doc.getFrame().close(True)
        except Exception:  # noqa: BLE001 - reported as not loaded either way
            pass
        return None
    return doc


def close_document(doc):
    """Close a document; a dialog left open by a failed step vetoes close(True) (reported)."""
    try:
        doc.close(True)
    except Exception as error:  # noqa: BLE001 - a dialog still open vetoes; never dispose under it
        print("close vetoed: %r" % error, flush=True)


def signature_state(office, frame):
    """What the status bar shows: SID_SIGNATURE state of the frame (SignatureState)."""
    import unohelper
    from com.sun.star.frame import XStatusListener
    from com.sun.star.util import URL

    class Listener(unohelper.Base, XStatusListener):
        state = None

        def statusChanged(self, event):
            Listener.state = event.State

        def disposing(self, _event):
            pass

    url = URL()
    url.Complete = ".uno:Signature"
    _ok, url = office.service("com.sun.star.util.URLTransformer").parseStrict(url)
    dispatch = frame.queryDispatch(url, "", 0)
    listener = Listener()
    dispatch.addStatusListener(listener, url)
    time.sleep(1)
    dispatch.removeStatusListener(listener, url)
    return SIGNATURE_STATE.get(Listener.state, Listener.state)


def hst_verify(office, path):
    """DocumentDigitalSignatures.verifyDocumentContentSignatures of a PDF, as HST shows it."""
    import uno
    dds = office.smgr.createInstanceWithArgumentsAndContext("com.sun.star.security.DocumentDigitalSignatures", ("1.2",), office.ctx)
    stream = office.service("com.sun.star.ucb.SimpleFileAccess").openFileRead(uno.systemPathToFileUrl(path))
    infos = dds.verifyDocumentContentSignatures(None, stream)
    return [{"signer": i.Signer.SubjectName if i.Signer else None, "valid": bool(i.SignatureIsValid),
             "certificate_status": i.CertificateStatus} for i in infos]


def make_documents(office, outdir, early_pdf=True):
    import uno
    paths = {}
    for ext, factory, filt in FORMATS:
        doc = office.load("private:factory/" + factory, hidden=True)
        if factory == "swriter":
            doc.getText().setString("Văn bản kiểm thử ký số bằng USB Token — HST Office.")
        elif factory == "scalc":
            sheet = doc.Sheets.getByIndex(0)
            sheet.getCellByPosition(0, 0).setString("Bảng tính ký số")
            sheet.getCellByPosition(1, 0).setValue(30)
        else:
            page = doc.DrawPages.getByIndex(0)
            shape = doc.createInstance("com.sun.star.drawing.TextShape")
            page.add(shape)
            shape.setString("Trình chiếu ký số")
        paths[ext] = os.path.join(outdir, "test." + ext)
        doc.storeToURL(uno.systemPathToFileUrl(paths[ext]), props(FilterName=filt, Overwrite=True))
        if ext == "odt":
            paths["pdf"] = os.path.join(outdir, "existing.pdf")
            if early_pdf:
                export_pdf(doc, paths["pdf"])
        doc.close(True)
    return paths


def export_pdf(doc, target):
    import uno
    doc.storeToURL(uno.systemPathToFileUrl(target), props(FilterName="writer_pdf_Export", Overwrite=True))


def export_signed_pdf(office, odt, target, certificate, tsa=None):
    import uno
    doc = office.load(uno.systemPathToFileUrl(odt), hidden=True)
    data = props(SignPDF=True, SignatureCertificate=certificate, SignatureReason="Kiểm thử ký số",
                 SignatureLocation="Đà Nẵng", SignatureContactInfo="lienhe@hasontech.vn", **({"SignatureTSA": tsa} if tsa else {}))
    try:
        doc.storeToURL(uno.systemPathToFileUrl(target), props(FilterName="writer_pdf_Export", FilterData=data, Overwrite=True))
    finally:
        doc.close(True)
    return target


def token_certificate(office):
    context = office.service("com.sun.star.xml.crypto.SEInitializer").createSecurityContext("")
    for cert in context.getSecurityEnvironment().getPersonalCertificates():
        if signature_pki.USER_CN in cert.SubjectName:
            return cert
    return None


def tamper(path, target):
    """Copy of a signed ODF file whose content.xml changed after signing."""
    with zipfile.ZipFile(path) as src, zipfile.ZipFile(target, "w") as dst:
        for item in src.infolist():
            data = src.read(item.filename)
            if item.filename == "content.xml":
                data = data.replace("kiểm thử".encode(), "ĐÃ SỬA".encode(), 1)
            dst.writestr(item, data)
    return target
