# SPDX-License-Identifier: AGPL-3.0-only
"""Every way a user can show, print, sign or re-export a PDF in HST Office, each ending in a PNG
of one page at a given resolution, for pdf_watermark_metrics.

- viewer: HST PDF's own page bitmap (.uno:HSTPdfInfo RenderFile; the screen and thumbnails use it);
- print: HST PDF's print dialog, "print to file", then pdftoppm of the printed PDF;
- draw: the PDF opened in HST Draw (hidden loads use Draw), the page exported by Draw's renderer;
- draw_pdf: that Draw document exported to PDF (optionally signed with a certificate);
- viewer_sign: HST PDF signs a copy (visible box in the top-left margin, off the watermark).
"""
import os
import threading
import time

import pdf_watermark_metrics
from pdf_viewer_uno import info, open_viewer, sign_copy, signing_props, wait_info
from pdf_viewer_stamps import print_to_file


def _url(path):
    import uno
    return uno.systemPathToFileUrl(os.path.abspath(str(path)))


def _filter_data(**values):
    import uno
    return uno.Any("[]com.sun.star.beans.PropertyValue", signing_props(**values))


def viewer_png(office, pdf, page, dpi, out):
    frame, _ = open_viewer(office, pdf)
    data = info(office, frame, RenderPage=page, RenderDpi=dpi, RenderFile=_url(out))
    frame.close(True)
    time.sleep(0.5)
    assert data.get("RenderFileWritten") is True, data
    return str(out)


def print_png(office, dialogs, pdf, page, dpi, out_stem, workdir):
    frame, _ = open_viewer(office, pdf)
    printed, _pngs = print_to_file(office, dialogs, frame, out_stem, workdir)
    frame.close(True)
    time.sleep(0.5)
    return pdf_watermark_metrics.render(printed, page, dpi, str(out_stem) + "-render")


def draw_open(office, pdf):
    doc = office.load(_url(pdf), hidden=True)
    assert doc is not None and doc.supportsService("com.sun.star.drawing.DrawingDocument"), doc
    return doc


def draw_png(office, doc, page, dpi, out):
    draw_page = doc.DrawPages.getByIndex(page - 1)
    exporter = office.service("com.sun.star.drawing.GraphicExportFilter")
    exporter.setSourceDocument(draw_page)
    width = round(draw_page.Width / 2540 * dpi)  # 1/100 mm
    height = round(draw_page.Height / 2540 * dpi)
    exporter.filter(signing_props(URL=_url(out), MediaType="image/png",
                                  FilterData=_filter_data(PixelWidth=width, PixelHeight=height)))
    return str(out)


def draw_pdf(office, dialogs, doc, out, certificate=None):
    """Export the Draw document to PDF; with a certificate, signed (token PIN answered)."""
    data = {"SignPDF": True, "SignatureCertificate": certificate,
            "SignatureReason": "Kiểm thử hình mờ"} if certificate is not None else {}
    done = {}

    def export():
        try:
            doc.storeToURL(_url(out), signing_props(FilterName="draw_pdf_Export", Overwrite=True,
                                                    FilterData=_filter_data(**data)))
            done["ok"] = True
        except Exception as error:  # noqa: BLE001 - reported by the caller
            done["error"] = repr(error)
    thread = threading.Thread(target=export, daemon=True)
    thread.start()
    deadline = time.time() + 120
    while thread.is_alive() and time.time() < deadline:
        win, kids = dialogs.top()
        if "newpassEntry" in kids:
            dialogs._answer_pin(win)
        time.sleep(0.5)
    thread.join(5)
    assert done.get("ok") and os.path.exists(out), done
    return str(out)


def choose_viewer_certificate(office, dialogs, frame, user_cn):
    """Choose the token certificate in this HST PDF window's panel (remembered after signing)."""
    threading.Thread(target=office.dispatch, args=(frame, ".uno:HSTPdfChooseCertificate"), daemon=True).start()
    chooser, rows = dialogs.certificate_rows(accept_errors=False)
    match = [cid for cid, text in rows if user_cn in text]
    assert match, rows
    chooser.getChild("signatures").getChild(match[0]).executeAction("SELECT", ())
    dialogs.later(chooser.getChild("ok"))
    data = wait_info(office, frame, "Certificate", lambda v: bool(v))
    assert user_cn in data["Certificate"], data


class SigningUnsupported(Exception):
    """HST PDF does not sign this file and says why: its structure cannot be updated, or the
    sender's permissions forbid signing (the file is left unchanged)."""


def viewer_sign(office, dialogs, pdf, target, user_cn):
    frame, _ = open_viewer(office, pdf)
    office.dispatch(frame, ".uno:HSTPdfSignPanel", signing_props(Show=True))
    if user_cn not in (info(office, frame).get("Certificate") or ""):
        choose_viewer_certificate(office, dialogs, frame, user_cn)
    done = sign_copy(office, dialogs, frame, target, Reason="Kiểm thử hình mờ", Page=1, X=40.0, Y=40.0)
    status = info(office, frame).get("StatusText") or ""
    if done.get("result") is not True:
        win, kids = dialogs.top()  # the error message box, or the permission message
        for button in ("ok", "close"):
            if button in kids:
                dialogs.later(win.getChild(button))
                time.sleep(1)
                break
    frame.close(True)
    if done.get("result") is not True and ("không thêm được chữ ký vào tệp này" in status
                                           or "không cho phép ký số" in status):
        raise SigningUnsupported(status)
    time.sleep(0.5)
    assert done.get("result") is True and os.path.exists(target), (done, dialogs.prompts, dialogs.unexpected)
    return str(target)


def token_certificate(office, user_cn):
    context = office.service("com.sun.star.xml.crypto.SEInitializer").createSecurityContext("")
    for cert in context.getSecurityEnvironment().getPersonalCertificates():
        if user_cn in cert.SubjectName:
            return cert
    return None
