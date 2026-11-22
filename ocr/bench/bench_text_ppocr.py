# SPDX-License-Identifier: LicenseRef-HST-Proprietary
"""Comparison only: PP-OCRv6 (RapidOCR ONNX) on SAMPLES/text. Its dictionary lacks most Vietnamese letters, so this
shows the accuracy cost rather than a candidate for the product.

Usage: taskset -c 0,1 python3 bench_text_ppocr.py SAMPLES MODELS_DIR SIZE(tiny|small) > results.jsonl
"""
import json
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from metrics import cer, wer  # noqa: E402


def main(samples, models, size):
    from rapidocr import RapidOCR
    engine = RapidOCR(params={
        "Global.use_cls": False,
        "Det.model_path": os.path.join(models, "PP-OCRv6_det_%s.onnx" % size),
        "Rec.model_path": os.path.join(models, "PP-OCRv6_rec_%s.onnx" % size),
        "EngineConfig.onnxruntime.intra_op_num_threads": 2,
        "EngineConfig.onnxruntime.inter_op_num_threads": 1,
    })
    truth = json.load(open(os.path.join(samples, "truth.json"), encoding="utf-8"))["text"]
    for name in sorted(os.listdir(os.path.join(samples, "text"))):
        page_id, variant = name[:-4].rsplit("-", 1)
        start = time.perf_counter()
        out = engine(os.path.join(samples, "text", name))
        secs = time.perf_counter() - start
        hyp = " ".join(out.txts or ())
        print(json.dumps({"engine": "ppocrv6-" + size, "sample": page_id, "variant": variant,
                          "seconds": round(secs, 2), "cer": round(cer(truth[page_id], hyp), 4),
                          "wer": round(wer(truth[page_id], hyp), 4), "hyp_head": hyp[:120]}, ensure_ascii=False))


if __name__ == "__main__":
    if len(sys.argv) != 4:
        sys.exit(__doc__)
    main(*sys.argv[1:])
