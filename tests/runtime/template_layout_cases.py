# SPDX-License-Identifier: AGPL-3.0-only
"""Test documents for check-template-layout.py: fictional content only, real templates and the real renderer."""
import os

from hst_office import nd30, nd30_layout, nd30_writer
import template_layout_measure as measure
import templates_multipage_fill

FILLER = "Đo kiểm bố cục văn bản hành chính. Dòng nội dung này dùng để kiểm tra lề trang, khoảng cách dòng và vị trí số trang khi văn bản kéo dài qua nhiều trang."
LONG = {"parentAgency": "Ủy ban nhân dân tỉnh Ví Dụ", "agency": "Sở Khoa học và Công nghệ tỉnh Ví Dụ phục vụ thử nghiệm",
        "number": "5", "symbol": "SKHCN-VP", "place": "Thành phố Ví Dụ", "date": "05/02/2026", "summary": "Thử nghiệm trình bày văn bản nhiều trang có trích yếu đủ dài để xuống hai dòng trong vùng trình bày",
        "kinhGui": "Văn phòng Ủy ban nhân dân tỉnh Ví Dụ\nCác sở, ban, ngành thuộc tỉnh Ví Dụ", "signerAuthority": "KT. Giám đốc",
        "signerTitle": "Phó Giám đốc", "signerName": "Nguyễn Văn Mẫu", "secretaryName": "Trần Thị Thử",
        "recipients": "Như trên\nBan Giám đốc\nCác phòng, ban chuyên môn"}
SHORT = {"agency": "Sở A", "number": "12", "symbol": "SA", "place": "Tỉnh A", "date": "2026-11-05", "summary": "Thử nghiệm",
         "kinhGui": "Sở B", "signerAuthority": "Giám đốc", "signerName": "Lê Mẫu", "body": "Nội dung ngắn."}


def _body_top_profile(profile_data, copy_rule=False):
    """Where the first glyph may start: the top margin, plus the ink offset, plus the extra leading of a fixed line height."""
    top = profile_data["defaultMarginsMm"]["top"]
    typography = profile_data["typography"]
    leading = max(0.0, typography.get("lineExactPt", 0) - 1.107 * typography["body"]) * 25.4 / 72
    return {**profile_data, "bodyTopMm": [top, top + 0.3 + leading + 1.5 * copy_rule]}


def _ott_doc(path, filler, ruled=False):
    """The template with 70 filler paragraphs before its signature; a ruled form (an office form of the van-thu group)
    grows by 70 table rows instead, the way the multi-page check and a user fill it."""
    def open_doc(desktop, prop):
        doc = desktop.loadComponentFromURL("file://" + path, "_blank", 0, (prop("Hidden", True), prop("AsTemplate", True)))
        rows = templates_multipage_fill.filler_for(templates_multipage_fill.Document(doc), "Body", True) if filler and ruled else None
        if rows is not None and rows.table is not None:
            for _ in range(70):
                rows.add()
        elif filler:
            text = doc.getText()
            elements, previous = text.createEnumeration(), None
            while elements.hasMoreElements():  # the last text paragraph before the signature table (not the gap above it)
                element = elements.nextElement()
                if element.supportsService("com.sun.star.text.TextTable"):
                    if element.getName().startswith("Signature"):
                        break
                elif not element.ParaStyleName.startswith("TableGap"):
                    previous = element
            cursor = text.createTextCursorByRange(previous.getEnd() if previous else text.getEnd())
            for index in range(70):
                text.insertControlCharacter(cursor, 0, False)
                text.insertString(cursor, "%02d. %s" % (index + 1, FILLER), False)
        return doc
    return open_doc


