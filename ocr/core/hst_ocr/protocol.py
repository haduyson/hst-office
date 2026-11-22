# SPDX-License-Identifier: LicenseRef-HST-Proprietary
"""JSON contract of the OCR core, version 1 (see ocr/README.md).

Request:  {"version": 1, "image": "<absolute path>", "mode": "text"|"formula"|"table"|"page",
           "lang": "vie", "threads": 2}
Response: {"version": 1, "ok": true, "mode": ..., "width": W, "height": H,
           "blocks": [{"type": "paragraph", "text": str, "bbox": [x, y, w, h], "confidence": 0..1}
                      | {"type": "formula", "latex": str, "display": bool, "bbox": [...]}
                      | {"type": "table", "rows": [[str, ...], ...], "bbox": [...]}],
           "timings_ms": {...}, "engine": {...}}
Error:    {"version": 1, "ok": false, "error": {"code": str, "message": str}}
"""
import os
from dataclasses import dataclass

from . import PROTOCOL_VERSION

MODES = ("text", "formula", "table", "page")
MAX_IMAGE_BYTES = 64 * 1024 * 1024
MAX_THREADS = 64


class OcrError(Exception):
    """A failure the caller can show: code is stable (for the UI texts), message is for logs."""

    def __init__(self, code, message):
        super().__init__(message)
        self.code = code
        self.message = message


@dataclass(frozen=True)
class Request:
    image: str
    mode: str = "text"
    lang: str = "vie"
    threads: int = 2


def parse_request(data):
    """Validate a decoded JSON request; raise OcrError("bad-request", ...) on anything unexpected."""
    if not isinstance(data, dict):
        raise OcrError("bad-request", "request must be a JSON object")
    if data.get("version") != PROTOCOL_VERSION:
        raise OcrError("bad-version", "unsupported protocol version %r" % data.get("version"))
    unknown = set(data) - {"version", "image", "mode", "lang", "threads"}
    if unknown:
        raise OcrError("bad-request", "unknown fields: %s" % ", ".join(sorted(unknown)))
    image = data.get("image")
    if not isinstance(image, str) or not os.path.isabs(image):
        raise OcrError("bad-request", "image must be an absolute path")
    if not os.path.isfile(image):
        raise OcrError("image-missing", "image not found")
    if os.path.getsize(image) > MAX_IMAGE_BYTES:
        raise OcrError("image-too-large", "image larger than %d MB" % (MAX_IMAGE_BYTES >> 20))
    mode = data.get("mode", "text")
    if mode not in MODES:
        raise OcrError("bad-request", "mode must be one of %s" % ", ".join(MODES))
    lang = data.get("lang", "vie")
    if not isinstance(lang, str) or not lang.replace("+", "").isalpha() or len(lang) > 32:
        raise OcrError("bad-request", "lang must look like 'vie' or 'vie+eng'")
    threads = data.get("threads", 2)
    if not isinstance(threads, int) or isinstance(threads, bool) or not 1 <= threads <= MAX_THREADS:
        raise OcrError("bad-request", "threads must be an integer 1..%d" % MAX_THREADS)
    return Request(image=image, mode=mode, lang=lang, threads=threads)


def ok_response(mode, size, blocks, timings, engine):
    return {"version": PROTOCOL_VERSION, "ok": True, "mode": mode, "width": size[0], "height": size[1],
            "blocks": blocks, "timings_ms": {k: round(v, 1) for k, v in timings.items()}, "engine": engine}


def error_response(code, message):
    return {"version": PROTOCOL_VERSION, "ok": False, "error": {"code": code, "message": message}}
