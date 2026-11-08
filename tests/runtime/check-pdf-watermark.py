#!/usr/bin/env python3
# SPDX-License-Identifier: AGPL-3.0-only
"""A translucent watermark (e.g. the per-download name a document system adds) stays faint on
every path a user can take in HST Office, measured against a pdftoppm render of the original.

For each PDF (read-only copies under --workdir), on its first page with a translucent watermark:
  viewer           HST PDF's page bitmap (screen and thumbnails)
  recent-thumbnail the Start Center "Recent documents" thumbnail HST PDF stores (page 1 only)
  print            HST PDF → print to file → pdftoppm
  draw             opened in HST Draw, the page exported by Draw
  draw-pdf         HST Draw → export to PDF → pdftoppm
  viewer-signed-*  HST PDF signs a copy (token), then: viewer, draw, pdftoppm of the signed file
  draw-signed-*    HST Draw → export as signed PDF (token), then: viewer, draw, pdftoppm
A path passes when the watermark pixels keep the reference grey (pdf_watermark_metrics) and
are not rendered solid. Crops (reference | candidate) go to --workdir/crops.

Default inputs: a generated sample (Writer text with a /ca 0.1 diagonal watermark, rewritten by
pyHanko like a download system does) and any --pdf given (e.g. the owner's files). Needs an X
display (Xvfb), softhsm2/opensc/libnss3-tools for the signed paths (else they are skipped).
  check-pdf-watermark.py --instdir upstream/libreoffice/instdir --workdir /tmp/wm --display :71 --pdf a.pdf
"""
import argparse
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

os.environ.setdefault("HST_VCLPLUGIN", "gen")  # UITest drives the print, chooser and PIN dialogs
import hst_gui
import pdf_watermark_metrics as metrics
import pdf_watermark_paths as paths
import signature_pki
from usb_token_harness import signing_helpers

DPI = 100


def sample_with_watermark(instdir, workdir):
    """A Writer PDF with the watermark appended the way a document system does (needs pyHanko)."""
    import pdf_samples
    from pdf_signature_fixtures import _add_page_content, _first_page
    from pyhanko.pdf_utils import writer as pdf_writer
    from pyhanko.pdf_utils.reader import PdfFileReader
    source = pdf_samples.make(instdir, workdir / "nguon.pdf", 2)
    target = workdir / "mau-hinh-mo.pdf"
    with open(source, "rb") as inf:
        new = pdf_writer.copy_into_new_writer(PdfFileReader(inf))
        _add_page_content(new, _first_page(new),
                          b"q /HSTGS1 gs 0 0 0 rg BT /HSTF1 28 Tf 0.7071 0.7071 -0.7071 0.7071 120 250 Tm "
                          b"(thaint - 20/10/2026 15:48:24) Tj ET Q", font=True, gstate=0.1)
        with open(target, "wb") as outf:
            new.write(outf)
    return target


