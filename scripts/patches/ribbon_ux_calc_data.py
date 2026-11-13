# SPDX-License-Identifier: AGPL-3.0-only
"""Data of generate-ribbon-ux-calc.py: the ribbon-only labels, the tooltips' second lines, the group captions,
the drop-down menus and the new buttons of the HST Sheets ribbon (Tabbed notebookbar.ui of Calc).

Every English text is a msgid of the context "TabbedCalc|<id>"; the Vietnamese is its msgstr in
translations/source/vi/sc/messages.po. A renamed group caption gets a new English msgid, so that the older
override rows of l10n/vi-overrides.jsonl (keyed by context and msgid) no longer replace the new Vietnamese.
Commands of the bundled HST extension (org.hst.office.vi:*) have no command label: their .ui label is
Vietnamese in every UI language, as on the Extension tab. The tooltips' second lines are in
ribbon_ux_calc_tips.py, the drop-down menus in ribbon_ux_calc_menus.py.
"""

UI = "sc/uiconfig/scalc/ui/notebookbar.ui"
VI_PO = "translations/source/vi/sc/messages.po"
SUPPR = "solenv/sanitizers/ui/modules/scalc.suppr"
# new po entries go before this entry, which the tarball and an l10n-filled tree both have
PO_ANCHOR = 'msgctxt "TabbedCalc|btnHstCellStyles0"'

