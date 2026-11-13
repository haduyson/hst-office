# SPDX-License-Identifier: AGPL-3.0-only
"""Group layouts of the Writer ribbon UX rework (generate-ribbon-ux-writer.py), item specs as in
ribbon_ux_writer_engine.py. A group listed here is rebuilt from its columns (or cells); a group a tab
(TABS) no longer lists is removed, with whatever its layout did not take elsewhere."""

VI = "org.hst.office.vi:"
CITE = {"klass": "GtkMenuToolButton", "tlabel": ("Insert\nCitation", "Chèn\ntrích dẫn"),
        "icon": "cmd/32/insertauthoritiesentry.png"}


def cite(name, pair, icon):
    return ("new", f"btnReferencesHst{name}", VI + name, "S", {"tlabel": pair, "icon": icon})


def wrap(tab):
    return ("menu", f"btn{tab}HstWrap", f"Menu HstWrap{tab}", "L", ("Wrap Text", "Ngắt dòng văn bản"),
            "cmd/lc_wrapideal.png")


# group id: {"new": caption (new group), "columns": [[item, ...], ...] or "cells": [(item, left, top, width)]}
GROUPS = {
    # Trang đầu
    "gdHomeClipboard": {"columns": [[("box", "bxHomePaste")], [("box", "bxHomeCut"), ("box", "bxHomeCopy")],
                                    [("box", "bxHomeFormatPaintbrush", "L")]]},
    "gdHomeFont": {"cells": [(("box", "bxHomeCharFontName"), 0, 0, 2), (("box", "bxHomeFontHeight"), 2, 0, 1),
                             (("box", "bxHomeFontSize"), 3, 0, 1), (("box", "bxHomeCharFormat"), 0, 1, 1),
                             (("box", "bxHomeScript"), 1, 1, 1), (("box", "bxHomeCharColor"), 2, 1, 2)]},
    "gdHomeHstEditing": {"new": ("Editing", "Chỉnh sửa"), "columns": [
        [("new", "btnHomeHstFind", "vnd.sun.star.findbar:FocusToFindbar", "S", {"icon": "cmd/sc_recsearch.png"}),
         ("btn", "btnHomeHstSearchDialog", "S")],
        [("menu", "btnHomeHstSelect", "Menu HstHomeSelect", "S", ("Select", "Chọn"), "cmd/sc_selectall.png")]]},
    "gdHomeHstVietnamese": {"new": ("Vietnamese Tools", "Tiện ích Việt"), "columns": [
        [("new", "btnHomeHstNd30", VI + "Nd30Wizard", "L",
          {"label": "Văn bản\nhành chính", "icon": "cmd/32/nd30wizard.png"})],
        [("new", "btnHomeHstConvertEncoding", VI + "ConvertEncoding", "S",
          {"label": "Chuyển mã Unicode", "icon": "cmd/sc_convertencoding.png"}),
         ("new", "btnHomeHstNumberToWords", VI + "NumberToWords", "S",
          {"label": "Đọc số thành chữ", "icon": "cmd/sc_numbertowords.png"})]]},
    # Chèn
    "gdInsertPage": {"columns": [[("box", "bxInsertTitlePageDialog", "L")], [("box", "bxInsertPagebreak", "L")]]},
    "gdInsertGraphic": {"columns": [
        [("box", "bxInsertInsertGraphic", "L")],
        [("menu", "btnInsertHstShapes", "Menu HstInsertShapes", "L", ("Shapes", "Hình dạng"),
          "cmd/lc_basicshapes.png")],
        [("box", "bxInsertInsertObjectChart", "L")],
        [("box", "bxInsertGallery", "S"), ("box", "bxInsertInsertAVMedia", "S")]]},
    "gdInsertReferences": {"columns": [[("box", "bxInsertHyperlinkDialog", "S"), ("box", "bxInsertInsertBookmark", "S")],
                                       [("box", "bxInsertInsertReferenceField", "S")]]},
    "gdInsertHeaderFooter": {"columns": [[("box", "bxHstInsertPageHeader2", "S"), ("box", "bxHstInsertPageFooter3", "S")],
                                         [("box", "boxPageNumberWizard", "L")]]},
    "gdInsertText": {"columns": [
        [("btn", "btnInsertDrawText", "L")],
        [("box", "bxInsertFontworkGalleryFloater", "S"), ("box", "bxInsertInsertFieldCtrl", "S")],
        [("box", "bxHstSignatureLine", "S"), ("box", "bxHstInsertDate", "S")],
        [("box", "bxHstDropcap", "S"), ("box", "bxInsertEditGlossary", "S")],
        [("box", "bxInsertInsertObject", "S")]]},
    "gdInsertSymbols": {"columns": [[("box", "bxInsertInsertObjectStarMath", "S"),
                                     ("box", "bxInsertCharmapControl", "S")]]},
    # Thiết kế
    "gdDesignBackground": {"columns": [
        [("box", "bxHstWatermark5", "L")], [("box", "bxHstFillPageColor", "L")],
        [("new", "btnDesignHstPageBorder", ".uno:BorderDialog?Page:string=hstpageborder", "L",
          {"icon": "cmd/32/borderdialog.png"})], [("box", "bxHstPageDialog6", "L")]]},
    # Bố cục
    "gdLayoutPageLayout": {"columns": [
        [("box", "boxMargin", "L")], [("box", "boOrientation", "L")], [("box", "boxAttributePageSize", "L")],
        [("box", "boxPageColumnType", "L")],
        [("menu", "btnLayoutHstBreaks", "Menu HstLayoutBreaks", "L", ("Breaks", "Ngắt"), "cmd/lc_insertbreak.png")],
        [("box", "boxHyphenate", "S"), ("box", "boxLineNumberingDialog", "S")]]},
    "gdLayoutParagraphLayout": {"columns": [
        [("label", "txtLayoutHstIndent", ("Indent", "Thụt lề"), ["boxLeftParaMargin", "boxRightParaMargin"])],
        [("box", "boxLeftParaMargin"), ("box", "boxRightParaMargin")],
        [("label", "txtLayoutHstSpacing", ("Spacing", "Giãn cách"), ["boxAboveSpacing", "boxBelowSpacing"])],
        [("box", "boxAboveSpacing"), ("box", "boxBelowSpacing")]]},
    # Tham khảo
    "gdReferencesIndex": {"columns": [
        [("box", "bxReferencesInsertMultiIndex", "L")],
        [("box", "bxReferencesUpdateCurIndex", "S"), ("btn", "References-UpdateAll", "S")],
        [("box", "bxReferencesInsertIndexesEntry", "S")]]},
    "gdReferencesHstCitations": {"new": ("Citations", "Trích dẫn"), "columns": [
        [("new", "btnReferencesHstCitationInsert", VI + "CitationInsert", "L", CITE)],
        [cite("CitationReinsert", ("Reinsert Citation", "Chèn lại trích dẫn"), "cmd/sc_insertauthoritiesentry.png"),
         cite("CitationBibliography", ("Bibliography", "Danh mục tài liệu tham khảo"), "cmd/sc_insertmultiindex.png")],
        [cite("CitationStyle", ("Style", "Kiểu"), "cmd/sc_designerdialog.png"),
         cite("CitationUpdate", ("Update", "Cập nhật"), "cmd/sc_updateall.png")],
        [cite("CitationLibrary", ("Manage Sources", "Quản lý nguồn"), "cmd/sc_bibliographycomponent.png")]]},
    "gdReferencesCaptions": {"columns": [
        [("box", "bxReferencesInsertCaptionDialog", "L")],
        [("new", "btnReferencesHstFigureIndex", ".uno:InsertMultiIndex", "S", {}), ("box", "boInsertReferenceField", "S")]]},
    # Xem lại
    "gdReviewHstAccessibility": {"columns": [[("box", "bxHstA11yCheck", "L")]]},
    "gdReviewTrackChanges": {"columns": [[("box", "bxReviewTrackChanges")],
                                         [("btn", "Review-AcceptTrackedChanges", "S")]]},
    "gdReviewProtect": {"columns": [[("box", "bxHstProtectTraceChangeMode12", "L")],
                                    [("new", "btnReviewHstSignature", ".uno:Signature", "L", {})]]},
    # Xem
    "gdViewWidgets": {"columns": [
        [("box", "bxViewSidebar")], [("box", "bxViewRuler"), ("box", "bxViewGridVisible")],
        [("box", "bxViewMenubar"), ("box", "bxViewNavigator")],
        [("box", "bxViewControlCodes"), ("box", "bxViewShowWhitespace")],
        [("box", "bxViewGridUse", "S")], [("box", "bxViewDarkMode")]]},
    "gdViewZoom": {"columns": [
        [("btn", "View-Zoom", "L")], [("box", "bxViewZoomOptimal")],
        [("box", "bxViewZoom100Percent"), ("box", "bxViewZoomPage")],
        [("box", "bxViewFullScreen"), ("box", "bxViewZoomPageWidth")]]},
    # Trợ giúp
    "gdHelpHst": {"columns": [
        [("box", "bxHstHelpIndex")],
        [("new", "btnHelpHstWhereIsCommand", VI + "WhereIsCommand", "L",
          {"tlabel": ("Where Is\nThat Command?", "Lệnh quen thuộc\nở đâu?"), "icon": "cmd/32/extendedhelp.png"})],
        [("new", "btnHelpHstKeyboardShortcuts", VI + "KeyboardShortcuts", "S",
          {"tlabel": ("Keyboard Shortcuts", "Phím tắt"), "icon": "cmd/sc_configuredialog.png"}),
         ("box", "bxHstTipOfTheDay", "S")],
        [("box", "bxHstReportError", "L")],
        [("box", "bxHstUpdateCheck", "S"), ("box", "bxHstAbout", "S")]]},
    # Phần mở rộng
    "gdExtensionHstAddins": {"columns": [[("box", "bxHstExtensionManager")], [("box", "bxHstOptions")],
                                         [("box", "bxHstTemplateManager", "L")]]},
    "gdToolsMacro": {"columns": [
        [("box", "bxToolsHstVba")],
        [("box", "bxToolsRunMacro", "S"), ("box", "bxHstMacroRecorder", "S")],
        [("box", "bxToolsBasicIDEAppear", "S"), ("box", "bxToolsMacroDialog", "S")],
        [("box", "bxHstMacroSecurity", "S"), ("widget", "btnHstContentControls:Menu HstContentControls")],
        [("box", "bxHstDesignMode", "S"), ("box", "bxHstControlProperties", "S")]]},
    # Thiết kế bảng, Bố trí bảng
    "gdTableStyle": {"columns": [
        [("box", "bxTableAutoFormat", "L")],
        [("btn", "btnTableCellBackgroundColor", "S"), ("btn", "btnTableSetBorderStyle", "S")],
        [("btn", "btnTableLineStyle", "S"), ("btn", "btnTableFrameLineColor", "S")]]},
    "gdTableLayout": {"columns": [
        [("btn", "btnTableInsertRowsBefore", "S"), ("btn", "btnTableInsertRowsAfter", "S")],
        [("btn", "btnTableInsertColumnsBefore", "S"), ("btn", "btnTableInsertColumnsAfter", "S")],
        [("menu", "btnTableHstDelete", "Menu HstTableDelete", "L", ("Delete", "Xóa"), "cmd/lc_deletetable.png")]]},
    "gdTableHstMerge": {"new": ("Merge", "Gộp"), "columns": [
        [("box", "bxTableMergeCells", "S"), ("box", "bxTableSplitCell", "S")], [("box", "bxTableSplitTable", "S")]]},
    "gdTableSelect": {"columns": [
        [("menu", "btnTableHstSelect", "Menu HstTableSelect", "L", ("Select", "Chọn"), "cmd/lc_selecttable.png")],
        [("btn", "Table-TableDialog", "S")]]},
    # Định dạng ảnh, Định dạng hình dạng, Đối tượng
    "gdImage": {"columns": [
        [("box", "bxImageInsertCaptionDialog", "L")],
        [("box", "bxImageCrop", "S"), ("box", "bxHstCtxChangePicture", "S")],
        [("box", "bxImageCompressGraphic", "S"), ("btn", "Image-SaveGraphic", "S")],
        [("box", "bxImageToggleRotate", "I"), ("btn", "Image-GraphicDialog", "S")]]},
    "gdImagePositioning": {"columns": [
        [wrap("Image")],
        [("box", "bxHstCtxImagePosition", "S"), ("btn", "btnHstCtxImageNavigator1", "S")],
        [("box", "bxImageAlign1"), ("box", "bxImageAlign2")],
        [("box", "bxImageBringToFront", "S"), ("box", "bxImageSendToBack", "S")],
        [("box", "bxImageObjectForwardOne", "S"), ("box", "bxImageObjectBackOne", "S")]]},
    "gdDrawPositioning": {"columns": [
        [wrap("Draw")],
        [("box", "bxDrawAlign3"), ("box", "bxDrawAlign4")],
        [("box", "bxDrawBringToFront", "S"), ("box", "bxDrawSendToBack", "S")],
        [("box", "bxDrawObjectForwardOne"), ("box", "bxDrawObjectBackOne")],
        [("box", "bxHstCtxDrawNavigator")]]},
    "gdObject": {"columns": [
        [("box", "bxObjectInsertCaptionDialog")], [("box", "bxObjectChainFrames"), ("box", "bxObjectUnhainFrames")],
        [("btn", "Object-FrameDialog", "S")]]},
    # Đầu trang và chân trang
    "gdHeaderFooterHstClose": {"new": ("Close", "Đóng"), "columns": [
        [("new", "btnHstCtxHFClose", ".uno:GoToStartOfPage", "L", {"icon": "cmd/lc_closepreview.png"})]]},
}

