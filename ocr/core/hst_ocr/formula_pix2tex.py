# SPDX-License-Identifier: LicenseRef-HST-Proprietary
"""Formula image → LaTeX with pix2tex (LaTeX-OCR, MIT code and weights) on ONNX Runtime.

Models: HST_OCR_HOME/models/formula/{image_resizer,encoder,decoder}.onnx + tokenizer.json, the ONNX export
published by RapidLaTeXOCR (MIT). The pre-processing, the resizer loop and the token clean-up follow pix2tex and
RapidLaTeXOCR (both MIT; notices go into the package's third-party notices); decoding is greedy, which is what
their near-zero sampling temperature amounts to. Kept free of the RapidLaTeXOCR package itself so the steps map
one-to-one onto the future Rust crate.
"""
import re

import numpy as np
from PIL import Image

from . import resources
from .protocol import OcrError

MAX_W, MAX_H, MIN_SIDE, DIV = 672, 192, 32, 32
MEAN, STD = 0.7931 * 255, 0.1738 * 255
GLYPH_PX = 9  # pix2tex reads best when the median glyph (connected ink blob) is about this tall (tuned on 9/11/13)
BOS, EOS, MAX_TOKENS = 1, 2, 512
_CACHE = {}


class Pix2Tex:
    def __init__(self, threads=2):
        try:
            import onnxruntime as ort
            from tokenizers import Tokenizer
        except ImportError as exc:
            raise OcrError("engine-missing", "formula engine not installed: %s" % exc) from exc
        opts = ort.SessionOptions()
        opts.intra_op_num_threads = threads  # default would be one thread per core: oversubscribes weak PCs
        opts.inter_op_num_threads = 1

        def session(name):
            return ort.InferenceSession(resources.model("formula", name), opts, providers=["CPUExecutionProvider"])

        self.resizer, self.encoder, self.decoder = (session(n) for n in
                                                    ("image_resizer.onnx", "encoder.onnx", "decoder.onnx"))
        self.tokenizer = Tokenizer.from_file(resources.model("formula", "tokenizer.json"))

    def __call__(self, image):
        tensor = self._resized_tensor(_crop_pad(_normalise_glyphs(image.convert("L"))))
        context = self.encoder.run(None, {self.encoder.get_inputs()[0].name: tensor})[0]
        names = [i.name for i in self.decoder.get_inputs()]
        ids = [BOS]
        for _ in range(MAX_TOKENS):
            seq = np.array([ids], dtype=np.int64)
            feed = dict(zip(names, (seq, np.ones_like(seq, dtype=bool), context)))
            nxt = int(np.argmax(self.decoder.run(None, feed)[0][0, -1]))
            if nxt == EOS:
                break
            ids.append(nxt)
        return _clean(self.tokenizer.decode(ids[1:]))

    def _resized_tensor(self, img):
        """pix2tex's resizer network predicts the width at which the formula reads best; loop until it agrees."""
        img = _minmax(img)
        ratio, width, height = 1.0, img.width, img.height
        tensor = None
        for _ in range(10):
            height = max(1, int(height * ratio))  # cumulative, exactly as pix2tex does it
            resized = img.resize((width, height), Image.BILINEAR if ratio > 1 else Image.LANCZOS)
            candidate = _crop_pad(_minmax(resized))
            tensor = ((np.asarray(candidate, dtype=np.float32) - MEAN) / STD)[None, None]
            pred = self.resizer.run(None, {self.resizer.get_inputs()[0].name: tensor})[0]
            width = (int(np.argmax(pred.reshape(-1))) + 1) * DIV
            if width == candidate.width:
                break
            ratio = width / candidate.width
        return tensor


def _normalise_glyphs(img, target=None):
    """Scale so the median glyph height is GLYPH_PX: a 300 dpi scan otherwise gives glyphs three times larger than
    pix2tex's training renders, and exact match on the HST formula set drops from 67 % to 33 %."""
    import cv2
    gray = np.asarray(img, dtype=np.uint8)
    _, ink = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
    _, _, stats, _ = cv2.connectedComponentsWithStats(ink)
    heights = [s[3] for s in stats[1:] if s[4] >= 12]
    if not heights:
        return img
    factor = min(3.0, max(0.1, (target or GLYPH_PX) / float(np.median(heights))))
    if abs(factor - 1) < 0.05:
        return img
    return img.resize((max(1, round(img.width * factor)), max(1, round(img.height * factor))), Image.LANCZOS)


def _crop_pad(img):
    """Contrast-stretch, crop to the ink, pad right/bottom to multiples of 32 on white (pix2tex `pad`)."""
    data = np.asarray(img, dtype=np.float32)
    span = float(data.max() - data.min()) or 1.0
    data = (data - data.min()) / span * 255
    if data.mean() <= 128:  # light ink on dark ground: invert
        data = 255 - data
    ys, xs = np.nonzero(data < 128)
    if not len(xs):
        raise OcrError("no-content", "the image holds no formula")
    rect = data[ys.min():ys.max() + 1, xs.min():xs.max() + 1].astype(np.uint8)
    h, w = rect.shape
    out = Image.new("L", (-(-w // DIV) * DIV, -(-h // DIV) * DIV), 255)
    out.paste(Image.fromarray(rect), (0, 0))
    return out


def _minmax(img):
    ratio = max(img.width / MAX_W, img.height / MAX_H)
    if ratio > 1:
        img = img.resize((max(1, int(img.width / ratio)), max(1, int(img.height / ratio))), Image.BILINEAR)
    if img.width < MIN_SIDE or img.height < MIN_SIDE:
        padded = Image.new("L", (max(img.width, MIN_SIDE), max(img.height, MIN_SIDE)), 255)
        padded.paste(img, (0, 0))
        img = padded
    return img


TEXT_CMD = re.compile(r"(\\(operatorname|mathrm|text|mathbf)\s?\*? {.*?})")


def _clean(decoded):
    """Token text → LaTeX: BPE pieces joined, Ġ is a space, spaces between non-letters dropped (pix2tex post)."""
    s = "".join(decoded.split(" ")).replace("Ġ", " ")
    for tok in ("[EOS]", "[BOS]", "[PAD]"):
        s = s.replace(tok, "")
    s = s.strip()
    names = [m[0].replace(" ", "") for m in TEXT_CMD.findall(s)]
    s = TEXT_CMD.sub(lambda _m: names.pop(0), s)
    while True:
        new = re.sub(r"(?!\\ )([\W_^\d])\s+?([\W_^\d])", r"\1\2", s)
        new = re.sub(r"(?!\\ )([\W_^\d])\s+?([a-zA-Z])", r"\1\2", new)
        new = re.sub(r"([a-zA-Z])\s+?([\W_^\d])", r"\1\2", new)
        if new == s:
            return s
        s = new


def recognize(image, threads=2):
    """LaTeX of a PIL image that holds one formula (no surrounding $)."""
    if threads not in _CACHE:
        _CACHE[threads] = Pix2Tex(threads)
    try:
        return _CACHE[threads](image)
    except OcrError:
        raise
    except Exception as exc:  # onnxruntime raises its own exception types; keep the message for the log
        raise OcrError("engine-failed", "formula recognition failed: %s" % exc) from exc