def _wizard_doc(type_id, fields):
    def open_doc(desktop, prop):
        doc = desktop.loadComponentFromURL("private:factory/swriter", "_blank", 0, (prop("Hidden", True),))
        layout = nd30_layout.build_layout(type_id, fields)
        cursor = doc.getCurrentController().getViewCursor()
        if layout.get("flow"):  # a copy goes on the document being copied
            source = "dang-thong-bao" if layout["profile"] == "dang" else "thong-bao"
            first = nd30_layout.build_layout(source, {"body": fields.get("body", "Nội dung ngắn.")})
            nd30_writer.insert_layout(doc, cursor, first, apply_page=True, page_numbers=True)
            layout = nd30_layout.build_layout(type_id, {**fields, "body": "Bản sao."})
            if layout["flow"] == "append":
                layout["blocks"] = [b for b in layout["blocks"] if b.get("role") != "Body"]  # the document above is the original
        result = nd30_writer.insert_layout(doc, cursor, layout, apply_page=True, page_numbers=True)
        if result["blockers"]:
            raise RuntimeError(result["blockers"])
        return doc
    return open_doc


def _footer_text(type_id, fields, template):
    """The first-page footer (contact details of an official letter) the renderers write for these fields, or None."""
    _blocks, footer = nd30_layout.portable_blocks(nd30_layout.build_layout(type_id, fields, template=template))
    return " ".join("".join(r["text"] for r in b["runs"]) for b in footer) or None


def writer_types():
    return [t for t in nd30.rules()["documentTypes"] if t.get("module", "writer") == "writer"]


def _paged(t):
    """Forms with their own paper or a single box do not run over pages."""
    return t["structure"] not in ("envelope", "stamp")


def all_cases(templates, only):
    catalog = {e["id"]: e for e in __import__("json").load(open(os.path.join(templates, "manifest.json"), encoding="utf-8"))["templates"]}
    long_body = "\n".join("%02d. %s" % (i + 1, FILLER) for i in range(70))
    for t in writer_types():
        ident = t["id"]
        if only and ident not in only:
            continue
        paged = _paged(t)
        data = _body_top_profile(nd30.profile_rules(t["profile"]), t["structure"] in ("copy", "dang-copy"))  # a copy may open a page with its rule
        common = {"profile": data, "type": t, "checkNumberRow": not t.get("noDate") and not t.get("noNumber") and not t.get("noHeader") and t["structure"] not in ("annex", "attached-only", "esign-copy", "stamp", "envelope"), "paged": paged}
        if ident in catalog:
            # the Party copy template holds only the copy form, whose number and date are numbered list items
            yield {**common, "checkNumberRow": common["checkNumberRow"] and t["structure"] != "dang-copy", "name": ident + "-ott", "multipage": paged, "open": _ott_doc(os.path.join(templates, catalog[ident]["output"]), paged,
                                                                        catalog[ident]["output"].startswith("van-thu/")),
                   "ruleSource": None, "footer": _footer_text(ident, {}, True), "rules": _header_rules(ident, {}, True), "titleRules": _title_rules(ident, {}, True)}
        if not paged:
            yield {**common, "name": ident + "-wizard-short", "multipage": False, "open": _wizard_doc(ident, {}), "ruleSource": SHORT,
                   "footer": _footer_text(ident, {}, False), "rules": _header_rules(ident, {}, False), "titleRules": _title_rules(ident, {}, False)}
            continue
        long_fields = {**LONG, "body": long_body}
        yield {**common, "name": ident + "-wizard-long", "multipage": True, "open": _wizard_doc(ident, long_fields), "ruleSource": LONG,
               "footer": _footer_text(ident, long_fields, False), "rules": _header_rules(ident, long_fields, False), "titleRules": _title_rules(ident, long_fields, False)}
        yield {**common, "name": ident + "-wizard-short", "multipage": False, "open": _wizard_doc(ident, SHORT), "ruleSource": SHORT,
               "footer": _footer_text(ident, SHORT, False), "rules": _header_rules(ident, SHORT, False), "titleRules": _title_rules(ident, SHORT, False)}


def _layout_blocks(type_id, fields, template):
    return nd30_layout.portable_blocks(nd30_layout.build_layout(type_id, fields, template=template))[0]


def _header_rules(type_id, fields, template):
    """(text, column) of the ruled paragraphs in the first header block the renderers write: the agency (column 0) and
    the motto or the Party name (column 1). [] when the type has no such header."""
    header = next((b for b in _layout_blocks(type_id, fields, template) if b["type"] == "grid" and b.get("name") == "Header"), None)
    if header is None:
        return []
    return [("".join(r["text"] for r in p["runs"]), column) for row in header["rows"]
            for column, cell in enumerate(row["cells"]) for p in cell if p.get("rule_mm")]


