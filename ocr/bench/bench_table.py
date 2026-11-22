# SPDX-License-Identifier: LicenseRef-HST-Proprietary
"""Table benchmark on SAMPLES/table: the core's ruling-line grid (no model) and, for comparison, SLANet-plus
(RapidTable ONNX; licence RISK, see the report) for structure. Cell text is Tesseract in both cases.

Usage: taskset -c 0,1 python3 bench_table.py SAMPLES SLANET_ONNX > results.jsonl
"""
import json
import os
import re
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path[:0] = [HERE, os.path.join(HERE, "..", "core")]
from hst_ocr import imaging, table_grid  # noqa: E402
from metrics import table_scores  # noqa: E402


def slanet_shape(engine, path):
    """Rows of the predicted HTML as lists of '' (structure only), honouring colspan."""
    out = engine(path)
    html = out.pred_htmls[0] if out.pred_htmls else ""
    rows = []
    for tr in re.findall(r"<tr>(.*?)</tr>", html, re.S):
        cols = 0
        for td in re.findall(r"<td([^>]*)>", tr):
            span = re.search(r'colspan="(\d+)"', td)
            cols += int(span.group(1)) if span else 1
        rows.append([""] * cols)
    return rows


def main(samples, slanet):
    truth = json.load(open(os.path.join(samples, "truth.json"), encoding="utf-8"))["table"]
    engine = None
    if os.path.isfile(slanet):
        from rapid_table import ModelType, RapidTable, RapidTableInput
        engine = RapidTable(RapidTableInput(model_type=ModelType.SLANETPLUS, model_dir_or_path=slanet, use_ocr=False,
                                            engine_cfg={"intra_op_num_threads": 2, "inter_op_num_threads": 1}))
    for name in sorted(os.listdir(os.path.join(samples, "table"))):
        tid, variant = name[:-4].rsplit("-", 1)
        path = os.path.join(samples, "table", name)
        start = time.perf_counter()
        result = table_grid.cells(imaging.load(path), threads=2)
        secs = time.perf_counter() - start
        rows = result["rows"] if result else []
        shape, cell_cer, exact = table_scores(truth[tid], rows)
        rec = {"engine": "grid+tesseract", "sample": tid, "variant": variant, "seconds": round(secs, 2),
               "shape_ok": shape, "cell_cer": round(cell_cer, 4), "cells_exact": round(exact, 3), "rows": rows}
        print(json.dumps(rec, ensure_ascii=False), flush=True)
        if engine is not None:
            start = time.perf_counter()
            shape_rows = slanet_shape(engine, path)
            secs = time.perf_counter() - start
            t = truth[tid]
            ok = len(t) == len(shape_rows) and all(len(a) == len(b) for a, b in zip(t, shape_rows))
            print(json.dumps({"engine": "slanet-plus(structure)", "sample": tid, "variant": variant,
                              "seconds": round(secs, 2), "shape_ok": ok,
                              "shape": [len(r) for r in shape_rows]}), flush=True)


if __name__ == "__main__":
    if len(sys.argv) != 3:
        sys.exit(__doc__)
    main(*sys.argv[1:])
