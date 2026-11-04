#!/usr/bin/env python3
# SPDX-License-Identifier: AGPL-3.0-only
"""HST PDF runtime check: open, render, search, copy, sign with a USB token, verify.

Generates sample PDFs with HST Office itself (6 pages of Vietnamese text, 50 and 300 pages),
opens them as a user would (loadComponentFromURL, visible), and asserts:
  - the PDF opens in HST PDF (not the Draw import), page count, rendered ink, window title;
  - time to first page: under 1.0 s (50 pages) and 1.5 s (300 pages);
  - Vietnamese search ("hợp đồng dịch vụ", case-insensitive) and text selection;
  - signing through the real certificate chooser and PIN prompt with the SoftHSM2 token of
    signature_pki (private key only on the token), a visible signature box, "save a copy"
    (the original stays byte-identical), the viewer validating the signature and pdfsig;
  - Options "Open PDF files in HST PDF" off, hidden loads and "Edit in HST Draw" use Draw.

Run as root or a normal user on an X display (Xvfb), with softhsm2, opensc, libnss3-tools,
openssl and poppler-utils. Example:
  check-pdf-viewer.py --instdir upstream/libreoffice/instdir --workdir /tmp/pdfv --display :71
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import threading
import time

os.environ.setdefault("HST_VCLPLUGIN", "gen")  # UITest drives the chooser and PIN dialogs
import hst_gui
import pdf_samples
import signature_pki
from usb_token_harness import signing_helpers

ROOT = Path(__file__).resolve().parents[2]
OPEN_LIMIT_MS = {50: 1000, 300: 1500}
VIEWER = "org.hasontech.comp.PdfViewerController"


def info(office, frame, **args):
    result = office.dispatch(frame, ".uno:HSTPdfInfo", signing_props(**args))
    return {item.Name: item.Value for item in result.Result}


def signing_props(**values):
    import uno  # noqa: F401
    from com.sun.star.beans import PropertyValue
    out = []
    for name, value in values.items():
        prop = PropertyValue()
        prop.Name, prop.Value = name, value
        out.append(prop)
    return tuple(out)


def wait_info(office, frame, key, predicate, timeout=30, **args):
    deadline = time.time() + timeout
    while True:
        data = info(office, frame, **args)
        if predicate(data.get(key)) or time.time() > deadline:
            return data
        time.sleep(0.1)


def open_viewer(office, path):
    import uno
    start = time.monotonic()
    component = office.load(uno.systemPathToFileUrl(str(path)))
    wall_ms = int((time.monotonic() - start) * 1000)
    assert component is not None and component.ImplementationName == VIEWER, component
    frame = component.getFrame()
    data = wait_info(office, frame, "OpenMillis", lambda v: v is not None and v >= 0)
    data["WallMillis"] = wall_ms
    return frame, data


def pdfinfo_pages(path):
    out = subprocess.run(["pdfinfo", str(path)], capture_output=True, text=True).stdout
    return int(next(line.split()[-1] for line in out.splitlines() if line.startswith("Pages:")))


def check_viewing(office, samples, checks, result):
    for pages in (6, 50, 300):
        frame, data = open_viewer(office, samples[pages])
        result["open_%d" % pages] = {k: data[k] for k in ("OpenMillis", "WallMillis", "PageCount", "Title")}
        assert data["PageCount"] == pdfinfo_pages(samples[pages]) == pages, data
        assert frame.Title == "%s — HST PDF" % samples[pages].name, frame.Title
        if pages in OPEN_LIMIT_MS:
            assert data["OpenMillis"] < OPEN_LIMIT_MS[pages], data
        if pages == 6:
            ink = info(office, frame, RenderPage=2)["RenderInkPermille"]
            result["render_ink_permille"] = ink
            assert 5 < ink < 400, ink
            count = office.dispatch(frame, ".uno:HSTPdfFind", signing_props(SearchString="hợp đồng dịch vụ")).Result
            # each page: the heading (upper case) and the phrase in five paragraphs
            assert count == 36, count
            office.dispatch(frame, ".uno:HSTPdfFind", signing_props(SearchString="HSTPDF-4"))
            found = info(office, frame)
            assert found["MatchCount"] == 1 and found["MatchPage"] == 4, found
            assert "Kết quả 1/1" in found["StatusText"], found["StatusText"]
            text = office.dispatch(frame, ".uno:HSTPdfSelectText",
                                   signing_props(Page=1, X1=0.0, Y1=0.0, X2=600.0, Y2=200.0)).Result
            assert "HỢP ĐỒNG DỊCH VỤ" in text and "Đà Nẵng" in text, text
            checks["vietnamese_search_and_selection"] = True
        frame.close(True)
        time.sleep(0.5)
    checks["opens_in_viewer_with_page_count_render_title"] = True
    checks["time_to_first_page_under_limits"] = True


def check_signing(office, signing, samples, workdir, pki, checks, result):
    import uno
    source = samples[6]
    before = hashlib.sha256(source.read_bytes()).hexdigest()
    target = workdir / "hop-dong-6-da-ky.pdf"
    target.unlink(missing_ok=True)
    frame, _ = open_viewer(office, source)
    office.dispatch(frame, ".uno:HSTPdfSignPanel", signing_props(Show=True))
    assert info(office, frame)["SignPanelVisible"]
    dialogs = signing.Dialogs(office, str(workdir / "shots"), [signature_pki.USER_PIN])
    # the panel's "Choose Certificate…" opens the document-signing chooser (token login first)
    threading.Thread(target=office.dispatch, args=(frame, ".uno:HSTPdfChooseCertificate"), daemon=True).start()
    chooser, rows = dialogs.certificate_rows(accept_errors=False)
    match = [cid for cid, text in rows if signature_pki.USER_CN in text]
    assert match, rows
    chooser.getChild("signatures").getChild(match[0]).executeAction("SELECT", ())
    dialogs.later(chooser.getChild("ok"))
    data = wait_info(office, frame, "Certificate", lambda v: bool(v))
    assert signature_pki.USER_CN in data["Certificate"], data
    checks["token_certificate_chosen_in_panel"] = True

    done = {}
    def sign():
        done["result"] = office.dispatch(frame, ".uno:HSTPdfSign", signing_props(
            TargetURL=uno.systemPathToFileUrl(str(target)), Reason="Đồng ý phê duyệt", Visible=True,
            Page=1, X=330.0, Y=650.0, Width=200.0, Height=70.0)).Result
    thread = threading.Thread(target=sign, daemon=True)
    thread.start()
    deadline = time.time() + 90
    while thread.is_alive() and time.time() < deadline:
        win, kids = dialogs.top()
        if "newpassEntry" in kids:
            dialogs._answer_pin(win)
        time.sleep(0.5)
    thread.join(5)
    assert done.get("result") is True, (done, dialogs.prompts, dialogs.unexpected)
    assert target.is_file() and hashlib.sha256(source.read_bytes()).hexdigest() == before
    checks["signed_copy_saved_original_unchanged"] = True

    data = wait_info(office, frame, "SignaturesChecked", lambda v: v is True)
    result["viewer_after_signing"] = {k: data[k] for k in ("URL", "SignatureCount", "ValidSignatures", "SignatureStatus", "StatusText")}
    assert data["URL"].endswith(target.name) and data["SignatureCount"] == 1, data
    assert data["ValidSignatures"] == 1 and "1 chữ ký số hợp lệ" in data["SignatureStatus"], data
    checks["viewer_shows_valid_signature"] = True
    frame.close(True)

    verified = signing.signature_verify.verify_pdf(str(target), pki.nssdb, pki.ca_pem)
    result["independent_verification"] = {k: v for k, v in verified.items() if k.endswith("_valid")}
    result["pdfsig"] = verified["pdfsig"]
    assert verified["pdfsig_valid"], verified["pdfsig"]
    assert "Đồng ý phê duyệt" in verified["pdfsig"] or "Signing Reason" not in verified["pdfsig"]
    checks["pdfsig_verifies_signature"] = True

    # the visible signature: ink inside the box on page 1 (y from the top: 650..720 pt)
    png = workdir / "signed-page1"
    subprocess.run(["pdftoppm", "-r", "72", "-png", "-f", "1", "-l", "1", "-x", "330", "-y", "650",
                    "-W", "200", "-H", "70", str(target), str(png)], check=True)
    box = next(workdir.glob("signed-page1*.png"))
    out = subprocess.run(["convert", str(box), "-colorspace", "gray", "-format", "%[fx:mean]", "info:"],
                         capture_output=True, text=True).stdout
    result["signature_box_mean_gray"] = float(out)
    assert float(out) < 0.97, out
    checks["visible_signature_drawn"] = True

    # reopen the signed copy: the viewer validates the signature on load
    frame, _ = open_viewer(office, target)
    data = wait_info(office, frame, "SignaturesChecked", lambda v: v is True)
    assert data["ValidSignatures"] == 1, data
    frame.close(True)
    checks["signed_copy_reopens_valid"] = True


def check_draw_handover(office, samples, checks):
    import uno
    url = uno.systemPathToFileUrl(str(samples[6]))
    hidden = office.load(url, hidden=True)
    assert hidden is not None and hidden.supportsService("com.sun.star.drawing.DrawingDocument"), hidden
    hidden.close(True)
    checks["hidden_load_uses_draw"] = True

    frame, _ = open_viewer(office, samples[6])
    threading.Thread(target=office.dispatch, args=(frame, ".uno:HSTPdfEditInDraw"), daemon=True).start()
    deadline, draw = time.time() + 120, None
    while time.time() < deadline and draw is None:
        time.sleep(1)
        enum = office.desktop().getComponents().createEnumeration()
        while enum.hasMoreElements():
            candidate = enum.nextElement()
            if hasattr(candidate, "supportsService") and candidate.supportsService("com.sun.star.drawing.DrawingDocument"):
                draw = candidate
    assert draw is not None
    time.sleep(2)
    frames = office.desktop().getFrames()
    viewers = [frames.getByIndex(i) for i in range(frames.getCount())
               if getattr(frames.getByIndex(i).getController(), "ImplementationName", "") == VIEWER]
    assert not viewers, "the viewer window stays open after Edit in HST Draw"
    draw.close(True)
    checks["edit_in_draw_replaces_viewer"] = True

    office.set_config("/org.openoffice.Office.HSTPdfViewer/Viewer", "OpenPdfInViewer", False)
    try:
        doc = office.load(url)
        assert doc is not None and doc.supportsService("com.sun.star.drawing.DrawingDocument"), doc
        doc.close(True)
    finally:
        office.set_config("/org.openoffice.Office.HSTPdfViewer/Viewer", "OpenPdfInViewer", True)
    checks["option_off_opens_draw"] = True


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--instdir", default="/opt/hst-office1.0")
    ap.add_argument("--workdir", type=Path, required=True)
    ap.add_argument("--display", default=":97")
    ap.add_argument("--port", type=int, default=2091)
    ap.add_argument("--no-signing", action="store_true", help="skip the token signing part")
    args = ap.parse_args()
    workdir = args.workdir.resolve()
    shutil.rmtree(workdir, ignore_errors=True)
    workdir.mkdir(parents=True)
    hst_gui.setup_uno(args.instdir)
    samples = {n: Path(pdf_samples.make(args.instdir, workdir / "samples" / ("hop-dong-%d.pdf" % n), n))
               for n in (6, 50, 300)}
    pki = None
    config = [("/org.openoffice.Office.Common/Misc", "DocumentTabs", "false")]
    env = {"TZ": "Asia/Ho_Chi_Minh",
           # no session bus on a test display: GTK would wait for dbus-launch on every window
           "DBUS_SESSION_BUS_ADDRESS": "unix:path=/nonexistent-hst-test-bus"}
    if not args.no_signing:
        missing = signature_pki.missing_tools()
        if missing:
            print("SKIP signing: " + ", ".join(missing))
            args.no_signing = True
        else:
            pki = signature_pki.TokenPki(str(workdir / "pki")).create()
            config.append(("/org.openoffice.Office.Common/Security/Scripting", "CertDir", pki.nssdb))
            env["SOFTHSM2_CONF"] = pki.conf
    if os.geteuid() == 0:
        subprocess.run(["chown", "-R", hst_gui.BUILD_USER, str(workdir)], check=True)
    signing = signing_helpers()
    office = hst_gui.Office(args.instdir, str(workdir / "office"), args.port, display=args.display,
                            config=config, env=env)
    checks = {}
    result = {"checks": checks}
    stop = signing.start_office(office)
    try:
        check_viewing(office, samples, checks, result)
        if not args.no_signing:
            check_signing(office, signing, samples, workdir, pki, checks, result)
        check_draw_handover(office, samples, checks)
    finally:
        stop.set()
        office.stop()
        (workdir / "results.json").write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps({k: result[k] for k in result if k.startswith("open_")}, ensure_ascii=False))
    print("PASS: %d checks" % len(checks))
    return 0


if __name__ == "__main__":
    sys.exit(main())
