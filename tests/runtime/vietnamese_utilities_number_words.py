# SPDX-License-Identifier: AGPL-3.0-only
""""Đọc số thành chữ" steps of check-vietnamese-utilities.py: the dialog reopens with the last choice, a column of
cells is read in one undo step (overwrite notice inside the dialog), and the file's default unit is kept in the
document and survives saving as .xlsx and .ods. Runs after dialogs(), which leaves "Số tiền" + "Công thức" chosen."""
import os
import time

import vietnamese_utilities_gui as gui
from vietnamese_utilities_gui import record

TITLE = r"^Đọc số thành chữ$"
SAY = r"^Công cụ tiếng Việt HST$"
FILE_MONEY = {"unit": "đồng", "sub_unit": "xu", "money_options": ""}


def _open(office, frame):
    thread = gui.background_dispatch(office, frame, "org.hst.office.vi:NumberToWords")
    return thread, gui.wait_window(office, TITLE)


def _close_message(office, args, shot=None):
    wid = gui.wait_window(office, SAY, timeout=15)
    if wid and shot:
        gui.dialog_shot(office, wid, args.shots, shot)
    if wid:
        gui.keys(office.display, wid, "Return")
    return wid


def _formula(cell):
    """The formula as typed: getFormula() names the add-in functions by their programmatic name."""
    return cell.getFormula().replace("ORG.HST.OFFICE.VI.CALCFUNCTIONS.", "")


def _remembered(office):
    from hst_office import number_words_prefs as prefs
    return prefs.load(office.ctx)


def number_words(office, doc, args):
    from hst_office import number_words_file_default as fd
    from hst_office import number_words_prefs as prefs
    controller = doc.getCurrentController()
    frame, sheet = controller.getFrame(), controller.getActiveSheet()
    cell = sheet.getCellRangeByName
    last = _remembered(office)
    record("the last choice is kept in the profile", last["money"] and last["formula"], last)
    # 1. the dialog reopens with the last choice: Return alone writes a DOCTIEN formula
    cell("S10").setValue(5000)
    controller.select(cell("S10"))
    thread, wid = _open(office, frame)
    if wid:
        gui.keys(office.display, wid, "Return")
        thread.join(30)
    record("dialog reopens with the last choice (money, formula)", _formula(cell("T10")) == "=DOCTIEN(S10)"
           and cell("T10").getString() == "Năm nghìn đồng chẵn", (_formula(cell("T10")), cell("T10").getString()))
    # 2. a column: empty skipped, text skipped and counted, an occupied target needs "Ghi đè", one undo
    for address, value in (("S1", 1000), ("S3", "abc"), ("S4", 2000000), ("S5", 5)):
        cell(address).setValue(value) if isinstance(value, int) else cell(address).setString(value)
    cell("T4").setString("cũ")
    doc.getUndoManager().clear()
    controller.select(sheet.getCellRangeByName("S1:S5"))
    thread, wid = _open(office, frame)
    if wid:
        gui.keys(office.display, wid, "Return")
        time.sleep(1)
        gui.dialog_shot(office, wid, args.shots, "doc-so-thanh-chu-ghi-de")
        record("an occupied target keeps the dialog open with the notice", cell("T4").getString() == "cũ"
               and gui.wait_window(office, TITLE, timeout=3) == wid)
        gui.keys(office.display, wid, "Return")
        _close_message(office, args, "doc-so-thanh-chu-vung-ket-qua")
        thread.join(30)
    got = [_formula(cell("T%d" % row)) for row in range(1, 6)]
    record("column: every number row written, empty and text rows left alone",
           got == ["=DOCTIEN(S1)", "", "", "=DOCTIEN(S4)", "=DOCTIEN(S5)"], got)
    doc.getUndoManager().undo()
    record("column: one undo restores every target", cell("T4").getString() == "cũ" and cell("T1").getFormula() == ""
           and cell("T5").getFormula() == "", [cell("T%d" % row).getFormula() for row in range(1, 6)])
    # 3. the file's default unit: sub-unit "xu", tick "Dùng làm mặc định cho tệp này"
    controller.select(cell("S1"))
    thread, wid = _open(office, frame)
    if wid:
        gui.keys(office.display, wid, *(["Tab"] * 5))
        gui.type_text(office.display, wid, "xu")
        gui.keys(office.display, wid, *(["Tab"] * 6), "space")
        gui.dialog_shot(office, wid, args.shots, "doc-so-thanh-chu-mac-dinh-tep")
        gui.keys(office.display, wid, "Return")
        thread.join(30)
    record("file default: the formula leaves out what the file's default reads", _formula(cell("T1")) == "=DOCTIEN(S1)"
           and cell("T1").getString() == "Một nghìn đồng chẵn", (_formula(cell("T1")), cell("T1").getString()))
    record("file default: stored as document properties", fd.read(doc) == FILE_MONEY, fd.read(doc))
    _hint(office, args, frame, controller, cell)
    _round_trip(office, doc, args, fd)
    prefs.save(office.ctx, prefs.DEFAULTS)  # the Writer step expects the program default


def _hint(office, args, frame, controller, cell):
    controller.select(cell("S5"))
    thread, wid = _open(office, frame)
    try:
        if wid:
            time.sleep(1)
            gui.dialog_shot(office, wid, args.shots, "doc-so-thanh-chu-goi-y-tep")
        try:
            app = gui.office_app() if wid else None
        except ImportError:  # no AT-SPI bindings in this Python: the screenshot shows the hint
            print("SKIP  “Đang dùng mặc định của tệp” (no pyatspi; see doc-so-thanh-chu-goi-y-tep.png)")
        else:
            hint = gui.find(app, "label", "Đang dùng mặc định của tệp") if app else None
            record("dialog shows “Đang dùng mặc định của tệp”", hint is not None)
    finally:
        if wid:
            gui.keys(office.display, wid, "Escape")
            thread.join(30)


def _round_trip(office, doc, args, fd):
    import uno
    from com.sun.star.beans import PropertyValue
    out = os.path.join(os.path.abspath(args.out), "files")
    os.makedirs(out, exist_ok=True)
    desktop = office.service("com.sun.star.frame.Desktop")
    blank = desktop.loadComponentFromURL("private:factory/scalc", "_blank", 0,
                                         (PropertyValue(Name="Hidden", Value=True),))
    usd = {"unit": "USD", "sub_unit": "", "money_options": "en", "number_options": ""}
    fd.store(blank, True, fd.group(True, usd))
    fd.store(blank, False, fd.group(False, usd))
    for source, expected in ((doc, FILE_MONEY), (blank, usd)):
        for name, filter_name in (("xlsx", "Calc Office Open XML"), ("ods", "calc8")):
            url = uno.systemPathToFileUrl(os.path.join(out, "mac-dinh-%s.%s" % (expected["unit"], name)))
            source.storeToURL(url, (PropertyValue(Name="FilterName", Value=filter_name),))
            loaded = desktop.loadComponentFromURL(url, "_blank", 0, (PropertyValue(Name="Hidden", Value=True),))
            try:
                record("file default %s survives .%s" % (expected["unit"], name), fd.read(loaded) == expected,
                       fd.read(loaded))
            finally:
                loaded.close(True)
    blank.close(True)
