# SPDX-License-Identifier: AGPL-3.0-only
"""Test documents for check-template-layout.py: fictional content only, real templates and the real renderer."""
import os

from hst_office import nd30, nd30_layout, nd30_writer
import template_layout_measure as measure

FILLER = "Đo kiểm bố cục văn bản hành chính. Dòng nội dung này dùng để kiểm tra lề trang, khoảng cách dòng và vị trí số trang khi văn bản kéo dài qua nhiều trang."
LONG = {"parentAgency": "Ủy ban nhân dân tỉnh Ví Dụ", "agency": "Sở Khoa học và Công nghệ tỉnh Ví Dụ phục vụ thử nghiệm",
        "number": "5", "symbol": "SKHCN-VP", "place": "Thành phố Ví Dụ", "date": "05/02/2026", "summary": "Thử nghiệm trình bày văn bản nhiều trang có trích yếu đủ dài để xuống hai dòng trong vùng trình bày",
        "kinhGui": "Văn phòng Ủy ban nhân dân tỉnh Ví Dụ\nCác sở, ban, ngành thuộc tỉnh Ví Dụ", "signerAuthority": "KT. Giám đốc",
        "signerTitle": "Phó Giám đốc", "signerName": "Nguyễn Văn Mẫu", "secretaryName": "Trần Thị Thử",
        "recipients": "Như trên\nBan Giám đốc\nCác phòng, ban chuyên môn"}
SHORT = {"agency": "Sở A", "number": "12", "symbol": "SA", "place": "Tỉnh A", "date": "2026-11-05", "summary": "Thử nghiệm",
         "kinhGui": "Sở B", "signerAuthority": "Giám đốc", "signerName": "Lê Mẫu", "body": "Nội dung ngắn."}


def _body_top_profile(profile_data):
    return {**profile_data, "bodyTopMm": profile_data["marginRangesMm"]["top"]}


def _ott_doc(path, filler):
    def open_doc(desktop, prop):
        doc = desktop.loadComponentFromURL("file://" + path, "_blank", 0, (prop("Hidden", True), prop("AsTemplate", True)))
        if filler:
            text = doc.getText()
            elements, previous = text.createEnumeration(), None
            while elements.hasMoreElements():  # the last paragraph before the signature table
                element = elements.nextElement()
                if element.supportsService("com.sun.star.text.TextTable"):
                    if element.getName().startswith("Signature"):
                        break
                else:
                    previous = element
            cursor = text.createTextCursorByRange(previous.getEnd())
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
        result = nd30_writer.insert_layout(doc, cursor, layout, apply_page=True, page_numbers=True)
        if result["blockers"]:
            raise RuntimeError(result["blockers"])
        return doc
    return open_doc


def writer_types():
    return [t for t in nd30.rules()["documentTypes"] if t.get("module", "writer") == "writer"]


def all_cases(templates, only):
    catalog = {e["id"]: e for e in __import__("json").load(open(os.path.join(templates, "manifest.json"), encoding="utf-8"))["templates"]}
    long_body = "\n".join("%02d. %s" % (i + 1, FILLER) for i in range(70))
    for t in writer_types():
        ident = t["id"]
        if only and ident not in only:
            continue
        data = _body_top_profile(nd30.profile_rules(t["profile"]))
        common = {"profile": data, "type": t, "checkNumberRow": not t.get("noDate")}
        if ident in catalog:
            yield {**common, "name": ident + "-ott", "multipage": True, "open": _ott_doc(os.path.join(templates, catalog[ident]["output"]), True),
                   "ruleSource": None}
        yield {**common, "name": ident + "-wizard-long", "multipage": True, "open": _wizard_doc(ident, {**LONG, "body": long_body}), "ruleSource": LONG}
        yield {**common, "name": ident + "-wizard-short", "multipage": False, "open": _wizard_doc(ident, SHORT), "ruleSource": SHORT}


def check_rules(case, pdf):
    """The motto rule is as long as the motto; the rule under the agency is 1/3-1/2 of its line (measured, not computed)."""
    fails = []
    rules = measure.rules_on_page_one(pdf)
    data = case["profile"]
    motto = measure.line_extent(pdf, data["motto"][:6]) if data.get("motto") else None
    if not rules or not motto:
        return fails
    width = motto[1] - motto[0]
    candidates = [r for r in rules if abs((r[0] + r[1]) / 2 - (motto[0] + motto[1]) / 2) < 2]
    if not candidates or abs((candidates[0][1] - candidates[0][0]) - width) > 0.5:
        fails.append("motto rule %s against line %.2f" % (candidates[:1], width))
    return fails
