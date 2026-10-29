# SPDX-License-Identifier: AGPL-3.0-only
"""Test-only Python macro copied into the ISOLATED test profile (never shipped). It runs the installed extension's
logic inside the office process so undo-action callbacks and UNO calls behave exactly as in the product."""
import json
import sys


def _load(py_dir):
    if py_dir not in sys.path:
        sys.path.insert(0, py_dir)


def insert_nd30(doc, py_dir, type_id, fields_json, apply_page, page_numbers):
    _load(py_dir)
    from hst_office import nd30_layout, nd30_writer
    cursor = doc.getCurrentController().getViewCursor()
    layout = nd30_layout.build_layout(type_id, json.loads(fields_json))
    result = nd30_writer.insert_layout(doc, cursor, layout, apply_page=bool(apply_page), page_numbers=bool(page_numbers))
    return json.dumps(result, ensure_ascii=False)


def convert_selection(doc, py_dir, encoding_key, tamper):
    _load(py_dir)
    from hst_office import encoding_writer
    rng, reasons = encoding_writer.check_selection(doc, doc.getCurrentController().getSelection())
    if reasons:
        return json.dumps({"blockers": reasons})
    items, skipped, protected = encoding_writer.collect(rng)
    snap = encoding_writer.snapshot(items)
    if tamper:
        snap = [("changed", "x")]
    result = encoding_writer.apply(doc, rng, encoding_key, snap)
    result["skipped"] = skipped
    return json.dumps(result, ensure_ascii=False)


def plan_selection(doc, py_dir, encoding_key):
    _load(py_dir)
    from hst_office import encoding_writer
    rng, reasons = encoding_writer.check_selection(doc, doc.getCurrentController().getSelection())
    if reasons:
        return json.dumps({"blockers": reasons})
    rows, totals = encoding_writer.plan(encoding_writer.collect(rng)[0], encoding_key)
    return json.dumps({"texts": [(r["text"], r["new"], r["new_font"]) for r in rows], **totals}, ensure_ascii=False)


def apply_format(doc, py_dir, kind):
    _load(py_dir)
    from hst_office import sheets
    selection = doc.getCurrentController().getSelection()
    reasons = sheets.sheet_blockers(doc.getCurrentController().getActiveSheet().isProtected(), True)
    if reasons:
        return json.dumps({"blockers": reasons})
    from hst_office import undo
    with undo.undo_step(doc, "Format " + kind):
        summary = sheets.apply_format(doc, selection, kind)
    return json.dumps(summary)


def import_csv(doc, py_dir, rows_json, mode, overwrite, column, row):
    _load(py_dir)
    from hst_office import csv_calc
    sheet = doc.getCurrentController().getActiveSheet()
    return json.dumps(csv_calc.write_rows(doc, sheet, column, row, json.loads(rows_json), mode, bool(overwrite)))


def build_dialogs(doc, py_dir, lang):
    """Construct (not show) each wizard, drive its fields and preview, return observations."""
    _load(py_dir)
    import uno
    from hst_office import data_files, wizard_csv, wizard_convert, wizard_nd30
    ctx = uno.getComponentContext()
    strings = data_files.load_locale(lang)
    out = {}
    wiz = wizard_nd30.Nd30Wizard(ctx, strings)
    wiz.set_fields("thong-bao", {"agency": "[Cơ quan thử]", "number": "7", "summary": "Về việc thử", "date": "05/02/2026"})
    ok = wiz.refresh()
    out["nd30"] = {"title": wiz.d.model.Title, "refresh": ok, "preview": wiz.d.get("preview")}
    wiz.set_fields(None, {"number": "x1"})
    out["nd30_bad"] = {"refresh": wiz.refresh(), "preview": wiz.d.get("preview"), "errors": wiz.errors()}
    wiz.d.dialog.dispose()
    wiz2 = wizard_csv.CsvWizard(ctx, strings, lambda: None)
    out["csv"] = {"title": wiz2.d.model.Title}
    wiz2.d.dialog.dispose()
    return json.dumps(out, ensure_ascii=False)


def _press_ok_later(action, delay=2.0):
    """Run `action` from a helper thread shortly after the modal dialog starts (stands in for a click on OK);
    a watchdog closes the dialog after 25 s so a failed check can never hang the run."""
    import threading
    timer = threading.Timer(delay, action)
    timer.daemon = True
    timer.start()


def run_nd30_dialog(doc, py_dir, lang, press_ok):
    """Execute the real modal ND30 wizard; a main-loop callback presses OK (or Cancel) after it is shown."""
    _load(py_dir)
    import uno
    from hst_office import data_files, wizard_nd30
    ctx = uno.getComponentContext()
    wiz = wizard_nd30.Nd30Wizard(ctx, data_files.load_locale(lang))
    wiz.set_fields("quyet-dinh", {"agency": "[Cơ quan thử]", "number": "9", "symbol": "qđ", "date": "2026-02-05", "summary": "Về việc thử"})
    _press_ok_later(wiz._accept if press_ok else (lambda: wiz.d.end(0)))
    _press_ok_later(lambda: wiz.d.end(0), 25.0)  # watchdog
    outcome = wiz.run(doc.getCurrentController().getFrame().getContainerWindow())
    return json.dumps(outcome, ensure_ascii=False)


def run_convert_dialog(doc, py_dir, lang, choose):
    _load(py_dir)
    import uno
    from hst_office import data_files, encoding_writer, wizard_convert
    ctx = uno.getComponentContext()
    rng, reasons = encoding_writer.check_selection(doc, doc.getCurrentController().getSelection())
    items = encoding_writer.collect(rng)[0]
    wiz = wizard_convert.ConvertWizard(ctx, data_files.load_locale(lang), items)
    if choose:
        wiz.d.select("source", 1)
    suggestion = wiz.d.model.getByName("suggestion").Label
    _press_ok_later(wiz._accept)
    _press_ok_later(lambda: wiz.d.end(0), 25.0)  # watchdog
    key = wiz.run(doc.getCurrentController().getFrame().getContainerWindow())
    return json.dumps({"key": key, "suggestion": suggestion}, ensure_ascii=False)
