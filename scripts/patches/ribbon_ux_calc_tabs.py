# SPDX-License-Identifier: AGPL-3.0-only
"""The tabs of the HST Sheets ribbon rework (generate-ribbon-ux-calc.py), one function per tab."""
import copy

import ribbon_ux_lib as L
from ribbon_ux_calc_data import (CHART_TYPES, CONVERT_TO_NUMBER, EXTENSION_ORDER, FIT_WIDTH_COMMAND, LABELS,
                                 NEW_CAPTIONS, SPLIT_BUTTONS, TOOLTIPS)
from ribbon_ux_calc_layout import CalcUxError
from ribbon_ux_calc_menus import NUMBER_TO_WORDS


def home(b):
    b.drop("btnHomeHstSearchDialog")  # Find and Replace: Editing ▸ Find and Select ▾
    for bid in SPLIT_BUTTONS:  # a click runs the command, the arrow opens its menu
        b.find(bid).set("class", "GtkMenuToolButton")
        L.set_prop(b.find(bid), "use-underline", None)
    b.style("bxHomeWrapRTL", big=False)
    b.style("bxHomeMergeCells", big=False)
    b.place("gdHomeAlignment", [["bxHomeVAlign", "boxHomeHAlign"], ["bxHomeSpacingIndentation", "bxHomeAlignBlock"],
                                ["bxHomeWrapRTL", "bxHomeMergeCells"]])
    # Number: đồng and dd/mm/yyyy of the HST extension
    vnd = b.button("btnHomeHstFormatVnd", "org.hst.office.vi:FormatVnd", label="₫", icon="cmd/sc_formatvnd.png",
                   tooltip=TOOLTIPS["btnHomeHstFormatVnd"])
    L.insert_child(b.find("bxHomeNumberFormat"), vnd, 0)
    date = b.button("btnHomeHstFormatDate", "org.hst.office.vi:FormatDate", klass="GtkMenuToolButton",
                    label="Ngày dd/mm/yyyy", icon="cmd/sc_formatdate.png", tooltip=TOOLTIPS["btnHomeHstFormatDate"])
    L.insert_child(b.find("bxHomeNumberDecimals"), date)
    # Styles: Conditional Formatting big, Format as Table and Cell Styles ▾ beside it
    b.style("bxHomeConditionalFormatMenu", big=True)
    b.place("gdHomeStyles", [["bxHomeConditionalFormatMenu"], ["bxLayoutAutoFormat", "btnHomeHstCellStyles:Menu HstCellStyles"]])
    # Cells: Insert ▾, Delete ▾, Format ▾
    b.drop("bxLayoutInsert", "btnHomeRow", "bxHomeColumn", "bxLayoutRenameTable")
    b.place("gdHomeCells", [[b.menu_button("HstCellsInsert"), b.menu_button("HstCellsDelete")],
                            [b.menu_button("HstCellsFormat")]])
    # Editing: AutoSum, Fill ▾, Clear ▾, Sort and Filter ▾, Find and Select ▾
    b.drop("bxHstFillDown2", "bxHstClearContents3")
    b.place("gdHomeEditing", [["bxHstAutoSum1"], [b.menu_button("HstEditingFill"), b.menu_button("HstEditingClear")],
                              [b.menu_button("HstEditingSortFilter")], [b.menu_button("HstEditingFindSelect")]])


def insert(b):
    b.drop("bxInsertRecalcPivotTable", "bxInsertDeletePivotTable")  # on the Pivot Table contextual tab
    b.place("gdInsertPivotTable", [["bxInsertDataDataPilotRun"], ["bxHstInsertCalcTable"]])
    b.drop("bxShapesTopLeft", "bxShapesBottomLeft", "bxShapesTopRight", "bxShapesBottomRight")
    b.style("bxInsertInsertGraphic", big=True)
    b.place("gdInsertShapes", [["bxInsertInsertGraphic"], [b.menu_button("HstInsertShapes")], ["bxInsertGallery", None]])
    b.drop("gdInsertHstExtensions")
    charts = [b.toolbox(f"bxInsertHstChart{kind}", [b.button(f"btnInsertHstChart{kind}",
                                                             f".uno:InsertObjectChart?ChartType:string={kind}",
                                                             icon=icon)], big=False) for kind, icon in CHART_TYPES]
    b.style("bxHstInsertSparkline4", big=False)
    b.place("gdInsertCharts", [["bxInsertInsertObjectChart"], charts[:2], [charts[2], "bxHstInsertSparkline4"]])


