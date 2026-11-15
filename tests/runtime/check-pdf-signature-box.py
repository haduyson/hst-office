#!/usr/bin/env python3
# SPDX-License-Identifier: AGPL-3.0-only
"""HST PDF signs with a visible signature box, with and without the optional signature/seal images.

A synthetic one-page PDF is signed in the HST PDF viewer (.uno:HSTPdfSign) with a disposable software
certificate, once per case:
  no-image        the box text only (200 x 70 pt)
  signature       a blue scribble image on the left (240 x 90)
  seal            a red round seal image on the left (240 x 90)
  both-left       signature and seal on the left, the seal over the signature's left third (240 x 90)
  both-above      both images above the text (200 x 120)
  long-text       both images, a long reason (240 x 90)
For each signed copy: the office survived the signing; the file has exactly one signature and the
document signature service finds it valid (the certificate itself is not trusted); the update holds
one image XObject per image, each with an /SMask (transparency kept); the viewer renders blue pixels
only with the signature image and red pixels only with the seal. Renders are saved as evidence.

The images are written here (pure Python PNG, nothing real), set through the user settings the panel
keeps (org.openoffice.Office.HSTPdfViewer/Signing), and the certificate is found by its thumbprint
(LastCertificateThumbprint), so no dialog is driven.

Linux (an existing X display, NSS certutil):
  <instdir>/program/python check-pdf-signature-box.py --instdir DIR --out DIR --display :97
Windows (installed or admin-extracted HST Office, in the console session; the certificate goes to
CurrentUser\\My and is removed afterwards):
  "<install>\\program\\python.exe" check-pdf-signature-box.py --install DIR --out DIR
Exit 0 when every case passes, 1 on a failure, 77 on an unsupported platform.
"""
import argparse
import json
import os
from pathlib import Path
import platform
import re
import subprocess
import sys

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from pdf_signature_box_fixtures import (SIGNER, LinuxCertificate, WindowsCertificate, sample_pdf,  # noqa: E402
                                        seal_png, signature_png, start_office)

SIGNING = "/org.openoffice.Office.HSTPdfViewer/Signing"
LONG_REASON = "Phê duyệt hợp đồng số 12/2026/HĐ-KHCN về việc triển khai chữ ký số trong toàn đơn vị"
# name, signature image, seal image, images above, reason, box width, box height
CASES = [("no-image", False, False, False, "", 200.0, 70.0),
         ("signature", True, False, False, "Phê duyệt", 240.0, 90.0),
         ("seal", False, True, False, "", 240.0, 90.0),
         ("both-left", True, True, False, "", 240.0, 90.0),
         ("both-above", True, True, True, "Phê duyệt", 200.0, 120.0),
         ("long-text", True, True, False, LONG_REASON, 240.0, 90.0)]


def render(office, frame, target):
    from pdf_viewer_uno import info
    return info(office, frame, RenderPage=1, RenderDpi=96, RenderFile=target.as_uri())


