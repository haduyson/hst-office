# SPDX-License-Identifier: AGPL-3.0-only
"""Helpers of the window mode checks (check-document-window-modes*.py): open documents from outside, PDF
fixtures, and a snapshot of every open document that proves nothing was reloaded or lost."""
import os
import subprocess
import time

import hst_gui
from pdf_fixture import tiny_pdf


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
            subprocess.run(["chown", hst_gui.BUILD_USER, path], check=False)
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