def _title_rules(type_id, fields, template):
    """(text, length mm) of the ruled title, summary and subtitle paragraphs, in document order. The length is the
    generator's own: nd30_heading sizes it with nd30_metrics.rule_for from the text it measures (the summary for a
    rule under a subtitle), and build_layout carries the result as rule_mm."""
    return [("".join(r["text"] for r in b["runs"]), b["rule_mm"]) for b in _layout_blocks(type_id, fields, template)
            if b["type"] == "paragraph" and b.get("rule_mm")]


def _ruled(lines, rules, text, after=-1.0):
    """(rule, lines of its paragraph) for the first paragraph starting with `text` below `after` mm, or an error."""
    words = " ".join(text.split())
    own = [ln for ln in lines if ln["y0"] > after and len(ln["text"]) >= 4
           and (words.startswith(ln["text"][:12]) or ln["text"].startswith(words[:12]))]
    if not own:
        return None, "ruled line %r not found" % words[:40]
    first = min(own, key=lambda ln: ln["y0"])
    centre = (first["x0"] + first["x1"]) / 2
    below = [r for r in rules if r[2] > first["y1"] - 0.5 and abs((r[0] + r[1]) / 2 - centre) < 15]
    if not below:
        return None, "no rule under %r" % words[:40]
    rule = min(below, key=lambda r: r[2])
    return (rule, [ln for ln in lines if first["y0"] - 0.5 <= ln["y0"] and ln["y1"] <= rule[2] + 0.5
                   and abs((ln["x0"] + ln["x1"]) / 2 - centre) < 15]), None


def _centred(rule, line, label):
    if abs((rule[0] + rule[1]) / 2 - (line["x0"] + line["x1"]) / 2) > 0.5:
        return ["rule under %r not centred: %s against line %.2f-%.2f" % (label, rule[:2], line["x0"], line["x1"])]
    return []


def check_rules(case, pdf):
    """Every rule, measured in the PDF and centred (±0.5 mm) under its paragraph; a rule or line that is expected and
    not found fails (Decree 30, Annex I).
    - Page-1 header: under the motto and the Party name as long as the line; under the agency 1/3 to 1/2 of its longest
      line (measured against the text, not computed).
    - Title, summary and subtitle rules on any page, in document order: the length the generator computed (±0.5 mm)."""
    fails = []
    rules, lines = measure.horizontal_lines(pdf, 1), measure.text_lines(pdf, 1)
    for text, column in case["rules"]:
        found, error = _ruled(lines, rules, text)
        if error:
            fails.append(error + " on page 1")
            continue
        rule, block = found
        line = max(block, key=lambda ln: ln["x1"] - ln["x0"])
        width, length, label = line["x1"] - line["x0"], rule[1] - rule[0], " ".join(text.split())[:30]
        fails += _centred(rule, line, label)
        if column == 1 and abs(length - width) > 0.5:
            fails.append("rule under %r is %.2f mm, its line %.2f mm" % (label, length, width))
        if column == 0 and not width / 3 - 0.5 <= length <= width / 2 + 0.5:
            fails.append("rule under %r is %.2f mm, not 1/3-1/2 of its line %.2f mm" % (label, length, width))
    if not case["titleRules"]:
        return fails
    page, after, pages = 1, -1.0, measure.page_count(pdf)
    cache = {}
    for text, expected in case["titleRules"]:
        label, found = " ".join(text.split())[:30], None
        while page <= pages:
            if page not in cache:
                cache[page] = (measure.horizontal_lines(pdf, page), measure.text_lines(pdf, page))
            found, _error = _ruled(cache[page][1], cache[page][0], text, after)
            if found:
                break
            page, after = page + 1, -1.0
        if not found:
            fails.append("ruled title %r or its rule not found" % label)
            break
        rule, block = found
        after = rule[2]
        fails += _centred(rule, max(block, key=lambda ln: ln["x1"] - ln["x0"]), label)
        if abs((rule[1] - rule[0]) - expected) > 0.5:
            fails.append("rule under %r on page %d is %.2f mm, the generator's %.2f mm" % (label, page, rule[1] - rule[0], expected))
    return fails
