# SPDX-License-Identifier: AGPL-3.0-only
"""Runtime ND30 checks: insert at cursor, one undo step, page margins, refusals, save .odt/.docx and reopen."""
import json
import os

import uno

from lo_session import props

EXPECTED_MARGINS_MM = {"Left": 30.0, "Right": 15.0, "Bottom": 20.0}


def full_text(doc):
    """Body paragraphs plus every table cell, in document order (a cursor string skips leading tables)."""
    parts, enum = [], doc.getText().createEnumeration()
    while enum.hasMoreElements():
        element = enum.nextElement()
        if element.supportsService("com.sun.star.text.TextTable"):
            parts += [element.getCellByName(n).getString() for n in element.getCellNames()]
        else:
            parts.append(element.getString())
    return "\n".join(parts)


def page_summary(doc):
    style = doc.getStyleFamilies().getByName("PageStyles").getByName(doc.getText().createTextCursor().PageStyleName)
    body_top = style.TopMargin + (style.HeaderHeight + style.HeaderBodyDistance if style.HeaderIsOn else 0)
    return {"Width": style.Width / 100, "Height": style.Height / 100, "Left": style.LeftMargin / 100, "Right": style.RightMargin / 100,
            "Bottom": style.BottomMargin / 100, "BodyTop": body_top / 100, "Header": style.HeaderIsOn, "FirstShared": style.FirstIsShared}


def near(a, b):
    return abs(a - b) <= 0.06  # 1/100 mm rounding in the document model and docx twips


def docx_margins_twips(path):
    """Page margins as Word sees them, read straight from word/document.xml (independent of LibreOffice's model)."""
    import re
    import zipfile
    xml = zipfile.ZipFile(path).read("word/document.xml").decode("utf-8")
    tag = re.search(r"<w:pgMar [^>]*>", xml).group(0)
    return {k: int(v) for k, v in re.findall(r'w:(top|bottom|left|right|header)="(-?\d+)"', tag)}


def check_layout(rec, label, doc, case, expect_page):
    text = full_text(doc)
    missing = [line for line in case["expectLines"] if line not in text]
    rec.check(label + ": expected text present", not missing, missing)
    page = page_summary(doc)
    if expect_page:
        ok = near(page["Width"], 210) and near(page["Height"], 297) and all(near(page[k], v) for k, v in EXPECTED_MARGINS_MM.items()) and near(page["BodyTop"], 20)
        rec.check(label + ": A4 + ND30 margins", ok, page)
    return page


def insert(session, doc, type_id, fields, apply_page=True, page_numbers=True):
    return json.loads(session.macro("insert_nd30", doc, session.installed_python_dir(), type_id, json.dumps(fields), apply_page, page_numbers))


