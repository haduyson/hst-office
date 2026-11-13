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
import base64
import hashlib
import json
import math
import os
from pathlib import Path
import platform
import re
import struct
import subprocess
import sys
import time
import zlib

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

SIGNER = "CÔNG TY TNHH THỬ NGHIỆM KHUNG CHỮ KÝ"
SIGNING = "/org.openoffice.Office.HSTPdfViewer/Signing"
LONG_REASON = "Phê duyệt hợp đồng số 12/2026/HĐ-KHCN về việc triển khai chữ ký số trong toàn đơn vị"
# name, signature image, seal image, images above, reason, box width, box height
CASES = [("no-image", False, False, False, "", 200.0, 70.0),
         ("signature", True, False, False, "Phê duyệt", 240.0, 90.0),
         ("seal", False, True, False, "", 240.0, 90.0),
         ("both-left", True, True, False, "", 240.0, 90.0),
         ("both-above", True, True, True, "Phê duyệt", 200.0, 120.0),
         ("long-text", True, True, False, LONG_REASON, 240.0, 90.0)]


def png(width, height, pixel):
    """RGBA PNG bytes; pixel(x, y) -> (r, g, b, a)."""
    rows = b"".join(b"\0" + b"".join(bytes(pixel(x, y)) for x in range(width)) for y in range(height))

    def chunk(kind, body):
        return struct.pack(">I", len(body)) + kind + body + struct.pack(">I", zlib.crc32(kind + body) & 0xFFFFFFFF)
    return (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 6, 0, 0, 0))
            + chunk(b"IDAT", zlib.compress(rows, 9)) + chunk(b"IEND", b""))


def signature_png():
    """A blue scribble on a transparent background (300 x 100)."""
    ink = set()
    for step in range(600):
        x = 15 + step * 0.45
        y = 50 + 30 * math.sin(step / 25.0) * math.exp(-step / 900.0) + 8 * math.sin(step / 7.0)
        for dx in range(-3, 4):
            for dy in range(-3, 4):
                if dx * dx + dy * dy <= 9:
                    ink.add((int(x) + dx, int(y) + dy))
    return png(300, 100, lambda x, y: (20, 40, 160, 255) if (x, y) in ink else (0, 0, 0, 0))


def seal_png():
    """A red round seal with a star on a transparent background (200 x 200); not a real seal."""
    star = [(100 + (45 if k % 2 == 0 else 18) * math.cos(-math.pi / 2 + k * math.pi / 5),
             100 + (45 if k % 2 == 0 else 18) * math.sin(-math.pi / 2 + k * math.pi / 5)) for k in range(10)]

    def inside(px, py):
        hit, j = False, len(star) - 1
        for i in range(len(star)):
            (xi, yi), (xj, yj) = star[i], star[j]
            if (yi > py) != (yj > py) and px < (xj - xi) * (py - yi) / (yj - yi) + xi:
                hit = not hit
            j = i
        return hit

    def pixel(x, y):
        r = math.hypot(x - 100, y - 100)
        if 88 <= r <= 96 or 62 <= r <= 66 or inside(x, y):
            return (210, 25, 30, 235)
        return (0, 0, 0, 0)
    return png(200, 200, pixel)


def sample_pdf(path):
    """A one-page A4 PDF with a line of text (classic xref table)."""
    content = b"BT /F1 14 Tf 72 760 Td (HST Office - signature box check) Tj ET"
    objects = [b"<< /Type /Catalog /Pages 2 0 R >>",
               b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
               b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] /Resources << /Font << /F1 4 0 R >> >> "
               b"/Contents 5 0 R >>",
               b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
               b"<< /Length %d >>\nstream\n" % len(content) + content + b"\nendstream"]
    out, offsets = bytearray(b"%PDF-1.7\n"), []
    for number, body in enumerate(objects, 1):
        offsets.append(len(out))
        out += b"%d 0 obj\n" % number + body + b"\nendobj\n"
    xref = len(out)
    out += b"xref\n0 %d\n0000000000 65535 f \n" % (len(objects) + 1)
    out += b"".join(b"%010d 00000 n \n" % offset for offset in offsets)
    out += b"trailer\n<< /Size %d /Root 1 0 R >>\nstartxref\n%d\n%%%%EOF\n" % (len(objects) + 1, xref)
    path.write_bytes(bytes(out))


