# SPDX-License-Identifier: AGPL-3.0-only
"""Windows: a Writer document with an embedded Calc sheet survives save and reopen as .odt and .docx (installed build).

Usage, in the user's own session (windows-own-session-task.ps1) with the office's Python:
  "<instdir>\\program\\python.exe" tests\\runtime\\check-windows-embedded-calc-roundtrip.py --instdir <instdir> --out DIR

Synthetic data only. Writes a Writer document holding a Calc object (A1 "Bút" 42, A2 "Vở" 17, B3 =SUM(B1:B2) = 59),
stores it as .odt and .docx, then reopens a fresh copy of each, hidden and visible, and reads the cells back over UNO.
Everything follows windows_modal_safe: a private QUIET-seeded profile (verified over UNO after the start), every load
on the office's main thread, a new file name per open, and on a timeout or a close veto the office's modal window
titles in the result, so "waiting on a dialog" is never reported as a product hang. Only this office is stopped,
and after a forced stop only lock files written by its profile are removed.
Writes <out>/results.json; exit 1 when any row fails.
"""
import argparse
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import windows_modal_safe as safe  # noqa: E402

CALC_CLSID = "47BBB4CB-CE4C-4E80-A591-42D9AE74950F"
FORMATS = (("odt", "writer8"), ("docx", "MS Word 2007 XML"))
EXPECTED = {"A1": "Bút", "B1": 42.0, "B2": 17.0, "B3": 59.0}


def prop(name, value):
    from com.sun.star.beans import PropertyValue
    p = PropertyValue()
    p.Name, p.Value = name, value
    return p


def write_sources(office, folder):
    """The Writer document with its Calc object, stored once per format; returns {format: path}."""
    import uno
    os.makedirs(folder, exist_ok=True)
    doc = office.load("private:factory/swriter", hidden=True)
    try:
        obj = doc.createInstance("com.sun.star.text.TextEmbeddedObject")
        obj.CLSID = CALC_CLSID
        cursor = doc.Text.createTextCursor()
        cursor.gotoEnd(False)
        doc.Text.insertTextContent(cursor, obj, False)
        sheet = obj.Model.Sheets.getByIndex(0)
        sheet.getCellByPosition(0, 0).setString("Bút")
        sheet.getCellByPosition(1, 0).setValue(42)
        sheet.getCellByPosition(0, 1).setString("Vở")
        sheet.getCellByPosition(1, 1).setValue(17)
        sheet.getCellByPosition(1, 2).setFormula("=SUM(B1:B2)")
        paths = {}
        for ext, filter_name in FORMATS:
            paths[ext] = os.path.join(folder, "embedded-calc." + ext)
            doc.storeToURL(uno.systemPathToFileUrl(paths[ext]), (prop("FilterName", filter_name), prop("Overwrite", True)))
        return paths
    finally:
        doc.close(True)


def calc_cells(doc):
    """{cell: value} of the first embedded Calc object of `doc` ({} when there is none)."""
    objects = doc.getEmbeddedObjects()
    for name in objects.getElementNames():
        model = objects.getByName(name).Model
        if model is not None and hasattr(model, "Sheets"):
            sheet = model.Sheets.getByIndex(0)
            return {"A1": sheet.getCellByPosition(0, 0).getString(), "B1": sheet.getCellByPosition(1, 0).getValue(),
                    "B2": sheet.getCellByPosition(1, 1).getValue(), "B3": sheet.getCellByPosition(1, 2).getValue()}
    return {}


def reopen(office, results, source, hidden, folder, timeout, opened):
    """One fresh copy of `source` loaded, checked and closed. Returns False when the office can no longer be used."""
    import uno
    label = "%s %s" % (os.path.splitext(source)[1][1:], "hidden" if hidden else "visible")
    path = safe.fresh_copy(source, folder, "h" if hidden else "v")
    opened.append(path)
    state, doc, titles = safe.bounded(lambda: office.load(uno.systemPathToFileUrl(path), hidden=hidden), timeout,
                                      office.url)
    if state != "done":
        results("reopen %s" % label, False, "%s after %d s; modal windows: %s" % (state, timeout, titles))
        return False
    if doc is None or isinstance(doc, Exception):
        results("reopen %s" % label, False, "load returned %r" % (doc,))
        return True
    cells = calc_cells(doc)
    results("reopen %s: embedded Calc data" % label, cells == EXPECTED, cells)
    veto = safe.close_or_report(doc, office.url)
    results("close %s" % label, veto is None, veto or "closed")
    return veto is None


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--instdir", required=True)
    parser.add_argument("--out", required=True)
    parser.add_argument("--port", type=int, default=2341)
    parser.add_argument("--timeout", type=int, default=60, help="seconds per load before the modal windows are read")
    args = parser.parse_args()
    from windows_gui import Results, WinOffice
    out = os.path.abspath(args.out)
    profile = os.path.join(out, "profile")
    url = safe.quiet_profile(os.path.join(args.instdir, "program"), profile, out)
    results = Results(out, profile)
    office = WinOffice(args.instdir, profile, args.port, os.path.join(out, "logs"), nodefault=True).start()
    opened, usable = [], True
    try:
        quiet = (office.config("/org.hasontech.hstoffice.Welcome", "Shown") is True
                 and office.config("/org.hasontech.hstoffice.DefaultApps", "Ask") is False)
        results("QUIET profile effective (no start-up question)", quiet, url)
        sources = write_sources(office, os.path.join(out, "src"))
        results("store .odt and .docx", all(os.path.getsize(p) > 0 for p in sources.values()), sources)
        for ext, _filter in FORMATS:
            for hidden in (True, False):
                usable = usable and reopen(office, results, sources[ext], hidden, os.path.join(out, "open"),
                                           args.timeout, opened)
                if not usable:
                    break
            if not usable:
                break
        if usable:
            results("office still running", office.desktop.getComponents() is not None)
    finally:
        office.stop()
        removed = safe.remove_own_locks(opened, url)
        if removed:
            results.note("removed own lock files after the stop", removed)
    return results.exit_code()


if __name__ == "__main__":
    sys.exit(main())