def page_layout(b):
    b.drop("bxLayoutPageFormatDialog", "bxHstRowBreak", "bxHstColumnBreak", "bxLayoutDefinePrintArea",
           "bxLayoutEditPrintArea", "bxLayoutPrintArea")  # the caption's launcher opens the page dialog
    b.style("bxLayoutEditHeaderAndFooter", big=False)
    fit = b.toolbox("bxLayoutHstFitWidth", [b.button("btnLayoutHstFitWidth", FIT_WIDTH_COMMAND,
                                                     icon="cmd/sc_zoompagewidth.png",
                                                     translate=LABELS["btnLayoutHstFitWidth"])], big=False)
    b.place("gdLayoutPage", [[b.menu_button("HstLayoutMargins")], [b.menu_button("HstLayoutOrientation")],
                             [b.menu_button("HstLayoutSize")], [b.menu_button("HstLayoutPrintArea")],
                             [b.menu_button("HstLayoutBreaks")], ["bxLayoutEditHeaderAndFooter", fit]])


def formulas(b):
    b.drop("bxHstAutoSum10")  # the AutoSum split button below
    autosum = b.toolbox("bxFunctionsHstAutoSum", [b.button("btnFunctionsHstAutoSum", ".uno:AutoSum",
                                                           klass="GtkMenuToolButton")], big=False)
    words = b.toolbox("bxFunctionsHstNumberToWords", [b.button(
        "btnFunctionsHstNumberToWords", NUMBER_TO_WORDS, icon="cmd/lc_numbertowords.png",
        translate=LABELS["btnFunctionsHstNumberToWords"])], big=True)
    b.place("gdFunctionsLibrary", [
        ["bxHstFunctionDialog9"], [autosum, "bxInsertFunctionBox"],
        [b.menu_button("HstFunctionsFinancial"), b.menu_button("HstFunctionsLogical")],
        [b.menu_button("HstFunctionsText"), b.menu_button("HstFunctionsDateTime")],
        [b.menu_button("HstFunctionsLookup"), b.menu_button("HstFunctionsMath")], [words]])
    b.style("bxInsertDefineName", big=True)
    b.place("gdInsertRange", [["bxInsertDefineName"], ["bxInsertAddName", "bxHstInsertName"], ["bxHstCreateNames", None]])
    b.drop("bxFunctionsAuditingFillMode", "bxFunctionsClearArrowPrecedents", "bxFunctionsClearArrowDependents")
    b.place("gdFunctionsDetective", [["bxFunctionsShowPrecedents", "bxFunctionsShowDependents"],
                                     ["bxHstClearArrows", "bxFunctionsShowInvalid"],
                                     ["bxFunctionsShowErrors", "bxViewToggleFormula"]])


def data(b):
    csv = b.find("btnHstImportCsv")
    for prop, value in (("label", "Từ văn bản/CSV"), ("tooltip-text", TOOLTIPS["btnDataHstImportCsv"])):
        L.set_prop(csv, prop, value)
    L.set_prop(csv, "action-name", None)
    L.set_prop(csv, "action-name", "org.hst.office.vi:ImportCsv")
    L.set_prop(csv, "icon-name", "cmd/lc_importcsv.png")
    b.style("bxHstImportCsv", big=True)
    b.drop("bxDataInsertExternalDataSource", "bxDataDataStreams", "bxDataManageXMLSource", "bxDataDataProvider",
           "bxDataDataProviderRefresh", "bxHstDataSourceBrowser")
    b.place("gdDataSources", [["bxHstImportCsv"], [b.menu_button("HstDataSources")], ["bxHstEditLinks", None]])
    b.drop("bxDataShuffle")
    b.style("bxDataDataFilterAutoFilter", big=True)
    b.place("gdDataSort", [["bxDataDataSort"], ["bxDataSortAscending", "bxDataSortDescending"],
                           ["bxDataDataFilterAutoFilter"], ["bxHstRemoveFilter", "bxDataDataFilterStandardFilter"],
                           ["bxDataDataFilterSpecialFilter", "bxDataDataFilterHideAutoFilter"]])
    # Data Tools, with "Chuyển thành số" (hst-sheets-text-to-number.patch: same ids, command and icon)
    convert = b.toolbox("bxHstConvertTextToNumber", [b.button(
        "btnHstConvertTextToNumber", CONVERT_TO_NUMBER, icon="cmd/sc_numberformatstandard.png")], big=False)
    b.place("gdDataExamination", [["bxDataTextToColumns", convert],
                                  ["bxDataHandleDuplicateRecords", "bxDataValidation"],
                                  ["bxDataDataConsolidate", None]])


