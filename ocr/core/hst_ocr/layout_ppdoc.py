# SPDX-License-Identifier: LicenseRef-HST-Proprietary
"""Page layout (text / display formula / table regions) with PP-DocLayoutV3 on ONNX Runtime.

Licence status RISK (Apache-2.0 weights, undisclosed training data; see the prototype report), 130 MB, ~3.7 s per
page on 2 cores: kept optional. Without HST_OCR_HOME/models/layout/pp_doc_layoutv3.onnx, mode "page" falls back to
plain text recognition and says so in the response warnings.
"""
import os

import numpy as np
from PIL import Image

from . import resources

SIZE = 800
MIN_SCORE = 0.45
KINDS = {"text": "text", "paragraph_title": "text", "doc_title": "text", "abstract": "text", "content": "text",
         "reference_content": "text", "footnote": "text", "vision_footnote": "text", "aside_text": "text",
         "algorithm": "text", "number": "text", "display_formula": "formula", "table": "table"}
_CACHE = {}


def available():
    return os.path.isfile(os.path.join(resources.home(), "models", "layout", "pp_doc_layoutv3.onnx"))


def _session(threads):
    if threads not in _CACHE:
        import onnxruntime as ort
        opts = ort.SessionOptions()
        opts.intra_op_num_threads = threads
        opts.inter_op_num_threads = 1
        sess = ort.InferenceSession(resources.model("layout", "pp_doc_layoutv3.onnx"), opts,
                                    providers=["CPUExecutionProvider"])
        labels = sess.get_modelmeta().custom_metadata_map["character"].split("\n")
        _CACHE[threads] = (sess, labels)
    return _CACHE[threads]


def regions(gray, threads=2):
    """[(kind, (x0, y0, x1, y1), score)] top to bottom, kind in text|formula|table; other classes (figures, headers,
    page numbers, seals) are dropped, overlapping boxes keep the higher score."""
    sess, labels = _session(threads)
    width, height = gray.size
    rgb = np.asarray(gray.convert("RGB").resize((SIZE, SIZE), Image.BICUBIC), dtype=np.float32) / 255.0
    feed = {"im_shape": np.array([[SIZE, SIZE]], np.float32), "image": rgb.transpose(2, 0, 1)[None],
            "scale_factor": np.array([[SIZE / height, SIZE / width]], np.float32)}
    boxes = sess.run(None, feed)[0]
    found = []
    for row in boxes:
        label = labels[int(row[0])] if 0 <= int(row[0]) < len(labels) else ""
        kind = KINDS.get(label)
        if kind is None or row[1] < MIN_SCORE:
            continue
        x0, y0, x1, y1 = (int(round(v)) for v in row[2:6])
        box = (max(0, x0), max(0, y0), min(width, x1), min(height, y1))
        if box[2] - box[0] > 4 and box[3] - box[1] > 4:
            found.append((kind, box, float(row[1])))
    kept = []
    for item in sorted(found, key=lambda r: -r[2]):
        if all(_overlap(item[1], k[1]) < 0.5 for k in kept):
            kept.append(item)
    return sorted(kept, key=lambda r: (r[1][1], r[1][0]))


def _overlap(a, b):
    """Intersection over the smaller box."""
    w = min(a[2], b[2]) - max(a[0], b[0])
    h = min(a[3], b[3]) - max(a[1], b[1])
    if w <= 0 or h <= 0:
        return 0.0
    small = min((a[2] - a[0]) * (a[3] - a[1]), (b[2] - b[0]) * (b[3] - b[1]))
    return w * h / max(1, small)
