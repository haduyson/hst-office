# SPDX-License-Identifier: AGPL-3.0-only
"""Defaults steps of check-vietnamese-utilities.py: DOCSO()/DOCTIEN() with an argument left out follow the file's own
default after recalculation (never the user's default), through .xlsx and .ods; Tùy chọn ▸ HST Office ▸ Đọc số và
tiền loads and saves the user default."""
import os

from vietnamese_utilities_gui import record

PAGE = "vnd.sun.star.expand:$BUNDLED_EXTENSIONS/hst-vietnamese-tools/dialogs/NumberWords.xdl"
CELLS = {"A1": "=DOCTIEN(1000.5)", "A2": "=DOCSO(105)", "A3": '=DOCTIEN(1000.5;"đồng";"")', "A4": '=DOCSO(105;"")'}
PROGRAM = {"A1": "Một nghìn không trăm lẻ một đồng chẵn", "A2": "Một trăm lẻ năm",
           "A3": "Một nghìn không trăm lẻ một đồng chẵn", "A4": "Một trăm lẻ năm"}
FILE = dict(PROGRAM, A1="Một nghìn đồng năm mươi xu", A2="Một trăm linh năm")


def _hidden(office, url):
    from com.sun.star.beans import PropertyValue
    return office.service("com.sun.star.frame.Desktop").loadComponentFromURL(
        url, "_blank", 0, (PropertyValue(Name="Hidden", Value=True),))


def _shown(doc):
    cell = doc.Sheets.getByIndex(0).getCellRangeByName
    return {address: cell(address).getString() for address in CELLS}


def function_defaults(office, doc, args):
    import uno
    from com.sun.star.beans import PropertyValue
    from hst_office import number_words_file_default as fd
    from hst_office import number_words_prefs as prefs
    sheet_doc = _hidden(office, "private:factory/scalc")
    try:
        cell = sheet_doc.Sheets.getByIndex(0).getCellRangeByName
        for address, text in CELLS.items():
            cell(address).setFormula(text)
        prefs.save(office.ctx, {"unit": "dollar", "sub_unit": "cent", "money_options": "ngàn en",
                                "number_options": "ngàn linh"})
        sheet_doc.calculateAll()
        record("the user's default never reaches a cell", _shown(sheet_doc) == PROGRAM, _shown(sheet_doc))
        fd.store(sheet_doc, True, {"unit": "đồng", "sub_unit": "xu", "money_options": ""})
        fd.store(sheet_doc, False, {"number_options": "linh"})
        print("INFO  before recalculation: %s" % _shown(sheet_doc))
        sheet_doc.calculateAll()  # what Ctrl+Shift+F9 does
        record("after recalculation, arguments left out follow the file's default; written ones win",
               _shown(sheet_doc) == FILE, _shown(sheet_doc))
        out = os.path.join(os.path.abspath(args.out), "files")
        os.makedirs(out, exist_ok=True)
        for name, filter_name in (("xlsx", "Calc Office Open XML"), ("ods", "calc8")):
            url = uno.systemPathToFileUrl(os.path.join(out, "ham-mac-dinh-tep.%s" % name))
            sheet_doc.storeToURL(url, (PropertyValue(Name="FilterName", Value=filter_name),))
            loaded = _hidden(office, url)
            try:
                loaded.calculateAll()
                formulas = [loaded.Sheets.getByIndex(0).getCellRangeByName(a).getFormula().replace(
                    "ORG.HST.OFFICE.VI.CALCFUNCTIONS.", "") for a in CELLS]
                record(".%s: same formulas, same file default reading" % name,
                       _shown(loaded) == FILE and formulas == list(CELLS.values()), (_shown(loaded), formulas))
            finally:
                loaded.close(True)
    finally:
        sheet_doc.close(True)
        prefs.save(office.ctx, prefs.DEFAULTS)


def options_page(office, doc, args):
    from hst_office import number_words_prefs as prefs
    handler = office.service("org.hst.office.vi.OptionsNumberWords")
    record("the Đọc số và tiền handler service exists", handler is not None)
    if handler is None:
        return
    parent = doc.getCurrentController().getFrame().getContainerWindow()
    page = office.service("com.sun.star.awt.ContainerWindowProvider").createContainerWindow(PAGE, "", parent, handler)
    try:
        prefs.save(office.ctx, {"unit": "USD", "sub_unit": "cent", "money_options": "tư", "number_options": "linh"})
        handler.callHandlerMethod(page, "initialize", "external_event")
        shown = (page.getControl("m_unit").getText(), page.getControl("m_sub").getText(),
                 page.getControl("m_four").getSelectedItem(), page.getControl("n_odd").getSelectedItem(),
                 page.getControl("n_language").getItemCount())
        record("Đọc số và tiền shows the user's default", shown == ("USD", "cent", "tư", "linh", 2), shown)
        page.getControl("m_unit").setText("đồng")
        page.getControl("m_sub").setText("xu")
        page.getControl("n_thousand").selectItemPos(1, True)
        page.getControl("m_four").selectItemPos(0, True)
        handler.callHandlerMethod(page, "ok", "external_event")
        saved = prefs.load(office.ctx)
        record("OK saves the page", (saved["unit"], saved["sub_unit"], saved["number_options"], saved["money_options"])
               == ("đồng", "xu", "ngàn linh", ""), saved)
    finally:
        page.dispose()
        prefs.save(office.ctx, prefs.DEFAULTS)