def measure_file(office, dialogs, pdf, name, workdir, signing, user_cn):
    out = workdir / name
    out.mkdir(parents=True, exist_ok=True)
    if os.geteuid() == 0:  # soffice runs as the build user and writes its outputs here
        subprocess.run(["chown", "-R", hst_gui.BUILD_USER, str(out)], check=True)
    page, reference = metrics.watermark_page(pdf, DPI, str(out))
    rows = {"page": page}
    if page is None:
        rows["error"] = "no translucent watermark found"
        return rows

    def check(path_name, produce):
        try:
            png = produce(out / (path_name + ".png"))
            rows[path_name] = metrics.measure(reference, png, str(workdir / "crops" / ("%s-%s.png" % (name, path_name))))
        except Exception as error:  # noqa: BLE001 - one path failing must not hide the others
            rows[path_name] = {"faint": False, "error": repr(error)[:300]}

    def three_views(prefix, signed_pdf):
        check(prefix + "-viewer", lambda png: paths.viewer_png(office, signed_pdf, page, DPI, png))
        check(prefix + "-pdftoppm", lambda png: metrics.render(signed_pdf, page, DPI, str(png)[:-4]))
        check(prefix + "-draw", lambda png: draw_page(signed_pdf, png))

    def draw_page(source, png):
        doc = paths.draw_open(office, source)
        try:
            return paths.draw_png(office, doc, page, DPI, png)
        finally:
            doc.close(True)

    check("viewer", lambda png: paths.viewer_png(office, pdf, page, DPI, png))
    if page == 1:  # the thumbnail shows the first page (smaller: measure() scales it up)
        check("recent-thumbnail", lambda png: paths.recent_thumbnail_png(office, pdf, png))
    check("print", lambda png: paths.print_png(office, dialogs, pdf, page, DPI, out / "in", out))
    check("draw", lambda png: draw_page(pdf, png))
    exported = out / "draw-xuat.pdf"

    def draw_export(png):
        doc = paths.draw_open(office, pdf)
        try:
            paths.draw_pdf(office, dialogs, doc, str(exported))
        finally:
            doc.close(True)
        return metrics.render(exported, page, DPI, str(png)[:-4])
    check("draw-pdf", draw_export)
    if signing:
        signed = out / "viewer-da-ky.pdf"
        try:
            paths.viewer_sign(office, dialogs, pdf, str(signed), user_cn)
            three_views("viewer-signed", signed)
        except paths.SigningUnsupported:
            # no signed file is written, so nothing can bake the watermark; the message is accurate
            rows["viewer-signed"] = {"faint": True, "signed": False, "message": "refused, file unchanged"}
        except Exception as error:  # noqa: BLE001
            rows["viewer-signed"] = {"faint": False, "error": repr(error)[:300]}
        draw_signed = out / "draw-da-ky.pdf"
        try:
            # after the viewer's chooser has logged in to the token
            certificate = paths.token_certificate(office, user_cn)
            assert certificate is not None, "no token certificate"
            doc = paths.draw_open(office, pdf)
            try:
                paths.draw_pdf(office, dialogs, doc, str(draw_signed), certificate)
            finally:
                doc.close(True)
            three_views("draw-signed", draw_signed)
        except Exception as error:  # noqa: BLE001
            rows["draw-signed"] = {"faint": False, "error": repr(error)[:300]}
    return rows


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--instdir", default="/opt/hst-office1.0")
    ap.add_argument("--workdir", type=Path, required=True)
    ap.add_argument("--display", default=":97")
    ap.add_argument("--port", type=int, default=2097)
    ap.add_argument("--pdf", action="append", default=[], help="also check a read-only copy of this PDF")
    ap.add_argument("--no-signing", action="store_true")
    args = ap.parse_args()
    workdir = args.workdir.resolve()
    shutil.rmtree(workdir, ignore_errors=True)
    workdir.mkdir(parents=True)
    hst_gui.setup_uno(args.instdir)
    inputs = {}
    try:
        inputs["mau"] = sample_with_watermark(args.instdir, workdir)
    except ImportError:
        print("SKIP generated sample: pyHanko is not installed")
    for number, pdf in enumerate(args.pdf, 1):
        copy = workdir / ("pdf-%d.pdf" % number)
        shutil.copyfile(pdf, copy)
        os.chmod(copy, 0o444)
        inputs["pdf-%d" % number] = copy
    config = [("/org.openoffice.Office.Common/Misc", "DocumentTabs", "false")]
    env = {"TZ": "Asia/Ho_Chi_Minh", "DBUS_SESSION_BUS_ADDRESS": "unix:path=/nonexistent-hst-test-bus"}
    pki = None
    if not args.no_signing and not signature_pki.missing_tools():
        pki = signature_pki.TokenPki(str(workdir / "pki")).create()
        config.append(("/org.openoffice.Office.Common/Security/Scripting", "CertDir", pki.nssdb))
        env["SOFTHSM2_CONF"] = pki.conf
    if os.geteuid() == 0:
        subprocess.run(["chown", "-R", hst_gui.BUILD_USER, str(workdir)], check=True)
    signing = signing_helpers()
    office = hst_gui.Office(args.instdir, str(workdir / "office"), args.port, display=args.display,
                            config=config, env=env)
    stop = signing.start_office(office)
    results = {}
    try:
        dialogs = signing.Dialogs(office, str(workdir / "shots"), [signature_pki.USER_PIN] * 6)
        for name, pdf in inputs.items():
            results[name] = measure_file(office, dialogs, str(pdf), name, workdir, pki is not None,
                                         signature_pki.USER_CN)
    finally:
        stop.set()
        office.stop()
        (workdir / "results.json").write_text(json.dumps(results, ensure_ascii=False, indent=1) + "\n")
    failures = []
    for name, rows in results.items():
        for path_name, row in rows.items():
            if isinstance(row, dict):
                print("%-6s %-26s %s" % (name, path_name, json.dumps(row, ensure_ascii=False)))
                if not row.get("faint"):
                    failures.append("%s %s" % (name, path_name))
        if rows.get("error"):
            failures.append("%s: %s" % (name, rows["error"]))
    print("FAIL: " + ", ".join(failures) if failures else "OK: the watermark stays faint on every path")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
