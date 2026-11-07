#!/usr/bin/env python3
# SPDX-License-Identifier: AGPL-3.0-only
""""In hai mặt" on the real build, measured in the exported PDF: Party documents mirror their margins on the back
(05-HD/VPTW IV.4.2: front left 30 / right 15 mm, back left 15 / right 30 mm), ND30 documents keep them (Phụ lục I,
Phần I, Mục I, khoản 3: no back-page rule); the HST menu toggle switches an existing document back.

Usage: python3 tests/runtime/check-duplex-margins.py --display :131 [--instdir upstream/libreoffice/instdir] [--out DIR]
                                                     [--port 2198]
The display must already run; it is never started or stopped here. PDFs stay in --out. Exit 1 on failure.
"""
import argparse
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path[:0] = [HERE, os.path.join(os.path.dirname(os.path.dirname(HERE)), "extensions/hst-vietnamese-tools/python")]
import hst_gui  # noqa: E402
from templates_multipage_measure import pdf_lines  # noqa: E402

ROWS = []
TOLERANCE_MM = 1.0
# paragraphs of four lines or more: the full-width lines after the first show the margin (the first is indented)
BODY = "\n".join(("Nội dung đoạn %d của văn bản dùng để đo lề trang khi in hai mặt, đủ dài để căn đều hai bên. " % n) * 4
                 for n in range(1, 25))


def check(name, ok, detail=""):
    ROWS.append(bool(ok))
    print("%s  %s  %s" % ("PASS" if ok else "FAIL", name, str(detail)[:200]), flush=True)


def body_edges(page):
    """(left, right) in mm of the body text: the lines that run (almost) the full width, page number excluded."""
    lines = [ln for ln in page if ln["x1"] - ln["x0"] > 120]
    return (min(ln["x0"] for ln in lines), max(ln["x1"] for ln in lines)) if lines else (None, None)


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--display", required=True)
    parser.add_argument("--instdir", default=os.path.join(hst_gui.ROOT, "upstream/libreoffice/instdir"))
    parser.add_argument("--out", default=os.path.join(hst_gui.ROOT, "tests/output/duplex-margins"))
    parser.add_argument("--port", type=int, default=2198)
    args = parser.parse_args()
    out = os.path.abspath(args.out)
    os.makedirs(out, exist_ok=True)
    hst_gui.setup_uno(args.instdir)
    office = hst_gui.Office(args.instdir, os.path.join(out, "office"), args.port, display=args.display).start()
    try:
        import uno
        from com.sun.star.beans import PropertyValue
        from hst_office import nd30_duplex, nd30_layout, nd30_writer

        def export(doc, name):
            path = os.path.join(office.workdir, name + ".pdf")  # soffice runs as the build user: its own folder
            prop = PropertyValue()
            prop.Name, prop.Value = "FilterName", "writer_pdf_Export"
            doc.storeToURL(uno.systemPathToFileUrl(path), (prop,))
            return pdf_lines(path)

        def make(type_id, duplex):
            doc = office.load("private:factory/swriter", hidden=True)
            cursor = doc.getCurrentController().getViewCursor()
            layout = nd30_layout.build_layout(type_id, {"body": BODY})
            result = nd30_writer.insert_layout(doc, cursor, layout, apply_page=True, page_numbers=True)
            assert not result["blockers"], result
            nd30_duplex.apply(doc, cursor, duplex, layout["profile"])
            return doc, cursor

        for type_id, mirrored in (("dang-thong-bao", True), ("thong-bao", False), ("thong-tu", False)):
            for duplex in (False, True):
                doc, _cursor = make(type_id, duplex)
                pages = export(doc, "%s-%s" % (type_id, "hai-mat" if duplex else "mot-mat"))
                doc.close(True)
                front, back = body_edges(pages[0]), body_edges(pages[1]) if len(pages) > 1 else (None, None)
                want_back = (15.0, 210.0 - 30.0) if (duplex and mirrored) else (30.0, 210.0 - 15.0)
                check("%s, %s: front page left 30 / right 15 mm" % (type_id, "hai mặt" if duplex else "một mặt"),
                      front[0] is not None and abs(front[0] - 30) <= TOLERANCE_MM and abs(front[1] - 195) <= TOLERANCE_MM, front)
                check("%s, %s: back page left %.0f / right %.0f mm" % (type_id, "hai mặt" if duplex else "một mặt", want_back[0], 210 - want_back[1]),
                      back[0] is not None and abs(back[0] - want_back[0]) <= TOLERANCE_MM and abs(back[1] - want_back[1]) <= TOLERANCE_MM, back)
        # the HST menu toggle on an existing Party document: on, then off again
        doc, cursor = make("dang-thong-bao", False)
        on = nd30_duplex.toggle(doc, cursor)
        back_on = body_edges(export(doc, "dang-toggle-on")[1])
        off = nd30_duplex.toggle(doc, cursor)
        back_off = body_edges(export(doc, "dang-toggle-off")[1])
        doc.close(True)
        check("toggle on mirrors the back page", on["duplex"] and abs(back_on[0] - 15) <= TOLERANCE_MM, back_on)
        check("toggle off restores one layout", not off["duplex"] and abs(back_off[0] - 30) <= TOLERANCE_MM, back_off)
    finally:
        office.stop()
    print("PASS" if all(ROWS) else "FAIL", flush=True)
    return 0 if all(ROWS) else 1


if __name__ == "__main__":
    sys.exit(main())