# --- ribbon-only labels (hst-ribbon-label): button id -> (English, Vietnamese) ----------------------------
LABELS = {
    # Trang đầu
    "btnHomeAlignTop": ("Align Top", "Căn trên"),
    "btnHomeAlignVCenter": ("Center Vertically", "Căn giữa theo chiều dọc"),
    "btnHomeAlignBottom": ("Align Bottom", "Căn dưới"),
    "btnHomeAlignLeft": ("Align Left", "Căn trái"),
    "btnHomeAlignHorizontalCenter": ("Center", "Căn giữa"),
    "btnHomeAlignRight": ("Align Right", "Căn phải"),
    "btnHomeAlignBlock": ("Justify", "Căn đều"),
    "btnHomeWrapText": ("Wrap Text", "Ngắt dòng"),
    "btnHomeMergeCells": ("Merge and Center", "Gộp và căn giữa"),
    "btnHomeConditionalFormatMenu": ("Conditional\nFormatting", "Định dạng có\nđiều kiện"),
    "btnLayoutAutoFormat": ("Format as Table", "Định dạng bảng"),
    "btnHstAutoSum1": ("AutoSum", "Tự tính tổng"),
    "btnFunctionsHstAutoSum": ("AutoSum", "Tự tính tổng"),
    # Chèn
    "btnInsertDataDataPilotRun": ("Pivot\nTable", "Bảng tổng\nhợp (Pivot)"),
    "btnHstInsertCalcTable": ("Table", "Bảng"),
    "btnInsertInsertObject": ("Other Object", "Đối tượng khác"),
    "btnInsertHyperlinkDialog": ("Link", "Liên kết"),
    "btnInsertHstChartColumn": ("Column", "Cột"),
    "btnInsertHstChartLine": ("Line", "Đường"),
    "btnInsertHstChartPie": ("Pie", "Tròn"),
    # Bố trí trang
    "btnLayoutEditHeaderAndFooter": ("Header and Footer", "Đầu trang và chân trang"),
    "btnHstToggleSheetGrid7": ("Gridlines", "Đường lưới"),
    "btnHstViewRowColumnHeaders8": ("Row and Column Headers", "Tiêu đề hàng, cột"),
    "btnLayoutHstFitWidth": ("Fit All Columns on One Page", "Co vừa một trang ngang"),
    # Công thức
    "btnHstFunctionDialog9": ("Insert Function", "Chèn hàm"),
    "btnInsertFunctionBox1": ("Function List", "Danh sách hàm"),
    "btnFunctionsHstNumberToWords": ("Number to Words", "Đọc số"),
    "btnInsertDefineName": ("Name Manager", "Quản lý tên"),
    "btnInsertAddName": ("Define Name", "Đặt tên vùng"),
    "btnHstCreateNames": ("Create from Selection", "Tạo từ vùng chọn"),
    "btnHstInsertName": ("Use in Formula", "Dùng trong công thức"),
    "btnFunctionsShowPrecedents": ("Trace Precedents", "Truy vết ô nguồn"),
    "btnFunctionsShowDependents": ("Trace Dependents", "Truy vết ô phụ thuộc"),
    "btnHstClearArrows": ("Remove Arrows", "Xóa mũi tên"),
    "btnFunctionsShowInvalid": ("Circle Invalid Data", "Khoanh dữ liệu sai"),
    "btnFunctionsShowErrors": ("Trace Error", "Truy vết lỗi"),
    "btnViewToggleFormula": ("Show Formulas", "Hiện công thức"),
    # Dữ liệu
    "btnHstEditLinks": ("Edit Links", "Liên kết tới tệp ngoài"),
    "btnDataDataSort": ("Sort", "Sắp xếp"),
    "btnDataDataFilterAutoFilter": ("Filter", "Lọc"),
    "btnHstRemoveFilter": ("Clear Filter", "Xóa lọc"),
    "btnDataDataFilterStandardFilter": ("Custom Filter", "Lọc tùy chỉnh"),
    "btnDataDataFilterSpecialFilter": ("Advanced Filter", "Lọc nâng cao"),
    "btnDataDataFilterHideAutoFilter": ("Hide Filter Buttons", "Ẩn nút lọc"),
    "btnDataTextToColumns": ("Text to Columns", "Tách văn bản thành cột"),
    "btnHstConvertTextToNumber": ("Convert to Number", "Chuyển thành số"),
    "btnDataHandleDuplicateRecords": ("Remove Duplicates", "Xóa trùng lặp"),
    "btnDataValidation": ("Data Validation", "Xác thực dữ liệu"),
    "btnDataDataConsolidate": ("Consolidate", "Hợp nhất dữ liệu"),
    "btnFunctionsGoalSeekDialog": ("Goal Seek", "Tìm mục tiêu"),
    "btnFunctionsSolverDialog": ("Solver", "Bộ giải (Solver)"),
    "btnDataDataSubTotals": ("Subtotal", "Tổng phụ"),
    "btnDataGroup": ("Group", "Nhóm"),
    "btnDataUngroup": ("Ungroup", "Bỏ nhóm"),
    "btnDataHideDetail": ("Hide Detail", "Ẩn chi tiết"),
    "btnDataShowDetail": ("Show Detail", "Hiện chi tiết"),
    # Xem lại
    "btnReviewTraceChangeMode": ("Track\nChanges", "Theo dõi\nthay đổi"),
    "btnReviewAcceptChanges": ("Accept or\nReject", "Chấp nhận/\nTừ chối"),
    "btnReviewMergeDocuments": ("Merge Documents", "Gộp tài liệu"),
    "btnReviewProtect": ("Protect\nSheet", "Bảo vệ\ntrang tính"),
    "btnReviewToolProtectionDocument": ("Protect\nWorkbook", "Bảo vệ sổ\nlàm việc"),
    "btnReviewRedactDoc": ("Redact", "Che thông tin"),
    # Xem
    "btnHstNormalViewMode13": ("Normal", "Thường"),
    "btnHstPagebreakMode14": ("Page Break Preview", "Xem ngắt trang"),
    "btnHstViewPageLayout": ("Print Preview", "Xem trước khi in"),
    "btnViewToggleSheetGrid": ("Gridlines", "Đường lưới"),
    "btnViewViewRowColumnHeaders": ("Row and Column Headers", "Tiêu đề hàng, cột"),
    "btnViewFreezePanes": ("Freeze Panes", "Cố định ngăn"),
    "btnViewSplitWindow": ("Split", "Chia cửa sổ"),
    "btnHstHideSheet": ("Hide Sheet", "Ẩn trang tính"),
    "btnHstShowSheet": ("Unhide Sheet", "Hiện trang tính"),
    # Phần mở rộng ▸ Nhà phát triển
    "btnToolsRunMacro": ("Run Macro", "Chạy macro"),
    "btnToolsBasicIDEAppear": ("Edit Macros", "Sửa macro"),
    "btnToolsMacroDialog": ("Manage Macros", "Quản lý macro"),
    "btnHstMacroRecorder": ("Record Macro", "Ghi macro"),
    "btnHstMacroSecurity": ("Macro Security", "Bảo mật macro"),
    "btnHstXmlSource": ("XML Source", "Nguồn XML"),
    "btnHstDesignMode0": ("Design Mode", "Chế độ thiết kế"),
    # thẻ ngữ cảnh
    "btnImageAssignMacro": ("Assign Macro", "Gán macro"),
    "btnDrawAssignMacro": ("Assign Macro", "Gán macro"),
    "btnObjectAssignMacro": ("Assign Macro", "Gán macro"),
    "btnMediaAssignMacro": ("Assign Macro", "Gán macro"),
}


