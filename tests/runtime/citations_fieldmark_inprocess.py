# SPDX-License-Identifier: AGPL-3.0-only
"""In-process timing of the citation scan and updates, as the extension will run them.

citations_fieldmark_perf.py copies this file into the test profile's user Python scripts and
calls time_citations(doc, runtime_dir) through the script provider, so the work runs inside the
office process without the UNO pipe in between. Returns a JSON string of timings in seconds.
"""
import json
import sys
import time


def time_citations(doc, runtime_dir):
    if runtime_dir not in sys.path:
        sys.path.insert(0, runtime_dir)
    import uno
    from citations_fieldmark_uno import BIBLIOGRAPHY_PREFIX, CITATION_PREFIX, Session, reading_order, scan

    ctx = uno.getComponentContext()
    session = Session(ctx, doc)
    timings = {}

    start = time.perf_counter()
    fields = scan(doc)
    for field in fields:  # reading every result is part of a scan
        field.result
    timings["scan_s"] = time.perf_counter() - start

    cites = [f for f in fields if f.code.startswith(CITATION_PREFIX)]
    start = time.perf_counter()
    reading_order(doc, cites)
    timings["reading_order_s"] = time.perf_counter() - start

    updates = [(f.code, "[%d]" % (i + 3)) for i, f in enumerate(cites)]
    start = time.perf_counter()
    session.bulk_update(CITATION_PREFIX, updates)
    timings["update_citations_s"] = time.perf_counter() - start

    bib = [f for f in fields if f.code.startswith(BIBLIOGRAPHY_PREFIX)]
    entries = bib[0].result.count("\n") + 1 if bib else 0
    html = "".join(f"<p>[{k + 1}] Lê Văn Trong {k} (2012), <i>Sách {k}</i>.</p>" for k in range(entries))
    start = time.perf_counter()
    if bib:
        session.bulk_update(BIBLIOGRAPHY_PREFIX, [(bib[0].code, html)])
    timings["update_bibliography_s"] = time.perf_counter() - start

    timings["fields"] = len(fields)
    timings["applied"] = [f.result for f in scan(doc, CITATION_PREFIX)] == [r for _, r in updates]
    return json.dumps(timings)


g_exportedScripts = (time_citations,)
