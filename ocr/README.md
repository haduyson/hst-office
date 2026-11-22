# HST OCR (prototype for 1.0.4)

Offline recognition of Vietnamese text, math formulas and tables in scanned images for HST Writer (Sheets comes
next). Prototype status: measurements and design are in
`plans/reports/fullstack-261122-1400-ocr-prototype.md`.

## Layout

| Path | What | UNO? |
|---|---|---|
| `core/hst_ocr/` | Recognition core: image loading, Tesseract text, pix2tex formulas (ONNX Runtime), ruled-table grid, optional PP-DocLayoutV3 page layout, JSON protocol, `python -m hst_ocr` process | no |
| `extension/` | `.oxt` source: the Writer command "Chèn ▸ Nhận dạng chữ từ ảnh…" (`vn.hasontech.hst.ocr:RecognizeText`), engine process client, insertion into Writer | thin layer only |
| `bench/` | Synthetic samples (no personal data), accuracy metrics, benchmarks | no |
| `tests/` | Unit tests (`python3 -m unittest discover -s ocr/tests`) and a manual Writer integration check | integration only |
| `build-oxt.py` | Deterministic `.oxt` build, optionally with a bundled `engine/` folder | – |

The core never imports UNO. The extension talks to it only through the JSON protocol below, so the same
extension can later run the Rust crate `hst-ocr` as its engine, and the Rust suite can reuse the protocol.

## Protocol v1

Request (one JSON object on stdin; with `--serve`, one per line):

```json
{"version": 1, "image": "/abs/path.png", "mode": "text|formula|table|page", "lang": "vie", "threads": 2}
```

Response:

```json
{"version": 1, "ok": true, "mode": "page", "width": 2500, "height": 1921,
 "blocks": [{"type": "paragraph", "text": "…", "bbox": [x, y, w, h], "confidence": 0.93},
            {"type": "formula", "latex": "x^{2}", "display": true, "bbox": [x, y, w, h]},
            {"type": "table", "rows": [["…"]], "cells": [{"r": 0, "c": 0, "rowspan": 1, "colspan": 2, "text": "…"}],
             "bbox": [x, y, w, h]}],
 "warnings": ["layout-missing"], "timings_ms": {"layout": 3600, "total": 7200}, "engine": {"core": "0.1.0"}}
```

Errors: `{"version": 1, "ok": false, "error": {"code": "…", "message": "…"}}`. Codes are stable (the UI maps them
to Vietnamese messages in `extension/python/hst_ocr_uno/texts.py`): `bad-json`, `bad-request`, `bad-version`,
`image-missing`, `image-unreadable`, `image-too-large`, `no-content`, `engine-missing`, `engine-failed`,
`model-missing`, `timeout`, `internal`.

## Data folder (`HST_OCR_HOME`)

`tessdata/vie.traineddata` (tessdata_best), `bin/tesseract[.exe]` (else `tesseract` on PATH),
`models/formula/{image_resizer,encoder,decoder}.onnx` + `tokenizer.json` (pix2tex ONNX),
`models/layout/pp_doc_layoutv3.onnx` (optional). Models are not in git.

## Development run

```bash
export HST_OCR_HOME=/path/to/data PYTHONPATH=/path/to/deps:ocr/core   # deps: onnxruntime numpy pillow opencv-python-headless tokenizers
echo '{"version":1,"image":"/abs/scan.png","mode":"page"}' | python3 -m hst_ocr
python3 ocr/build-oxt.py dist/hst-ocr.oxt
HST_OCR_ENGINE='["python3","-m","hst_ocr"]'   # how the extension finds the core during development
```