# --- group captions: caption label id -> (English, Vietnamese) ----------------------------------------------
CAPTIONS = {
    "lbDataSort": ("Sort and Filter", "Sắp xếp và lọc"),
    "lbFunctionsDetective": ("Formula Checking", "Kiểm tra công thức"),
    "lbFunctionsGoalSeeker": ("What-If Analysis", "Phân tích giả định"),
    "lbDataSubtotal": ("Group and Subtotal", "Nhóm và tổng phụ"),
    "lbToolsMacro": ("Developer", "Nhà phát triển"),
    "lbImageFillBorder": ("Fill and Border", "Tô và viền"),
    "lbDrawFillBorder": ("Fill and Border", "Tô và viền"),
    "lbObjectFillBorder": ("Fill and Border", "Tô và viền"),
    "lbMedia": ("Macro", "Macro"),
}
NEW_CAPTIONS = {
    "lbImageHstMacro": ("Macro", "Macro"),
    "lbDrawHstMacro": ("Macro", "Macro"),
    "lbObjectHstMacro": ("Macro", "Macro"),
}

# --- new tool buttons ---------------------------------------------------------------------------------------
FIT_WIDTH_COMMAND = ".uno:HstFitToPagesWide"
# split buttons and chart types of hst-ribbon-ux-calc-commands.patch
SPLIT_BUTTONS = ("btnHstAutoSum1", "btnHomeMergeCells")  # Controller.xcu: popups hstautosum, hstmergecells
CHART_TYPES = [("Column", "chart2/res/typecolumn_16.png"), ("Line", "chart2/res/typepointline_16.png"),
               ("Pie", "chart2/res/typepie_16.png")]  # .uno:InsertObjectChart?ChartType:string=<type>
CONVERT_TO_NUMBER = ".uno:HstConvertTextToNumber"  # hst-sheets-text-to-number.patch (its ids and icon)

# --- Phần mở rộng: Vietnamese utility groups first, then the other HST groups, then one developer group -----
EXTENSION_ORDER = ["gdExtensionHstText", "gdExtensionHstFormats", "gdExtensionHstData", "gdExtensionHstUtilities",
                   "gdExtensionHstSolutions", "gdExtensionHstAddins", "gdToolsMacro"]
# the trailing "<tab> ▾" blocks that go (the Extension tab keeps its add-on menus block)
DROP_BLOCKS = ["Home-Menu", "Insert-Menu", "Layout-Menu", "Data-Menu", "Reference-Menu", "View-Menu",
               "Image-Menu", "Draw-Menu", "Object-Menu", "Media-Menu"]

TOOLTIPS = {  # Vietnamese tooltips of extension-command buttons (no command label, product policy)
    "btnHomeHstFormatVnd": "Định dạng tiền đồng (₫)",
    "btnHomeHstFormatDate": "Định dạng ngày dd/mm/yyyy; mũi tên: các kiểu ngày khác",
    "btnDataHstImportCsv": "Mở tệp văn bản hoặc CSV (UTF-8)",
    "btnExtensionHstConvertEncoding": "Chuyển chữ mã TCVN3 hoặc VNI trong vùng ô đã chọn sang Unicode",
}
