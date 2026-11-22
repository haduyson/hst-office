# SPDX-License-Identifier: LicenseRef-HST-Proprietary
"""One OCR request → one response (protocol.py). The only entry point the CLI and tests use."""
import time

from . import __version__, formula_pix2tex, imaging, layout_ppdoc, protocol, table_grid, text_tesseract
from .protocol import OcrError


def _text_blocks(img, req, offset=(0, 0), psm=3):
    scaled, factor = imaging.normalise_scale(img)
    blocks = text_tesseract.recognize(scaled, req.lang, req.threads, psm=psm)
    for block in blocks:
        x, y, w, h = block["bbox"]
        block["bbox"] = [round(x / factor) + offset[0], round(y / factor) + offset[1], round(w / factor),
                         round(h / factor)]
    return blocks


def _formula_block(img, req, bbox):
    return {"type": "formula", "latex": formula_pix2tex.recognize(img, req.threads), "display": True, "bbox": bbox}


def _table_block(img, req, offset=(0, 0)):
    table = table_grid.cells(img, req.lang, req.threads)
    if table is None:
        return None
    x, y, w, h = table["bbox"]
    return {"type": "table", "rows": table["rows"], "cells": table["cells"],
            "bbox": [x + offset[0], y + offset[1], w, h]}


def _page(img, req, timings, warnings):
    if not layout_ppdoc.available():
        warnings.append("layout-missing")
        return _text_blocks(img, req)
    start = time.perf_counter()
    found = layout_ppdoc.regions(img, req.threads)
    timings["layout"] = (time.perf_counter() - start) * 1000
    blocks = []
    for kind, (x0, y0, x1, y1), _score in found:
        pad = 6
        box = (max(0, x0 - pad), max(0, y0 - pad), min(img.width, x1 + pad), min(img.height, y1 + pad))
        crop = img.crop(box)
        bbox = [box[0], box[1], box[2] - box[0], box[3] - box[1]]
        if kind == "formula":
            blocks.append(_formula_block(crop, req, bbox))
            continue
        if kind == "table":
            table = _table_block(crop, req, box[:2])
            if table is not None:
                blocks.append(table)
                continue
            warnings.append("table-without-borders")  # read as text so nothing is lost
        blocks.extend(_text_blocks(crop, req, box[:2], psm=6))
    return blocks


def run(data):
    """Response dict for a decoded JSON request; never raises for bad input or engine failures."""
    started = time.perf_counter()
    try:
        req = protocol.parse_request(data)
        img = imaging.load(req.image)
        timings, warnings = {}, []
        if req.mode == "formula":
            blocks = [_formula_block(img, req, [0, 0, img.width, img.height])]
        elif req.mode == "table":
            table = _table_block(img, req)
            if table is None:
                warnings.append("table-without-borders")
                blocks = _text_blocks(img, req)
            else:
                blocks = [table]
        elif req.mode == "page":
            blocks = _page(img, req, timings, warnings)
        else:
            blocks = _text_blocks(img, req)
        timings["total"] = (time.perf_counter() - started) * 1000
        used_layout = req.mode == "page" and "layout-missing" not in warnings
        engine = {"core": __version__, "text": "tesseract", "formula": "pix2tex", "table": "ruling-grid",
                  "layout": "pp-doclayout-v3" if used_layout else None}
        response = protocol.ok_response(req.mode, img.size, blocks, timings, engine)
        if warnings:
            response["warnings"] = warnings
        return response
    except OcrError as exc:
        return protocol.error_response(exc.code, exc.message)
