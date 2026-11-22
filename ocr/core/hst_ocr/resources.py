# SPDX-License-Identifier: LicenseRef-HST-Proprietary
"""Where the core finds its models and the Tesseract program.

Layout of HST_OCR_HOME (the folder shipped next to the engine, or set by the environment for development):
  tessdata/vie.traineddata            Tesseract language data (tessdata_best)
  bin/tesseract[.exe]                 Tesseract program; falls back to `tesseract` on PATH
  models/formula/{encoder,decoder,image_resizer}.onnx, tokenizer.json   formula recognition (pix2tex)
  models/layout/pp_doc_layoutv3.onnx  page layout (optional, mode "page")
"""
import os
import shutil

from .protocol import OcrError


def home():
    path = os.environ.get("HST_OCR_HOME") or os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "data")
    return os.path.abspath(path)


def model(*parts):
    path = os.path.join(home(), "models", *parts)
    if not os.path.isfile(path):
        raise OcrError("model-missing", "missing model file %s" % "/".join(parts))
    return path


def tessdata_dir():
    path = os.path.join(home(), "tessdata")
    return path if os.path.isdir(path) else None


def tesseract_exe():
    exe = "tesseract.exe" if os.name == "nt" else "tesseract"
    bundled = os.path.join(home(), "bin", exe)
    if os.path.isfile(bundled):
        return bundled
    found = shutil.which("tesseract")
    if not found:
        raise OcrError("engine-missing", "Tesseract program not found")
    return found