def run(rec, session, fixtures, out):
    cases = json.load(open(os.path.join(fixtures, "nd30-cases.json"), encoding="utf-8"))["layouts"]
    case = cases[0]
    doc = session.new_doc("swriter")
    try:
        view = doc.getCurrentController().getViewCursor()
        um = doc.getUndoManager()
        # margins only: pre-existing undo history survives, page style change itself is not undoable
        doc.getText().insertString(doc.getText().createTextCursor(), "x", False)
        doc.getText().setString("")
        history = len(um.getAllUndoActionTitles())
        res = insert(session, doc, case["typeId"], case["fields"], page_numbers=False)
        rec.check("margins-only insert: no blockers, history kept", res["blockers"] == [] and not res["page"]["undoHistoryCleared"] and history > 0, res)
        rec.check("margins-only: undo history preserved + one new step", len(um.getAllUndoActionTitles()) == history + 1, um.getAllUndoActionTitles())
        um.undo()
        rec.check("margins-only: one undo empties document", full_text(doc) == "" and doc.getTextTables().getCount() == 0)
        um.redo()
        check_layout(rec, "margins-only redo", doc, case, True)
        doc.close(True)
        doc = session.new_doc("swriter")
        view = doc.getCurrentController().getViewCursor()
        um = doc.getUndoManager()
        res = insert(session, doc, case["typeId"], case["fields"])
        rec.check("insert: no blockers", res["blockers"] == [], res)
        rec.check("insert with page numbers reports cleared history", res["page"]["undoHistoryCleared"] and not res["page"]["headerSkipped"], res)
        check_layout(rec, "insert", doc, case, True)
        rec.check("insert: exactly one undo action", um.getAllUndoActionTitles() == ("Insert ND30 document",), um.getAllUndoActionTitles())
        rec.check("insert: header shows page number, first page differs", page_summary(doc)["Header"] and not page_summary(doc)["FirstShared"])
        um.undo()
        rec.check("undo once: document empty", full_text(doc) == "" and doc.getTextTables().getCount() == 0, repr(full_text(doc))[:80])
        um.redo()
        check_layout(rec, "redo", doc, case, True)
        um.undo()
        rec.check("second undo cycle empty", full_text(doc) == "")
        # refusals write nothing
        doc.getText().setString("keep")
        view.gotoStart(False)
        view.goRight(2, True)
        rec.check("selection refused", insert(session, doc, case["typeId"], {})["blockers"] == ["selection"])
        rec.check("refusal leaves text untouched", full_text(doc) == "keep" and doc.getTextTables().getCount() == 0)
        doc.getText().setString("")
        view.gotoStart(False)
        # every document type, placeholders only
        for t in ("cong-van", "thong-bao", "quyet-dinh", "to-trinh", "bao-cao", "giay-moi", "bien-ban"):
            d2 = session.new_doc("swriter")
            try:
                insert(session, d2, t, {}, apply_page=False)
                txt = full_text(d2)
                rec.check("type %s inserts placeholders" % t, "[TÊN CƠ QUAN BAN HÀNH]" in txt and "[Họ và tên]" in txt, txt[:60])
            finally:
                d2.close(True)
        # insert after existing text, then save and reopen
        doc.getText().setString("Before")
        view.gotoEnd(False)
        insert(session, doc, case["typeId"], case["fields"])
        rec.check("insert after text keeps prior text", full_text(doc).startswith("Before"))
        paths = {}
        for ext, flt in (("odt", "writer8"), ("docx", "MS Word 2007 XML")):
            paths[ext] = os.path.join(out, "nd30-sample." + ext)
            doc.storeToURL(uno.systemPathToFileUrl(paths[ext]), props(FilterName=flt))
            rec.check("saved " + ext, os.path.getsize(paths[ext]) > 2000, os.path.getsize(paths[ext]))
    finally:
        doc.close(True)
    for ext, path in paths.items():
        d3 = session.open_doc(path)
        try:
            check_layout(rec, "reopen " + ext, d3, case, ext == "odt")
            if ext == "docx":
                m = docx_margins_twips(path)
                tw = lambda mm: round(mm * 56.6929)
                rec.check("docx w:pgMar = ND30 margins (20/20/30/15 mm)", all(abs(m[k] - tw(v)) <= 2 for k, v in (("top", 20), ("bottom", 20), ("left", 30), ("right", 15))), m)
        finally:
            d3.close(True)
    if not session.display:
        rec.blocked("modal ND30 dialog", "needs --display: headless runs do not show modal dialogs")
    else:
        d4 = session.new_doc("swriter")
        try:
            ok = json.loads(session.macro("run_nd30_dialog", d4, session.installed_python_dir(), "vi", True))
            rec.check("modal ND30 dialog: OK returns the entered fields", ok and ok["type"] == "quyet-dinh" and ok["fields"]["number"] == "9" and ok["apply_page"], ok)
            cancel = session.macro("run_nd30_dialog", d4, session.installed_python_dir(), "vi", False)
            rec.check("modal ND30 dialog: Cancel returns nothing and writes nothing", json.loads(cancel) is None and full_text(d4) == "")
        finally:
            d4.close(True)
    dialogs = json.loads(session.macro("build_dialogs", session.new_doc("swriter"), session.installed_python_dir(), "vi"))
    rec.check("nd30 dialog builds and previews in office", dialogs["nd30"]["refresh"] and "THÔNG BÁO" in dialogs["nd30"]["preview"] and "Số: 07/" in dialogs["nd30"]["preview"], dialogs["nd30"])
    rec.check("nd30 dialog rejects bad number, no preview", not dialogs["nd30_bad"]["refresh"] and "number" in dialogs["nd30_bad"]["errors"][0], dialogs["nd30_bad"])
