# SPDX-License-Identifier: AGPL-3.0-only
"""Runtime conversion checks: TCVN3 text with bold/italic runs is converted per run, formatting survives, one undo."""
import json

import uno


def portions(doc):
    """[(text, bold, italic, font)] for every text portion, in document order."""
    out, enum = [], doc.getText().createEnumeration()
    while enum.hasMoreElements():
        para = enum.nextElement()
        pe = para.createEnumeration()
        while pe.hasMoreElements():
            p = pe.nextElement()
            if p.TextPortionType == "Text":
                out.append((p.getString(), p.CharWeight > 100, p.CharPosture.value == "ITALIC", p.CharFontName))
    return out


def field_count(doc):
    enum, n = doc.getTextFields().createEnumeration(), 0
    while enum.hasMoreElements():
        enum.nextElement()
        n += 1
    return n


def build(doc):
    text = doc.getText()
    cur = text.createTextCursor()

    def put(s, font, bold=False, italic=False):
        text.insertString(cur, s, True)
        cur.CharFontName, cur.CharWeight = font, 150.0 if bold else 100.0
        cur.CharPosture = uno.Enum("com.sun.star.awt.FontSlant", "ITALIC" if italic else "NONE")
        cur.collapseToEnd()

    put("Hµ Néi ", ".VnTime")             # "Hà Nội "  (TCVN3 bytes decoded as cp1252)
    put("ViÖt", ".VnTime", bold=True)         # "Việt" bold
    put(" Nam", ".VnTime", italic=True)           # italic
    text.insertControlCharacter(cur, 0, False)
    put("HµNéI", ".VnTimeH")             # uppercase font: "HÀNỘI"
    text.insertControlCharacter(cur, 0, False)
    put("Trang ", ".VnTime")
    field = doc.createInstance("com.sun.star.text.TextField.PageNumber")
    field.NumberingType, field.SubType = 4, 1
    text.insertTextContent(cur, field, False)
    put(" Nguy\u00d4n", ".VnTime")                # trailing run after the field: " Nguyễn"


def select_all(doc):
    view = doc.getCurrentController().getViewCursor()
    view.gotoStart(False)
    view.gotoEnd(True)


def conv(session, doc, key="tcvn3", tamper=False):
    return json.loads(session.macro("convert_selection", doc, session.installed_python_dir(), key, tamper))


def run(rec, session, fixtures, out):
    doc = session.new_doc("swriter")
    try:
        build(doc)
        original = portions(doc)
        rec.check("fixture portions built", len(original) >= 5, original)
        select_all(doc)
        plan = json.loads(session.macro("plan_selection", doc, session.installed_python_dir(), "tcvn3"))
        rec.check("preview computed, document untouched", portions(doc) == original and plan["converted"] > 0, plan)
        um = doc.getUndoManager()
        depth = len(um.getAllUndoActionTitles())
        tampered = conv(session, doc, tamper=True)
        rec.check("changed selection refused (content-changed)", tampered["blockers"] == ["content-changed"] and portions(doc) == original, tampered)
        res = conv(session, doc)
        rec.check("convert: no blockers", res["blockers"] == [], res)
        got = portions(doc)
        text = "".join(p[0] for p in got)
        rec.check("converted text correct", "Hà Nội Việt Nam" in text and "HÀNỘI" in text and text.endswith("Nguyễn"), repr(text))
        by_text = {p[0]: p for p in got}
        rec.check("bold run kept on Việt only", by_text.get("Việt", ("", 0))[1] is True and not by_text["Hà Nội "][1])
        rec.check("italic run kept on Nam only", by_text[" Nam"][2] is True and not by_text["Việt"][2])
        rec.check("legacy fonts replaced by Unicode font", all(p[3] == "Times New Roman" for p in got if p[0]), [p[3] for p in got])
        rec.check("page-number field untouched", field_count(doc) == 1 and res["skipped"]["fields"] == 1, res["skipped"])
        rec.check("exactly one undo step", len(um.getAllUndoActionTitles()) == depth + 1, um.getAllUndoActionTitles())
        um.undo()
        rec.check("one undo restores text AND formatting", portions(doc) == original, portions(doc))
        um.redo()
        rec.check("redo converts again", "".join(p[0] for p in portions(doc)) == text)
        um.undo()
        # refusals
        doc.RecordChanges = True
        select_all(doc)
        rec.check("tracked changes refused", conv(session, doc)["blockers"] == ["tracked-changes"] and portions(doc) == original)
        doc.RecordChanges = False
        view = doc.getCurrentController().getViewCursor()
        view.gotoStart(False)
        rec.check("no selection refused", conv(session, doc)["blockers"] == ["no-selection"])
        select_all(doc)
        try:
            conv(session, doc, key="auto")
            rec.check("auto/unknown encoding refused", False)
        except Exception as exc:  # noqa: BLE001 - the conversion layer must reject non-explicit encodings
            rec.check("auto/unknown encoding refused", "unknown-encoding" in str(exc) or "ValueError" in str(exc), str(exc)[:120])
        rec.check("document untouched after refusals", portions(doc) == original)
        if not session.display:
            rec.blocked("modal convert dialog", "needs --display: headless runs do not show modal dialogs")
        else:
            select_all(doc)
            py = session.installed_python_dir()
            no_choice = json.loads(session.macro("run_convert_dialog", doc, py, "vi", False))
            rec.check("convert dialog: OK without explicit encoding is refused (no auto choice)", no_choice["key"] is None, no_choice)
            explicit = json.loads(session.macro("run_convert_dialog", doc, py, "vi", True))
            rec.check("convert dialog: explicit TCVN3 returned; detection stays a suggestion", explicit["key"] == "tcvn3" and explicit["suggestion"], explicit)
    finally:
        doc.close(True)
