# SPDX-License-Identifier: AGPL-3.0-only
"""Fixtures of check-pdf-signature-box.py: synthetic images and PDF, and a disposable certificate.

Nothing real: the images are a blue scribble and a red round seal written as PNG in pure Python, the PDF a
one-page sample, the certificate self-signed (an NSS database on Linux, CurrentUser\\My on Windows, removed
afterwards)."""
import base64
import hashlib
import math
import os
import platform
from pathlib import Path
import re
import struct
import subprocess
import zlib

SIGNER = "CÔNG TY TNHH THỬ NGHIỆM KHUNG CHỮ KÝ"


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