def run_case(office, case, folder, sample, images, thumbprint, results, baseline):
    import uno
    from pdf_viewer_uno import info, open_viewer, signing_props, wait_info
    name, with_signature, with_seal, above, reason, width, height = case
    target = (folder / ("signed-" + name + ".pdf")).resolve()
    row = dict(case=name)
    results.append(row)
    office.set_config(SIGNING, "LastCertificateThumbprint", thumbprint)
    office.set_config(SIGNING, "UseImages", with_signature or with_seal)
    office.set_config(SIGNING, "SignatureImageURL", images["signature"].as_uri() if with_signature else "")
    office.set_config(SIGNING, "SealImageURL", images["seal"].as_uri() if with_seal else "")
    office.set_config(SIGNING, "ImagesAbove", above)
    frame, _ = open_viewer(office, sample)
    try:
        office.dispatch(frame, ".uno:HSTPdfSignPanel", signing_props(Show=True))
        panel = info(office, frame)
        row["certificate"] = panel.get("Certificate")
        result = office.dispatch(frame, ".uno:HSTPdfSign", signing_props(
            TargetURL=uno.systemPathToFileUrl(str(target)), Reason=reason, Visible=True, Page=1, X=40.0, Y=40.0,
            Width=width, Height=height)).Result
        row["signed"] = result is True and target.exists()
    finally:
        frame.close(True)
    if not row["signed"]:
        row["status"] = "FAIL"
        return
    data = target.read_bytes()
    update = data[len(sample.read_bytes()):]
    row["image_xobjects"] = len(re.findall(rb"/Subtype\s*/Image", update))
    row["smasks"] = len(re.findall(rb"/SMask\s+\d+\s+\d+\s+R", update))
    expected_images = int(with_signature) + int(with_seal)
    frame, _ = open_viewer(office, target)
    try:
        checked = wait_info(office, frame, "SignaturesChecked", lambda v: v is True, timeout=60)
        row["signatures"] = checked.get("SignatureCount")
        row["valid_or_untrusted"] = (checked.get("ValidSignatures") or 0) + (checked.get("UntrustedSignatures") or 0)
        row["invalid"] = checked.get("InvalidSignatures")
        drawn = render(office, frame, (folder / ("render-" + name + ".png")).resolve())
        row["red_pixels"], row["blue_pixels"] = drawn.get("RenderRedPixels"), drawn.get("RenderBluePixels")
        row["ink_permille"] = drawn.get("RenderInkPermille")
    finally:
        frame.close(True)
    checks = dict(
        one_valid_signature=row["signatures"] == 1 and row["valid_or_untrusted"] == 1 and not row["invalid"],
        # each image once, as an image XObject with its soft mask (the mask is an image XObject too)
        images_embedded_once=row["image_xobjects"] == 2 * expected_images and row["smasks"] == expected_images,
        # against the box without images: anti-aliased text has a few coloured edge pixels too
        blue_only_with_signature=coloured(row["blue_pixels"], baseline.get("blue_pixels"), with_signature),
        red_only_with_seal=coloured(row["red_pixels"], baseline.get("red_pixels"), with_seal),
        certificate_found=SIGNER in (row.get("certificate") or ""))
    row["checks"] = checks
    row["status"] = "PASS" if all(checks.values()) else "FAIL"
    if name == "no-image":
        baseline.update(row)


def coloured(pixels, baseline, expected):
    """Clearly more red (blue) pixels than the box without images when the image is there, else about as many."""
    pixels, baseline = pixels or 0, baseline if baseline is not None else (pixels or 0)
    return pixels > baseline + 60 if expected else pixels <= baseline + 30


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--instdir", help="Linux: the instdir (or an extracted .deb's opt/hst-office*)")
    parser.add_argument("--install", help="Windows: the installation folder (or an administrative MSI extraction)")
    parser.add_argument("--out", required=True)
    parser.add_argument("--display", default=":97")
    parser.add_argument("--port", type=int, default=2131)
    args = parser.parse_args()
    system = platform.system()
    if system not in ("Linux", "Windows"):
        print("SKIP: no disposable certificate route on", system)
        return 77
    out = Path(args.out).resolve()
    out.mkdir(parents=True, exist_ok=True)
    folder = out / "files"
    folder.mkdir(exist_ok=True)
    sample = folder / "mau.pdf"
    sample_pdf(sample)
    images = dict(signature=folder / "chu-ky-thu.png", seal=folder / "con-dau-thu.png")
    images["signature"].write_bytes(signature_png())
    images["seal"].write_bytes(seal_png())
    nssdb = out / "nssdb"
    certificate = LinuxCertificate(nssdb) if system == "Linux" else WindowsCertificate()
    results, report = [], dict(platform=system)
    thumbprint, office, baseline = None, None, {}
    try:
        thumbprint = certificate.install()
        if system == "Linux" and os.geteuid() == 0:
            import hst_gui
            subprocess.run(["chown", "-R", hst_gui.BUILD_USER, str(out)], check=True)
        office = start_office(args, out, nssdb)
        for case in CASES:
            try:
                run_case(office, case, folder, sample, images, thumbprint, results, baseline)
            except Exception as error:  # noqa: BLE001 - a crash of the office shows up here
                if not results or results[-1]["case"] != case[0]:
                    results.append(dict(case=case[0]))
                results[-1].update(status="FAIL", error=f"{type(error).__name__}: {error}")
                break
    except Exception as error:  # noqa: BLE001
        report["setup_error"] = f"{type(error).__name__}: {error}"
    finally:
        if office is not None:
            try:
                office.stop()
            except Exception:  # noqa: BLE001
                pass
        certificate.remove(thumbprint)
    report["cases"] = results
    (out / "result.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    for row in results:
        print(row.get("status"), row["case"], json.dumps({k: v for k, v in row.items() if k not in ("case", "status")},
                                                        ensure_ascii=False))
    passed = (not report.get("setup_error") and len(results) == len(CASES)
              and all(row.get("status") == "PASS" for row in results))
    if report.get("setup_error"):
        print("SETUP FAIL", report["setup_error"])
    print("PASS" if passed else "FAIL", "-", out / "result.json")
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
