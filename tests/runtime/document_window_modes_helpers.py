# SPDX-License-Identifier: AGPL-3.0-only
"""Helpers of the window mode checks (check-document-window-modes*.py): open documents from outside, PDF
fixtures, and a snapshot of every open document that proves nothing was reloaded or lost."""
import os
import subprocess
import time

import hst_gui


def tiny_pdf(path, text):
    """A one-page PDF (shown by HST PDF) with valid cross references."""
    stream = f"BT /F1 24 Tf 72 720 Td ({text}) Tj ET".encode()
    objects = [b"<< /Type /Catalog /Pages 2 0 R >>", b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
               b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Contents 4 0 R "
               b"/Resources << /Font << /F1 5 0 R >> >> >>",
               b"<< /Length %d >>\nstream\n" % len(stream) + stream + b"\nendstream",
               b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>"]
    out, offsets = bytearray(b"%PDF-1.4\n"), []
    for number, body in enumerate(objects, 1):
        offsets.append(len(out))
        out += b"%d 0 obj\n" % number + body + b"\nendobj\n"
    xref = len(out)
    out += b"xref\n0 %d\n0000000000 65535 f \n" % (len(objects) + 1)
    out += b"".join(b"%010d 00000 n \n" % offset for offset in offsets)
    out += b"trailer\n<< /Size %d /Root 1 0 R >>\nstartxref\n%d\n%%%%EOF\n" % (len(objects) + 1, xref)
    with open(path, "wb") as handle:
        handle.write(out)
    subprocess.run(["chown", hst_gui.BUILD_USER, path], check=False)


def touch_all(office):
    for doc in office.desktop().getComponents():
        try:
            doc.setModified(True)  # no untouched new document may be replaced (upstream recycling)
        except Exception:  # noqa: BLE001 - HST PDF has no modified state
            pass


def open_twice(c, office, app, flag):
    for n in (1, 2):
        if flag:
            c.second_office(flag)
        else:
            path = os.path.join(office.workdir, f"tep-{n}.pdf")
            tiny_pdf(path, f"HST PDF {n}")
            c.second_office(path)
        time.sleep(3)
        touch_all(office)


def snapshot(office):
    """RuntimeUID -> (modified, text) of every document: proves nothing was reloaded or lost."""
    result = {}
    for doc in office.desktop().getComponents():
        try:
            text = doc.getText().getString() if hasattr(doc, "getText") else ""
            result[doc.RuntimeUID] = (doc.isModified(), text)
        except Exception:  # noqa: BLE001 - HST PDF (no model state)
            pass
    return result