def review(b):
    b.drop("bxReviewHyphenate")
    b.place("gdReviewSpelling", [["bxReviewSpelling"], ["bxReviewSpellOnline", None]])
    b.style("bxReviewToolProtectionDocument", big=True)
    b.style("bxReviewRedactDoc", big=False)
    b.place("gdReviewDocument", [["bxReviewProtect"], ["bxReviewToolProtectionDocument"],
                                 ["bxReviewShareDocument", "bxReviewRedactDoc"]])


def view(b):
    freeze = b.find("btnViewFreezePanes")  # a split button: the arrow lists first row, first column
    freeze.set("class", "GtkMenuToolButton")
    L.set_prop(freeze, "use-underline", None)
    split = b.toolbox("bxViewHstSplitWindow", [b.take_button("btnViewSplitWindow")], big=False)
    b.place("gdViewFreeze", [["bxFreezeSplit"], [split, "bxHstNewWindow15"], ["bxHstHideSheet", "bxHstShowSheet"]])
    zoom = b.toolbox("bxViewHstZoom", [b.take_button("btnViewZoom")], big=False)
    b.place("gdViewZoom", [["bxViewZoomOptimal"], ["bxViewZoom100Percent", "bxViewZoomPage"], [zoom, None],
                           ["bxViewFullScreen"]])
    b.drop("gdViewHstMacros")  # Run Macro: Extension ▸ Developer


def extension(b):
    nd30 = b.find("btnExtensionHstNd30")
    L.set_prop(nd30, "label", "Văn bản\nhành chính mới")
    utilities = b.find("bxExtensionHstUtilities")
    template = b.find("btnExtensionHstNumberToWords")
    hold = copy.deepcopy(L.holder(b.root, template)[0])
    obj = hold.find("object")
    obj.set("id", "btnExtensionHstConvertEncoding")
    for prop, value in (("label", "Chuyển mã\nsang Unicode"), ("tooltip-text", TOOLTIPS["btnExtensionHstConvertEncoding"]),
                        ("action-name", "org.hst.office.vi:ConvertEncoding"), ("icon-name", "cmd/32/convertencoding.png")):
        L.set_prop(obj, prop, value)
    L.insert_child(utilities, hold)
    # one Developer group: macros, form controls, XML source
    b.style("bxHstXmlSource", big=False)
    b.place("gdToolsMacro", [["bxToolsHstVba"], ["bxToolsRunMacro"], ["bxToolsBasicIDEAppear", "bxToolsMacroDialog"],
                             ["bxHstMacroRecorder", "bxHstMacroSecurity"], ["bxHstFormControls", "bxHstDesignMode"],
                             ["bxHstXmlSource", None]])
    b.drop("gdExtensionHstControls", "gdExtensionHstXml")
    box = b.find("pmhbExtension")
    holds = {h.find("object").get("id"): h for h in box.findall("child")}
    if set(holds) != set(EXTENSION_ORDER) | {"pmhbExtensionAddons"}:
        raise CalcUxError(f"Extension tab groups: {sorted(holds)}")
    for gid in EXTENSION_ORDER + ["pmhbExtensionAddons"]:
        box.remove(holds[gid])
        L.insert_child(box, holds[gid])


def contextual(b):
    for tab, first, macro_box in (("Image", "gdImageImage", "bxImageAssignMacro"),
                                  ("Draw", "gdDraw", "bxDrawAssignMacro"),
                                  ("Object", "gdObject", "bxObjectAssignMacro")):
        columns = [column for column in b.columns_of(first)
                   if not (len(column) == 1 and column[0].get("id") == macro_box)]
        macro = b.detach(b.find(macro_box))
        if tab == "Image":
            save = b.toolbox("bxImageHstSaveGraphic", [b.take_button("btnImageSaveGraphic")], big=False)
            b.style("bxImageCrop", big=True)
            columns = [["bxImageCrop"], ["bxImageCompressGraphic", "bxHstCtxChangePicture"], ["bxImageToggleRotate", save]]
        b.place(first, columns)
        page_box = L.holder(b.root, b.find(first))[1]
        last = [k for k in page_box.findall("child")][-1].find("object").get("id")
        b.new_group(f"gd{tab}HstA11y" if tab != "Object" else "gdObjectPositioning",
                    f"gd{tab}HstMacro", f"lb{tab}HstMacro", *NEW_CAPTIONS[f"lb{tab}HstMacro"], [[macro]], after=last)
    for tab in ("Image", "Draw", "Object", "Media"):
        positioning = f"gd{tab}Positioning"
        transform = b.toolbox(f"bx{tab}HstTransform", [b.take_button(f"btn{tab}TransformDialog")], big=False)
        b.place(positioning, b.columns_of(positioning) + [[transform, None]])
    media = L.holder(b.root, b.find("gdMedia"))
    media[1].remove(media[0])
    L.insert_child(media[1], media[0])


