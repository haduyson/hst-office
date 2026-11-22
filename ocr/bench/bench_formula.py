# SPDX-License-Identifier: LicenseRef-HST-Proprietary
"""Formula benchmark: pix2tex (core) and Pix2Text MFR (comparison) on SAMPLES/formula.

Reports token error rate, exact match (after normalisation) and whether HST's own TeX → Công thức converter
(extensions/hst-vietnamese-tools/python/hst_office/tex_to_starmath.py, the engine of "Chuyển TeX ⇄ công thức")
accepts the output, plus seconds per formula. Usage:
  taskset -c 0,1 python3 bench_formula.py SAMPLES MFR_MODEL_DIR > results.jsonl   (HST_OCR_HOME has models/formula)
"""
import json
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", ".."))
sys.path[:0] = [HERE, os.path.join(HERE, "..", "core"),
                os.path.join(REPO, "extensions", "hst-vietnamese-tools", "python")]
from hst_ocr import formula_pix2tex, imaging  # noqa: E402
from metrics import formula_scores  # noqa: E402


def converts(latex):
    from hst_office import tex_to_starmath
    try:
        tex_to_starmath.convert(latex, display=True)
        return True
    except Exception:  # noqa: BLE001 - any converter failure counts as "would stay text, highlighted"
        return False


def main(samples, mfr_dir):
    from formula_mfr import Mfr
    truth = json.load(open(os.path.join(samples, "truth.json"), encoding="utf-8"))["formula"]
    engines = {"pix2tex": lambda img: formula_pix2tex.recognize(img, threads=2)}
    if os.path.isdir(mfr_dir):
        mfr = Mfr(mfr_dir, threads=2)
        engines["p2t-mfr-1.5"] = mfr
    for label, engine in engines.items():
        engine(imaging.load(os.path.join(samples, "formula", "f00-clean.png")))  # warm-up: model load not timed
        for name in sorted(os.listdir(os.path.join(samples, "formula"))):
            fid, variant = name[:-4].rsplit("-", 1)
            img = imaging.load(os.path.join(samples, "formula", name))
            start = time.perf_counter()
            hyp = engine(img)
            secs = time.perf_counter() - start
            ter, exact = formula_scores(truth[fid], hyp)
            print(json.dumps({"engine": label, "sample": fid, "variant": variant, "seconds": round(secs, 3),
                              "ter": round(ter, 4), "exact": exact, "converts": converts(hyp),
                              "truth": truth[fid], "hyp": hyp}, ensure_ascii=False), flush=True)


if __name__ == "__main__":
    if len(sys.argv) != 3:
        sys.exit(__doc__)
    main(*sys.argv[1:])