# Merged group box of each changed tab: its groups in visual order.
TABS = {
    "pmhbHome": ["gdHomeClipboard", "gdHomeFont", "gdHomeParagraph", "gdHomeStyle", "gdHomeHstEditing",
                 "gdHomeHstVietnamese"],
    "pmhbInsert": ["gdInsertPage", "gdInsertTables", "gdInsertGraphic", "gdInsertReferences", "gdInsertComments",
                   "gdInsertHeaderFooter", "gdInsertText", "gdInsertSymbols"],
    "pmhbReferences": ["gdReferencesIndex", "gdReferencesReference", "gdReferencesHstCitations",
                       "gdReferencesCaptions"],
    "pmhbView": ["gdViewMode", "gdViewWidgets", "gdViewZoom", "gdViewWindow", "gdViewHstMacros"],
    "pmhbExtension": ["gdExtensionHstVietnamese", "gdExtensionHstSolutions", "gdExtensionHstAddins", "gdToolsMacro",
                      "Extension"],
    "pmhbTable": ["gdTableLayout", "gdTableHstMerge", "gdTableSelect", "gdTableAlignment", "gdTableFunctions",
                  "gdTableNumbers"],
    "pmhbImage": ["gdImage", "gdImageFillBorder", "gdImageHstA11y", "gdImagePositioning", "gdImageModify"],
    "pmhbDraw": ["gdDraw", "gdDrawFillBorder", "gdDrawHstA11y", "gdDrawPositioning", "gdDrawGrouping", "gdDraw3D"],
    "pmhbphbHeaderFooter": ["gdHeaderFooterHstMain", "gdHeaderFooterHstInsert", "gdHeaderFooterHstNavigation",
                            "gdHeaderFooterHstOptions", "gdHeaderFooterHstClose"],
}

# Trailing "Tab ▾" blocks that go (their commands left in groups above, or in the menu bar).
BLOCKS = ["Home-Menu", "Insert-Menu", "Layout-Menu", "References-Menu", "Review-Menu", "View-Menu", "Table-Menu",
          "Image-Menu", "Draw-Menu", "Object-Menu", "Media-Menu"]

# Buttons left out of groups that are not rebuilt (the command is in a menu button now).
DROP_BUTTONS = ["btnHstSelectAll"]
# Buttons moved into another toolbox before the groups are rebuilt: (button id, toolbox id).
INTO = [("btnHomeResetAttributes", "bxHomeFontSize")]