class LinuxCertificate:
    """A self-signed certificate in a fresh NSS database (the profile's CertDir)."""

    def __init__(self, folder):
        self.folder = Path(folder)

    def install(self):
        self.folder.mkdir(parents=True, exist_ok=True)
        subprocess.run(["certutil", "-N", "-d", "sql:" + str(self.folder), "--empty-password"], check=True)
        noise = self.folder / "noise"
        noise.write_bytes(os.urandom(64))
        subprocess.run(["certutil", "-S", "-d", "sql:" + str(self.folder), "-n", "hst-box", "-s",
                        "CN=" + SIGNER + ",O=HST Test,C=VN", "-x", "-t", "CTu,Cu,Cu", "-k", "rsa", "-g", "2048",
                        "-Z", "SHA256", "-v", "12", "-z", str(noise), "--keyUsage",
                        "digitalSignature,nonRepudiation"], check=True, capture_output=True)
        pem = subprocess.run(["certutil", "-L", "-d", "sql:" + str(self.folder), "-n", "hst-box", "-a"],
                             check=True, capture_output=True, text=True).stdout
        der = base64.b64decode("".join(line for line in pem.splitlines() if line and "CERTIFICATE" not in line))
        return hashlib.sha1(der).hexdigest().upper()

    def remove(self, _thumbprint):
        pass


class WindowsCertificate:
    """A self-signed certificate with a software key in CurrentUser\\My, removed afterwards."""

    def install(self):
        command = ("$c = New-SelfSignedCertificate -CertStoreLocation Cert:\\CurrentUser\\My -Subject "
                   "'CN=" + SIGNER + ", O=HST Test, C=VN' -KeyUsage DigitalSignature,NonRepudiation "
                   "-KeyAlgorithm RSA -KeyLength 2048 -HashAlgorithm SHA256 -NotAfter (Get-Date).AddDays(30) "
                   "-Provider 'Microsoft Software Key Storage Provider'; $c.Thumbprint")
        done = subprocess.run(["powershell", "-NoProfile", "-Command", command], capture_output=True, text=True,
                              encoding="utf-8")
        thumbprint = done.stdout.strip().splitlines()[-1].strip() if done.stdout.strip() else ""
        if done.returncode or not re.fullmatch(r"[0-9A-F]{40}", thumbprint):
            raise RuntimeError("cannot create the test certificate: " + done.stderr[-500:])
        return thumbprint

    def remove(self, thumbprint):
        if re.fullmatch(r"[0-9A-F]{40}", thumbprint or ""):
            subprocess.run(["powershell", "-NoProfile", "-Command",
                            "Remove-Item -LiteralPath 'Cert:\\CurrentUser\\My\\" + thumbprint + "' -Force"],
                           capture_output=True)


def start_office(args, out, nssdb):
    if platform.system() == "Linux":
        import hst_gui
        hst_gui.setup_uno(args.instdir)
        work = out / "office"
        office = hst_gui.Office(args.instdir, str(work), args.port, display=args.display, config=[
            ("/org.openoffice.Office.Common/Security/Scripting", "CertDir", str(nssdb))])
        office.start()
        return office
    import windows_gui as wg

    class Office(wg.WinOffice):
        """The Windows office with the two calls the Linux helper (hst_gui.Office) offers too."""

        def dispatch(self, frame, command, args=()):
            return self.service("com.sun.star.frame.DispatchHelper").executeDispatch(frame, command, "", 0, args)

        def set_config(self, node, name, value):
            import uno
            arg = uno.createUnoStruct("com.sun.star.beans.PropertyValue")
            arg.Name, arg.Value = "nodepath", node
            access = self.service("com.sun.star.configuration.ConfigurationProvider").createInstanceWithArguments(
                "com.sun.star.configuration.ConfigurationUpdateAccess", (arg,))
            access.setPropertyValue(name, value)
            access.commitChanges()

    office = Office(os.path.abspath(args.install), str(out / "profile"), args.port, str(out / "logs"), nodefault=True)
    office.start(fresh=True)
    wg.dismiss_startup(office, str(out / "startup-dialog.png"))
    return office


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
