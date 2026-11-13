#!/usr/bin/env python3
# SPDX-License-Identifier: AGPL-3.0-only
"""The rule under the agency name at each length the ND30 wizard offers (1/3, 2/5, 1/2, as long as the line above, a
typed length in mm, one longer than the cell), measured in the exported PDF of the real build: as long as the layout
says, centred under the agency's text and inside the header cell (ND30 Phụ lục I, II.2b).

Usage: <office>/program/python tests/runtime/check-nd30-agency-rule.py --display :173 --instdir <instdir>
       [--out DIR] [--port 2309]
The display must already run; it is never started or stopped here. PDFs stay in --out. Exit 1 on failure.
"""
import argparse
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path[:0] = [HERE, os.path.join(os.path.dirname(os.path.dirname(HERE)), "extensions/hst-vietnamese-tools/python")]
import hst_gui  # noqa: E402
from template_layout_measure import horizontal_lines, words_by_page  # noqa: E402

ROWS = []
FIELDS = {"parentAgency": "Ủy ban nhân dân tỉnh Bắc Ninh", "agency": "Sở Tài nguyên và Môi trường tỉnh Bắc Ninh"}
CHOICES = ("1/3", "2/5", "1/2", "parent", "mm:30", "mm:400")
TOLERANCE_MM = 0.6


def check(name, ok, detail=""):
    ROWS.append(bool(ok))
    print("%s  %s  %s" % ("PASS" if ok else "FAIL", name, str(detail)[:240]), flush=True)


def agency_rule(layout):
    header = layout["blocks"][0]
    cell_mm = layout["textWidthMm"] * header["widthsPct"][0] / 100.0
    return next(p for p in header["rows"][0]["cells"][0] if p.get("role") == "Agency")["rule_mm"], cell_mm


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--display", required=True)
    parser.add_argument("--instdir", default=os.path.join(hst_gui.ROOT, "upstream/libreoffice/instdir"))
    parser.add_argument("--out", default=os.path.join(hst_gui.ROOT, "tests/output/nd30-agency-rule"))
    parser.add_argument("--port", type=int, default=2309)
    args = parser.parse_args()
    out = os.path.abspath(args.out)
    os.makedirs(out, exist_ok=True)
    hst_gui.setup_uno(args.instdir)
    office = hst_gui.Office(args.instdir, os.path.join(out, "office"), args.port, display=args.display).start()
    lengths = {}
    try:
        import uno
        from com.sun.star.beans import PropertyValue
        from hst_office import nd30_layout, nd30_rule_length, nd30_writer
        for choice in CHOICES:
            doc = office.load("private:factory/swriter", hidden=True)
            layout = nd30_layout.build_layout("cong-van", {**FIELDS, nd30_rule_length.FIELD: choice})
            want, cell_mm = agency_rule(layout)
            result = nd30_writer.insert_layout(doc, doc.getCurrentController().getViewCursor(), layout, apply_page=True,
                                               page_numbers=False)
            path = os.path.join(office.workdir, "agency-rule-%s.pdf" % choice.replace("/", "-").replace(":", ""))
            prop = PropertyValue()
            prop.Name, prop.Value = "FilterName", "writer_pdf_Export"
            doc.storeToURL(uno.systemPathToFileUrl(path), (prop,))
            doc.close(True)
            left_margin = 30.0  # ND30 default margins (apply_page)
            cell = (left_margin, left_margin + cell_mm)
            rules = [r for r in horizontal_lines(path, 1) if r[1] <= cell[1] + 0.5]
            rule = rules[0] if rules else None
            # the agency's last line: the words of the left cell just above the rule
            words = [w for w in words_by_page(path)[0] if rule and w["x1"] <= cell[1] + 0.5 and rule[2] - 9 < w["y1"] < rule[2]]
            text_centre = (min(w["x0"] for w in words) + max(w["x1"] for w in words)) / 2 if words else None
            name = "rule %s" % choice
            check(name + ": inserted, one rule in the agency cell", not result["blockers"] and rule is not None, (result["blockers"], rules))
            if rule is None:
                continue
            length = rule[1] - rule[0]
            lengths[choice] = length
            check(name + ": %.1f mm as the layout says" % want, abs(length - want) <= TOLERANCE_MM, round(length, 2))
            check(name + ": centred under the agency text", text_centre is not None and abs((rule[0] + rule[1]) / 2 - text_centre) <= 1.0,
                  (rule, text_centre))
            check(name + ": inside the cell", rule[0] >= cell[0] - 0.3 and rule[1] <= cell[1] + 0.3, (rule, cell))
        check("1/3 < 2/5 < 1/2", lengths.get("1/3", 0) < lengths.get("2/5", 0) < lengths.get("1/2", 0), lengths)
    finally:
        office.stop()
    print("PASS" if all(ROWS) else "FAIL", flush=True)
    return 0 if all(ROWS) else 1


if __name__ == "__main__":
    sys.exit(main())
