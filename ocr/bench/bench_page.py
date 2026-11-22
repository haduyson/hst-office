# SPDX-License-Identifier: LicenseRef-HST-Proprietary
"""Whole-page benchmark (mode "page": layout + text + formulas + tables) on SAMPLES/page.

Usage: taskset -c 0,1 python3 bench_page.py SAMPLES > results.jsonl   (HST_OCR_HOME with layout, formula, tessdata)
Scores: block types in the right order, text CER over all paragraphs, formula exact match, table shape and cells.
"""
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path[:0] = [HERE, os.path.join(HERE, "..", "core")]
from hst_ocr import pipeline  # noqa: E402
from metrics import cer, formula_scores, table_scores  # noqa: E402


def main(samples):
    truth = json.load(open(os.path.join(samples, "truth.json"), encoding="utf-8"))["page"]
    for name in sorted(os.listdir(os.path.join(samples, "page"))):
        pid, variant = name[:-4].rsplit("-", 1)
        resp = pipeline.run({"version": 1, "image": os.path.abspath(os.path.join(samples, "page", name)),
                             "mode": "page", "threads": 2})
        if not resp["ok"]:
            print(json.dumps({"sample": pid, "variant": variant, "error": resp["error"]}))
            continue
        want, got = truth[pid], resp["blocks"]
        text_t = " ".join(b["text"] for b in want if b["type"] == "paragraph")
        text_h = " ".join(b["text"] for b in got if b["type"] == "paragraph")
        f_t = [b["latex"] for b in want if b["type"] == "formula"]
        f_h = [b["latex"] for b in got if b["type"] == "formula"]
        t_t = [b["rows"] for b in want if b["type"] == "table"]
        t_h = [b["rows"] for b in got if b["type"] == "table"]
        print(json.dumps({
            "sample": pid, "variant": variant, "seconds": round(resp["timings_ms"]["total"] / 1000, 2),
            "layout_seconds": round(resp["timings_ms"].get("layout", 0) / 1000, 2),
            "types_ok": [b["type"] for b in want] == [b["type"] for b in got],
            "text_cer": round(cer(text_t, text_h), 4),
            "formulas_exact": sum(formula_scores(a, b)[1] for a, b in zip(f_t, f_h)), "formulas": len(f_t),
            "tables_shape_ok": sum(table_scores(a, b)[0] for a, b in zip(t_t, t_h)), "tables": len(t_t),
            "table_cells_exact": [round(table_scores(a, b)[2], 3) for a, b in zip(t_t, t_h)],
        }), flush=True)


if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    main(sys.argv[1])
