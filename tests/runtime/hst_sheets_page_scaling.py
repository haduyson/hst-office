# SPDX-License-Identifier: AGPL-3.0-only
"""Print scaling on the Page tab of Sheets, part of check-dialogs-sheets.py."""
from hst_dialog_uitest import click, props, select_entry, select_tab, state, tab_titles, visible
from hst_sheets_dialog_checks import new_sheet, type_text


def check_page_scaling(h, c):
    """Excel's place for scaling: the Page tab. The same style items, so existing values keep working."""
    doc, sheet = new_sheet(h, "A1")
    style = doc.getStyleFamilies().getByName("PageStyles").getByName(sheet.PageStyle)
    style.PageScale = 60  # as an existing file brings it
    dlg = h.open_dialog(".uno:PageFormatDialog", "PageTemplateDialog")
    titles = tab_titles(dlg)
    select_tab(dlg, titles.index("Trang"))
    children = dlg.getChildren()
    c.equal("scaling: on the Page tab", "comboLB_SCALEMODE" in children, True)
    c.equal("scaling: page format still on the Page tab", "comboPageFormat" in children and "spinMargLeft" in children, True)
    c.equal("scaling: existing value shown", state(dlg.getChild("spinED_SCALEALL"))["Value"].rstrip("%").strip(), "60")
    select_tab(dlg, titles.index("Trang tính"))
    c.equal("scaling: gone from the Sheet tab", visible(dlg, "comboLB_SCALEMODE"), False)
    c.equal("scaling: Sheet tab keeps its options", visible(dlg, "checkBTN_GRID") and visible(dlg, "entryRepeatRows"), True)

    select_tab(dlg, titles.index("Trang"))
    select_entry(dlg, "comboLB_SCALEMODE", 1)
    c.equal("scaling: width and height shown", visible(dlg, "spinED_SCALEPAGEWIDTH"), True)
    type_text(dlg, "spinED_SCALEPAGEWIDTH", "2")
    type_text(dlg, "spinED_SCALEPAGEHEIGHT", "3")
    # Leaving for another tab, then OK there, must carry the values (and the hosted page's own).
    select_tab(dlg, titles.index("Trang tính"))
    click(dlg, "ok")
    h.wait_idle()
    c.equal("scaling: fit to width and height reaches the style", (style.ScaleToPagesX, style.ScaleToPagesY, style.PageScale), (2, 3, 0))

    dlg = h.open_dialog(".uno:PageFormatDialog", "PageTemplateDialog")
    select_tab(dlg, titles.index("Trang"))
    select_entry(dlg, "comboLB_SCALEMODE", 2)
    type_text(dlg, "spinED_SCALEPAGENUM", "4")
    click(dlg, "cancel")
    h.wait_idle()
    c.equal("scaling: Cancel keeps the style", (style.ScaleToPagesX, style.ScaleToPages), (2, 0))

    dlg = h.open_dialog(".uno:PageFormatDialog", "PageTemplateDialog")
    select_tab(dlg, titles.index("Trang"))
    select_entry(dlg, "comboLB_SCALEMODE", 2)
    type_text(dlg, "spinED_SCALEPAGENUM", "4")
    type_text(dlg, "spinMargLeft", "3")  # the hosted page still does its own work
    click(dlg, "ok")
    h.wait_idle()
    c.equal("scaling: fit to pages reaches the style", (style.ScaleToPages, style.ScaleToPagesX), (4, 0))
    c.equal("scaling: margin of the hosted page reaches the style", style.LeftMargin, 3000)

    # xlsx keeps Excel's two kinds of scaling: percent and fit to width/height.
    url = h.temp_url("page-scaling.xlsx")
    for values, expected in (({"PageScale": 75}, {"PageScale": 75}), ({"ScaleToPagesX": 2, "ScaleToPagesY": 3}, {"ScaleToPagesX": 2, "ScaleToPagesY": 3})):
        for key in ("PageScale", "ScaleToPages", "ScaleToPagesX", "ScaleToPagesY"):
            setattr(style, key, 0)
        for key, value in values.items():
            setattr(style, key, value)
        doc.storeToURL(url, props(FilterName="Calc MS Excel 2007 XML"))
        again = h.office.desktop().loadComponentFromURL(url, "_blank", 0, props(Hidden=True))
        reopened = again.getStyleFamilies().getByName("PageStyles").getByName(again.getSheets().getByIndex(0).PageStyle)
        c.equal(f"scaling: {expected} survives xlsx", {k: getattr(reopened, k) for k in expected}, expected)
        h.close_document(again)
    # Excel has no "fit on N pages in total": what xlsx makes of it is printed, not asserted.
    for key in ("PageScale", "ScaleToPages", "ScaleToPagesX", "ScaleToPagesY"):
        setattr(style, key, 0)
    style.ScaleToPages = 4
    doc.storeToURL(url, props(FilterName="Calc MS Excel 2007 XML"))
    again = h.office.desktop().loadComponentFromURL(url, "_blank", 0, props(Hidden=True))
    reopened = again.getStyleFamilies().getByName("PageStyles").getByName(again.getSheets().getByIndex(0).PageStyle)
    print("info scaling: fit on 4 pages after xlsx:", {k: getattr(reopened, k) for k in ("PageScale", "ScaleToPages", "ScaleToPagesX", "ScaleToPagesY")}, flush=True)
    h.close_document(again)
    h.close_document(doc)
