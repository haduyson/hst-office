# SPDX-License-Identifier: LicenseRef-HST-Proprietary
"""Text benchmark: Tesseract (tessdata given by HST_OCR_HOME) on SAMPLES/text, CER/WER and seconds per page.

Usage: taskset -c 0,1 python3 bench_text.py SAMPLES LABEL [--no-upscale] > results.jsonl
Run under `taskset -c 0,1` to model a weak 2-core teacher PC; Tesseract gets OMP_THREAD_LIMIT=2.
"""
import json
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path[:0] = [HERE, os.path.join(HERE, "..", "core")]
from hst_ocr import imaging, text_tesseract  # noqa: E402
from metrics import cer, diacritic_errors, wer  # noqa: E402


def main(samples, label, upscale=True):
    truth = json.load(open(os.path.join(samples, "truth.json"), encoding="utf-8"))["text"]
    for name in sorted(os.listdir(os.path.join(samples, "text"))):
        page_id, variant = name[:-4].rsplit("-", 1)
        start = time.perf_counter()
        img = imaging.load(os.path.join(samples, "text", name))
        if upscale:
            img, _ = imaging.normalise_scale(img)
        blocks = text_tesseract.recognize(img, threads=2)
        secs = time.perf_counter() - start
        hyp = "\n".join(b["text"] for b in blocks)
        ref = truth[page_id]
        print(json.dumps({"engine": label, "sample": page_id, "variant": variant, "seconds": round(secs, 2),
                          "cer": round(cer(ref, hyp), 4), "wer": round(wer(ref, hyp), 4),
                          "diacritic_err": round(diacritic_errors(ref, hyp), 4), "chars": len(ref),
                          "hyp_head": hyp[:160]}, ensure_ascii=False), flush=True)


if __name__ == "__main__":
    if len(sys.argv) < 3:
        sys.exit(__doc__)
    main(sys.argv[1], sys.argv[2], "--no-upscale" not in sys.argv)
