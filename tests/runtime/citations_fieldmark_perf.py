# SPDX-License-Identifier: AGPL-3.0-only
"""Thesis-sized timing: about 200 pages, 300 citations (every 30th in a footnote) and one
150-entry bibliography. Times listing, ordering, renumbering every citation in one command and
rewriting the bibliography, then checks a .docx save keeps every field. Timings are taken over the
UNO pipe from a separate process, so the extension (in-process Python) will be faster."""
import time

from citations_fieldmark_uno import (BIBLIOGRAPHY_PREFIX, CITATION_PREFIX, MARKER, Session, prop,
                                     reading_order, scan)

PARAGRAPHS = 1650  # about 200 A4 pages in the default Times New Roman 12
SENTENCE = ("Kết quả nghiên cứu cho thấy chính sách tiền tệ có tác động rõ rệt tới tăng trưởng "
            "kinh tế trong giai đoạn khảo sát, đặc biệt ở khu vực doanh nghiệp vừa và nhỏ. ")


def build(session, citations, entries):
    text = session.doc.getText()
    cursor = text.createTextCursor()
    every = PARAGRAPHS // citations
    for i in range(PARAGRAPHS):
        marker = f" {MARKER}" if i % every == 0 and i // every < citations else ""
        text.insertString(cursor, SENTENCE * 3 + marker, False)
        text.insertControlCharacter(cursor, 0, False)
    start = time.perf_counter()
    for n, rng in enumerate(session.markers()):
        code = CITATION_PREFIX + '{"v":1,"citationID":"p%d","items":[{"id":"item-%d"}]}' % (n, n % entries)
        session.insert_field(rng, code, "[%d]" % (n % entries + 1), "Footnote" if n % 30 == 29 else None)
    inserted = time.perf_counter() - start
    bib = "".join(f"<p>[{k + 1}] Nguyễn Văn Tác Giả {k} (2010), <i>Tên sách {k}</i>, Nxb Giáo dục.</p>"
                  for k in range(entries))
    session.insert_field(text.getEnd(), BIBLIOGRAPHY_PREFIX + ' {"v":1}', bib)
    session.drop_markers()
    return inserted


def timed(fn):
    start = time.perf_counter()
    value = fn()
    return value, time.perf_counter() - start


def in_process(ctx, doc, out):
    """Run citations_fieldmark_inprocess.time_citations inside the office (see that file)."""
    import json
    import os
    import shutil
    here = os.path.dirname(os.path.abspath(__file__))
    scripts = os.path.join(out, "profile", "user", "Scripts", "python")
    os.makedirs(scripts, exist_ok=True)
    shutil.copy(os.path.join(here, "citations_fieldmark_inprocess.py"), scripts)
    factory = ctx.ServiceManager.createInstanceWithContext(
        "com.sun.star.script.provider.MasterScriptProviderFactory", ctx)
    script = factory.createScriptProvider("").getScript(
        "vnd.sun.star.script:citations_fieldmark_inprocess.py$time_citations?language=Python&location=user")
    return json.loads(script.invoke((doc, here), (), ())[0])


def run(rec, ctx, desktop, out, citations=300, entries=150):
    import uno
    doc = desktop.loadComponentFromURL("private:factory/swriter", "_blank", 0, (prop("Hidden", True),))
    try:
        session = Session(ctx, doc)
        inserted = build(session, citations, entries)
        pages = doc.getCurrentController().PageCount
        rec.info("perf-document", {"pages": pages, "citations": citations, "entries": entries,
                                   "insert_all_over_pipe_s": round(inserted, 2)})
        rec.check("perf-pages", pages >= 190, pages)
        timing = in_process(ctx, doc, out)
        rec.info("perf-in-process", {k: round(v, 3) if isinstance(v, float) else v for k, v in timing.items()})
        rec.check("perf-in-process-updates-applied", timing["applied"] and timing["fields"] == citations + 1, timing["fields"])
        rec.check("perf-scan-le-0.5s", timing["scan_s"] <= 0.5, round(timing["scan_s"], 3))
        rec.check("perf-update-300-le-2s", timing["update_citations_s"] <= 2.0, round(timing["update_citations_s"], 3))
        rec.check("perf-bibliography-150-le-2s", timing["update_bibliography_s"] <= 2.0,
                  round(timing["update_bibliography_s"], 3))
        unchanged = timing["scan_s"] + timing["reading_order_s"]  # nothing to apply: scan and order only
        rec.check("perf-unchanged-le-0.6s", unchanged <= 0.6, round(unchanged, 3))
        cites, t_scan = timed(lambda: [f for f in scan(doc, CITATION_PREFIX) if f.result])
        _, t_order = timed(lambda: reading_order(doc, cites))
        rec.info("perf-over-pipe", {"scan_s": round(t_scan, 3), "reading_order_s": round(t_order, 3)})
        path = f"{out}/perf-300.docx"
        _, t_save = timed(lambda: doc.storeToURL(uno.systemPathToFileUrl(path), (prop("FilterName", "MS Word 2007 XML"),)))
        rec.info("perf-save-docx-s", round(t_save, 2))
    finally:
        doc.close(True)
    reopened, t_load = timed(lambda: desktop.loadComponentFromURL(uno.systemPathToFileUrl(path), "_blank", 0,
                                                                  (prop("Hidden", True),)))
    try:
        again = scan(reopened)
        rec.check("perf-docx-reload-keeps-all", len(again) == citations + 1, len(again))
        rec.info("perf-load-docx-s", round(t_load, 2))
    finally:
        reopened.close(True)
