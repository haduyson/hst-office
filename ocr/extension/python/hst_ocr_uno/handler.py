# SPDX-License-Identifier: LicenseRef-HST-Proprietary
"""vn.hasontech.hst.ocr:RecognizeText — "Nhận dạng chữ từ ảnh" in HST Writer.

Asks for an image, runs the OCR core (engine_client, a separate process speaking JSON) in mode "page" — text,
display formulas and bordered tables; the core falls back to plain text when it has no layout model — and inserts
the result at the cursor (writer_insert). The office window is busy while the core runs (status bar text); an
asynchronous run with a Cancel button is listed as next step in the prototype report.
"""
import os

import unohelper
from com.sun.star.frame import XDispatch, XDispatchProvider
from com.sun.star.lang import XInitialization

from . import blocks, engine_client
from .texts import ERRORS, TEXTS

COMMAND = "vn.hasontech.hst.ocr:RecognizeText"
IMPLEMENTATION = "vn.hasontech.hst.ocr.DispatchProvider"
IMAGE_FILTERS = (("Ảnh (*.png; *.jpg; *.jpeg; *.tif; *.tiff; *.bmp; *.webp)",
                  "*.png;*.jpg;*.jpeg;*.tif;*.tiff;*.bmp;*.webp"),)


class Handler(unohelper.Base, XDispatchProvider, XDispatch, XInitialization):
    def __init__(self, ctx, *args):
        self.ctx = ctx
        self.frame = None

    def initialize(self, args):
        if args:
            self.frame = args[0]

    def queryDispatch(self, url, target, flags):
        return self if url.Complete == COMMAND else None

    def queryDispatches(self, requests):
        return tuple(self.queryDispatch(r.FeatureURL, r.FrameName, r.SearchFlags) for r in requests)

    def addStatusListener(self, listener, url):
        pass

    def removeStatusListener(self, listener, url):
        pass

    def dispatch(self, url, args):
        if self.frame is None:
            return
        doc = self.frame.getController().getModel()
        if not doc.supportsService("com.sun.star.text.TextDocument"):
            return self._message(TEXTS["writerOnly"])
        path = self._pick_image()
        if not path:
            return
        status = self.frame.createStatusIndicator()
        status.start(TEXTS["running"], 0)
        try:
            response = engine_client.recognize(path, mode="page", threads=_threads())
        except engine_client.EngineError as exc:
            return self._message(ERRORS.get(exc.code, ERRORS["engine-failed"]) + "\n\n(" + exc.code + ")")
        finally:
            status.end()
        items = blocks.to_items(response["blocks"])
        if not items:
            return self._message(TEXTS["nothing"])
        from .writer_insert import insert_items
        insert_items(self.ctx, doc, items, TEXTS["undo"])

    def _pick_image(self):
        picker = self.ctx.ServiceManager.createInstanceWithArgumentsAndContext(
            "com.sun.star.ui.dialogs.FilePicker", (10,), self.ctx)  # FILEOPEN_SIMPLE
        picker.setTitle(TEXTS["pickTitle"])
        for title, pattern in IMAGE_FILTERS:
            picker.appendFilter(title, pattern)
        if picker.execute() != 1:
            return None
        import uno
        files = picker.getSelectedFiles()
        return uno.fileUrlToSystemPath(files[0]) if files else None

    def _message(self, text):
        window = self.frame.getContainerWindow()
        toolkit = window.getToolkit()
        box = toolkit.createMessageBox(window, 1, 1, TEXTS["title"], text)  # INFOBOX, BUTTONS_OK
        box.execute()


def _threads():
    """Two threads keep the office responsive on 2-core teacher PCs; more cores get at most four."""
    return max(1, min(4, (os.cpu_count() or 2) // 2 or 1))
