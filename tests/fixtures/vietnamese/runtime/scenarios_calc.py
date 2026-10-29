# SPDX-License-Identifier: AGPL-3.0-only
"""Runtime Calc checks: vi-VN number formats leave values/formulas unchanged; CSV import is literal, single-undo, safe."""
import json
import time


def cell_state(sheet, name):
    c = sheet.getCellRangeByName(name)
    return (c.Type.value, c.getValue(), c.getFormula())


def run(rec, session, fixtures, out):
    try:
        probe = session.new_doc("scalc")
    except Exception as exc:  # noqa: BLE001 - the system office has no Calc module installed
        rec.blocked("calc scenarios", "this LibreOffice has no Calc module: %s" % str(exc)[:100])
        return
    probe.close(True)
    py = session.installed_python_dir()
    doc = session.new_doc("scalc")
    try:
        ctrl, sheet = doc.getCurrentController(), doc.Sheets.getByIndex(0)
        rec.check("null date is 1899-12-30", (doc.NullDate.Year, doc.NullDate.Month, doc.NullDate.Day) == (1899, 12, 30))
        sheet.getCellRangeByName("A1").setValue(46058)       # 2026-02-05 with that null date
        sheet.getCellRangeByName("B1").setValue(1234567)
        sheet.getCellRangeByName("C1").setValue(0.125)
        sheet.getCellRangeByName("D1").setFormula("=B1*2")
        sheet.getCellRangeByName("E1").setString("abc")
        before = {n: cell_state(sheet, n) for n in ("A1", "B1", "C1", "D1", "E1")}
        for name, kind, want in (("A1", "date", "05/02/2026"), ("B1", "vnd", "1.234.567 ₫"), ("C1", "percent", "12,50%"), ("D1", "vnd", "2.469.134 ₫")):
            ctrl.select(sheet.getCellRangeByName(name))
            res = json.loads(session.macro("apply_format", doc, py, kind))
            got = sheet.getCellRangeByName(name).getString()
            rec.check("%s as %s renders %r" % (name, kind, want), got.replace(" ", " ") == want, got)
        after = {n: cell_state(sheet, n) for n in before}
        rec.check("values and formulas unchanged by formats", after == before, (before, after))
        ctrl.select(sheet.getCellRangeByName("E1"))
        res = json.loads(session.macro("apply_format", doc, py, "date"))
        rec.check("text cell stays text, reported", sheet.getCellRangeByName("E1").getString() == "abc" and res["text_cells"] == 1, res)
        locale_ok = doc.getNumberFormats().getByKey(res["key"]).Locale.Language == "vi"
        rec.check("format registered for locale vi-VN", locale_ok)
        # --- CSV import
        um = doc.getUndoManager()
        rows = [["ma", "ten", "=1+1"], ["00123", "Nguyễn", "+84912345678"], ["-5", "@x", "1,5"], ["2026-01-01", "a\nb", "1e3"]]
        depth = len(um.getAllUndoActionTitles())
        res = json.loads(session.macro("import_csv", doc, py, json.dumps(rows), "text", False, 0, 5))
        rec.check("csv import ok", res["blockers"] == [] and res["cells"] == 12, res)
        ok = all(sheet.getCellByPosition(c, 5 + r).getString() == v and sheet.getCellByPosition(c, 5 + r).Type.value == "TEXT"
                 for r, row in enumerate(rows) for c, v in enumerate(row))
        rec.check("all cells literal text (00123, =1+1, +84, -5, @x, 1e3, newline)", ok)
        rec.check("no formula was created", not any(sheet.getCellByPosition(c, 5 + r).getFormula().startswith("=") and sheet.getCellByPosition(c, 5 + r).Type.value == "FORMULA"
                                                     for r in range(4) for c in range(3)))
        rec.check("csv import is one undo step", len(um.getAllUndoActionTitles()) == depth + 1, um.getAllUndoActionTitles())
        um.undo()
        left = [(c, r, sheet.getCellByPosition(c, 5 + r).Type.value, sheet.getCellByPosition(c, 5 + r).getString()) for r in range(4) for c in range(3)
                if sheet.getCellByPosition(c, 5 + r).Type.value != "EMPTY"]
        rec.check("one undo clears the imported range", not left, left)
        um.redo()
        rec.check("redo restores import", sheet.getCellByPosition(0, 6).getString() == "00123")
        again = json.loads(session.macro("import_csv", doc, py, json.dumps(rows), "text", False, 0, 5))
        rec.check("non-empty destination refused without consent", again["blockers"] == ["overwrite-needed"] and sheet.getCellByPosition(0, 6).getString() == "00123", again)
        rec.check("overwrite with consent works", json.loads(session.macro("import_csv", doc, py, json.dumps([["z"]]), "text", True, 0, 5))["blockers"] == [])
        far = json.loads(session.macro("import_csv", doc, py, json.dumps([["a", "b", "c"]]), "text", False, 16383, 40))
        rec.check("data past the last column refused", far["blockers"] == ["outside-sheet"], far)
        sheet.protect("")
        prot = json.loads(session.macro("import_csv", doc, py, json.dumps([["q"]]), "text", False, 10, 10))
        sheet.unprotect("")
        rec.check("protected sheet refused", prot["blockers"] == ["sheet-protected"] and sheet.getCellByPosition(10, 10).Type.value == "EMPTY", prot)
        gen = json.loads(session.macro("import_csv", doc, py, json.dumps([["00123", "123", "=1+1", "4.5"]]), "general", False, 0, 20))
        kinds = [sheet.getCellByPosition(c, 20).Type.value for c in range(4)]
        rec.check("general mode: numbers only where safe", gen["blockers"] == [] and kinds == ["TEXT", "VALUE", "TEXT", "VALUE"] and sheet.getCellByPosition(0, 20).getString() == "00123", kinds)
        big = [["r%d" % i, "00%d" % i, "=A%d" % i] for i in range(5000)]
        started = time.time()
        res = json.loads(session.macro("import_csv", doc, py, json.dumps(big), "text", False, 4, 100))
        rec.check("5000 rows imported (%.1fs)" % (time.time() - started), res["blockers"] == [] and sheet.getCellByPosition(6, 5099).getString() == "=A4999", res)
    finally:
        doc.close(True)
