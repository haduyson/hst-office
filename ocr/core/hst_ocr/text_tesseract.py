# SPDX-License-Identifier: LicenseRef-HST-Proprietary
"""Text recognition with the Tesseract program (LSTM engine, Vietnamese tessdata_best).

The image goes to Tesseract on stdin as PNG; Tesseract answers TSV (one row per word with block, paragraph and
line numbers), which becomes paragraphs: words of a line are joined by spaces, lines of a paragraph by spaces
too (a scanned line break is layout, not a paragraph end), and a word ending in "-" at line end is kept as is.
"""
import io
import os
import subprocess

from . import resources
from .protocol import OcrError

TIMEOUT_S = 180


def _png(image):
    buf = io.BytesIO()
    image.save(buf, "PNG")
    return buf.getvalue()


def run_tsv(image, lang="vie", threads=2, psm=3):
    """Raw TSV text of Tesseract for a PIL image."""
    cmd = [resources.tesseract_exe(), "stdin", "stdout", "-l", lang, "--oem", "1", "--psm", str(psm)]
    tessdata = resources.tessdata_dir()
    if tessdata:
        cmd[1:1] = ["--tessdata-dir", tessdata]
    cmd += ["-c", "tessedit_create_tsv=1"]  # not the "tsv" config name: bundled tessdata has no configs/ folder
    env = dict(os.environ, OMP_THREAD_LIMIT=str(threads))
    try:
        proc = subprocess.run(cmd, input=_png(image), capture_output=True, timeout=TIMEOUT_S, env=env, check=False)
    except subprocess.TimeoutExpired as exc:
        raise OcrError("timeout", "Tesseract did not finish in %d s" % TIMEOUT_S) from exc
    except OSError as exc:
        raise OcrError("engine-missing", "cannot start Tesseract: %s" % exc) from exc
    if proc.returncode != 0:
        tail = proc.stderr.decode("utf-8", "replace").strip().splitlines()[-1:] or [""]
        raise OcrError("engine-failed", "Tesseract exit %d: %s" % (proc.returncode, tail[0]))
    return proc.stdout.decode("utf-8", "replace")


def paragraphs_from_tsv(tsv, offset=(0, 0)):
    """[{"type": "paragraph", "text", "bbox", "confidence"}] in reading order from Tesseract TSV."""
    groups = {}
    order = []
    for row in tsv.splitlines()[1:]:
        cols = row.split("\t")
        if len(cols) != 12 or cols[0] != "5" or not cols[11].strip():
            continue
        key = (int(cols[2]), int(cols[3]))  # block, paragraph
        if key not in groups:
            groups[key] = {"lines": {}, "boxes": [], "conf": []}
            order.append(key)
        group = groups[key]
        group["lines"].setdefault(int(cols[4]), []).append(cols[11])
        x, y, w, h = (int(c) for c in cols[6:10])
        group["boxes"].append((x, y, x + w, y + h))
        if float(cols[10]) >= 0:
            group["conf"].append(float(cols[10]) / 100)
    blocks = []
    for key in order:
        group = groups[key]
        text = " ".join(" ".join(words) for _, words in sorted(group["lines"].items()))
        x0 = min(b[0] for b in group["boxes"])
        y0 = min(b[1] for b in group["boxes"])
        x1 = max(b[2] for b in group["boxes"])
        y1 = max(b[3] for b in group["boxes"])
        conf = sum(group["conf"]) / len(group["conf"]) if group["conf"] else 0.0
        blocks.append({"type": "paragraph", "text": text, "bbox": [x0 + offset[0], y0 + offset[1], x1 - x0, y1 - y0],
                       "confidence": round(conf, 3)})
    return blocks


def recognize(image, lang="vie", threads=2, psm=3, offset=(0, 0)):
    return paragraphs_from_tsv(run_tsv(image, lang, threads, psm), offset)


def line_text(image, lang="vie", threads=2):
    """Text of a single-line or single-cell crop (psm 6 = one uniform block), joined with spaces."""
    return " ".join(b["text"] for b in recognize(image, lang, threads, psm=6))
