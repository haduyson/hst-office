# SPDX-License-Identifier: AGPL-3.0-only
"""The drop-down menus of the HST Sheets ribbon (generate-ribbon-ux-calc.py).

A menu becomes an svtlo-ManagedMenuButton (the button that opens it) and a GtkMenu of GtkMenuItems at the top
of notebookbar.ui; the item labels are translatable (context "TabbedCalc|Menu<name>-<slug>").
"""

# --- drop-down menus (svtlo-ManagedMenuButton): a menu item is (slug, command, English, Vietnamese) or None for
# a separator; a label None keeps the command's own label (function names, the same in every language) --------
MARGINS = "Page.LeftMargin:long={lr}&Page.RightMargin:long={lr}&Page.TopMargin:long={tb}&Page.BottomMargin:long={tb}"


def margins(lr, tb):
    """.uno:CalcPageMargin with the page margins in 1/100 mm (left and right, top and bottom)."""
    return ".uno:CalcPageMargin?" + MARGINS.format(lr=lr, tb=tb)


def paper(number):
    """.uno:CalcPageSize with a value of i18nutil's enum Paper."""
    return f".uno:CalcPageSize?PaperFormat:long={number}"


def function(name):
    """.uno:InsertFunction with a function name: the function with its argument names, as the sidebar's
    function list inserts it (category 0 is the list of every function)."""
    return f".uno:InsertFunction?FunctionName:string={name}&FunctionCategory:short=0"


MORE_FUNCTIONS = ("more", ".uno:FunctionDialog", "More Functions", "Thêm hàm")
FUNCTION_CATEGORIES = [  # (button slug, English, Vietnamese, function names)
    ("Financial", "Financial", "Tài chính", "PMT PV FV NPV IRR RATE NPER SLN DB"),
    ("Logical", "Logical", "Logic", "IF IFS IFERROR IFNA AND OR NOT XOR SWITCH"),
    ("Text", "Text", "Văn bản", "CONCAT TEXTJOIN LEFT RIGHT MID LEN TRIM UPPER LOWER PROPER SUBSTITUTE FIND TEXT VALUE"),
    ("DateTime", "Date and Time", "Ngày giờ", "TODAY NOW DATE DAY MONTH YEAR WEEKDAY DATEDIF NETWORKDAYS"),
    ("Lookup", "Lookup", "Tra cứu", "VLOOKUP HLOOKUP XLOOKUP LOOKUP INDEX MATCH XMATCH CHOOSE OFFSET INDIRECT FILTER UNIQUE SORT"),
    ("Math", "Math", "Toán học", "SUM SUMIF SUMIFS SUMPRODUCT SUBTOTAL ROUND ROUNDUP ROUNDDOWN INT MOD ABS COUNTIF"),
]

# name -> (button id, English, Vietnamese, image (None: text only), big, items)
MENUS = {
    "HstCellsInsert": ("btnHomeHstCellsInsert", "Insert", "Chèn", "cmd/sc_insertcell.png", False, [
        ("cells", ".uno:InsertCell", "Insert Cells", "Chèn ô"),
        ("rows", ".uno:InsertRowsBefore", "Insert Rows Above", "Chèn hàng phía trên"),
        ("columns", ".uno:InsertColumnsBefore", "Insert Columns Before", "Chèn cột bên trái"),
        ("sheet", ".uno:Insert", "Insert Sheet", "Chèn trang tính"),
    ]),
    "HstCellsDelete": ("btnHomeHstCellsDelete", "Delete", "Xóa", "cmd/sc_deletecell.png", False, [
        ("cells", ".uno:DeleteCell", "Delete Cells", "Xóa ô"),
        ("rows", ".uno:DeleteRows", "Delete Rows", "Xóa hàng"),
        ("columns", ".uno:DeleteColumns", "Delete Columns", "Xóa cột"),
        ("sheet", ".uno:Remove", "Delete Sheet", "Xóa trang tính"),
    ]),
    "HstCellsFormat": ("btnHomeHstCellsFormat", "Format", "Định dạng", "cmd/lc_formatcelldialog.png", True, [
        ("rowheight", ".uno:RowHeight", "Row Height", "Chiều cao hàng"),
        ("rowfit", ".uno:SetOptimalRowHeight", "AutoFit Row Height", "Tự khớp chiều cao hàng"),
        ("colwidth", ".uno:ColumnWidth", "Column Width", "Độ rộng cột"),
        ("colfit", ".uno:SetOptimalColumnWidth", "AutoFit Column Width", "Tự khớp độ rộng cột"),
        None,
        ("hiderows", ".uno:HideRow", "Hide Rows", "Ẩn hàng"),
        ("showrows", ".uno:ShowRow", "Unhide Rows", "Hiện hàng"),
        ("hidecols", ".uno:HideColumn", "Hide Columns", "Ẩn cột"),
        ("showcols", ".uno:ShowColumn", "Unhide Columns", "Hiện cột"),
        ("hidesheet", ".uno:Hide", "Hide Sheet", "Ẩn trang tính"),
        ("showsheet", ".uno:Show", "Unhide Sheet", "Hiện trang tính"),
        None,
        ("rename", ".uno:RenameTable", "Rename Sheet", "Đổi tên trang tính"),
        ("tabcolor", ".uno:SetTabBgColor", "Sheet Tab Color", "Màu thẻ trang tính"),
        None,
        ("cells", ".uno:FormatCellDialog", "Format Cells", "Định dạng ô"),
    ]),
    "HstEditingFill": ("btnHomeHstEditingFill", "Fill", "Điền", "cmd/sc_filldown.png", False, [
        ("down", ".uno:FillDown", "Down", "Xuống"),
        ("right", ".uno:FillRight", "Right", "Sang phải"),
        ("up", ".uno:FillUp", "Up", "Lên"),
        ("left", ".uno:FillLeft", "Left", "Sang trái"),
        None,
        ("series", ".uno:FillSeries", "Series", "Chuỗi số"),
        ("sheets", ".uno:FillTable", "Across Sheets", "Sang các trang tính"),
    ]),
    "HstEditingClear": ("btnHomeHstEditingClear", "Clear", "Xóa", "cmd/sc_delete.png", False, [
        ("contents", ".uno:ClearContents", "Clear Contents", "Xóa nội dung"),
        ("formats", ".uno:ResetAttributes", "Clear Formats", "Xóa định dạng"),
        ("comments", ".uno:DeleteNote", "Clear Comments", "Xóa chú thích"),
        None,
        ("choose", ".uno:Delete", "Choose What to Clear", "Chọn nội dung cần xóa"),
    ]),
    "HstEditingSortFilter": ("btnHomeHstEditingSortFilter", "Sort and\nFilter", "Sắp xếp\nvà lọc",
                             "cmd/lc_datasort.png", True, [
        ("ascending", ".uno:SortAscending", "Sort Ascending", "Sắp xếp tăng dần"),
        ("descending", ".uno:SortDescending", "Sort Descending", "Sắp xếp giảm dần"),
        ("custom", ".uno:DataSort", "Custom Sort", "Sắp xếp tùy chỉnh"),
        None,
        ("filter", ".uno:DataFilterAutoFilter", "Filter", "Lọc"),
        ("clear", ".uno:DataFilterRemoveFilter", "Clear Filter", "Xóa lọc"),
        ("customfilter", ".uno:DataFilterStandardFilter", "Custom Filter", "Lọc tùy chỉnh"),
    ]),
    "HstEditingFindSelect": ("btnHomeHstEditingFindSelect", "Find and\nSelect", "Tìm và\nchọn",
                             "cmd/lc_searchdialog.png", True, [
        ("replace", ".uno:SearchDialog", "Find and Replace", "Tìm và thay thế"),
        ("navigator", ".uno:Navigator", "Navigator", "Ngăn dẫn hướng"),
        None,
        ("all", ".uno:SelectAll", "Select All", "Chọn tất cả"),
        ("data", ".uno:SelectData", "Select Data Area", "Chọn vùng dữ liệu"),
        ("unprotected", ".uno:SelectUnprotectedCells", "Select Unprotected Cells", "Chọn ô không bị khóa"),
    ]),
    "HstInsertShapes": ("btnInsertHstShapes", "Shapes", "Hình dạng", "cmd/lc_basicshapes.png", True, [
        ("line", ".uno:Line", "Line", "Đường thẳng"),
        ("arrowline", ".uno:LineArrowEnd", "Line with Arrow", "Đường có mũi tên"),
        None,  # each family below opens its palette as a submenu (ToolbarAsMenuController, as the menu bar)
        ("basic", ".uno:BasicShapes", "Basic Shapes", "Hình cơ bản"),
        ("symbol", ".uno:SymbolShapes", "Symbol Shapes", "Hình biểu tượng"),
        ("arrows", ".uno:ArrowShapes", "Block Arrows", "Mũi tên khối"),
        ("stars", ".uno:StarShapes", "Stars and Banners", "Ngôi sao và băng rôn"),
        ("callouts", ".uno:CalloutShapes", "Callouts", "Khung chú thích"),
        ("flowchart", ".uno:FlowChartShapes", "Flowchart", "Lưu đồ"),
    ]),
    "HstLayoutMargins": ("btnLayoutHstMargins", "Margins", "Lề", "cmd/lc_pagemargin.png", True, [
        ("normal", margins(1800, 1900), "Normal: top and bottom 1.9 cm, left and right 1.8 cm",
         "Thường: trên, dưới 1,9 cm; trái, phải 1,8 cm"),
        ("wide", margins(2540, 2540), "Wide: 2.54 cm on every side", "Rộng: 2,54 cm mỗi bên"),
        ("narrow", margins(640, 1900), "Narrow: top and bottom 1.9 cm, left and right 0.64 cm",
         "Hẹp: trên, dưới 1,9 cm; trái, phải 0,64 cm"),
        None,
        ("custom", ".uno:PageFormatDialog", "Custom Margins", "Lề tùy chỉnh"),
    ]),
    "HstLayoutOrientation": ("btnLayoutHstOrientation", "Orientation", "Hướng giấy", "cmd/lc_orientation.png",
                             True, [
        ("portrait", ".uno:Orientation?isLandscape:bool=false", "Portrait", "Dọc"),
        ("landscape", ".uno:Orientation?isLandscape:bool=true", "Landscape", "Ngang"),
    ]),
    "HstLayoutSize": ("btnLayoutHstSize", "Size", "Khổ giấy", "cmd/lc_attributepagesize.png", True, [
        ("a4", paper(4), "A4 (21 × 29.7 cm)", "A4 (21 × 29,7 cm)"),
        ("a3", paper(3), "A3 (29.7 × 42 cm)", "A3 (29,7 × 42 cm)"),
        ("a5", paper(5), "A5 (14.8 × 21 cm)", "A5 (14,8 × 21 cm)"),
        ("letter", paper(8), "Letter (21.59 × 27.94 cm)", "Letter (21,59 × 27,94 cm)"),
        ("legal", paper(9), "Legal (21.59 × 35.56 cm)", "Legal (21,59 × 35,56 cm)"),
        None,
        ("more", ".uno:PageFormatDialog", "More Paper Sizes", "Khổ giấy khác"),
    ]),
    "HstLayoutPrintArea": ("btnLayoutHstPrintArea", "Print Area", "Vùng in", "cmd/lc_defineprintarea.png", True, [
        ("set", ".uno:DefinePrintArea", "Set Print Area", "Đặt vùng in"),
        ("add", ".uno:AddPrintArea", "Add to Print Area", "Thêm vào vùng in"),
        ("edit", ".uno:EditPrintArea", "Edit Print Ranges and Print Titles", "Sửa vùng in và tiêu đề in"),
        ("clear", ".uno:DeletePrintArea", "Clear Print Area", "Xóa vùng in"),
    ]),
    "HstLayoutBreaks": ("btnLayoutHstBreaks", "Breaks", "Ngắt trang", "cmd/lc_insertrowbreak.png", True, [
        ("row", ".uno:InsertRowBreak", "Insert Row Break", "Chèn ngắt trang trước hàng"),
        ("column", ".uno:InsertColumnBreak", "Insert Column Break", "Chèn ngắt trang trước cột"),
        None,
        ("delrow", ".uno:DeleteRowbreak", "Remove Row Break", "Xóa ngắt trang trước hàng"),
        ("delcolumn", ".uno:DeleteColumnbreak", "Remove Column Break", "Xóa ngắt trang trước cột"),
        ("delall", ".uno:DeleteAllBreaks", "Remove All Page Breaks", "Xóa mọi ngắt trang"),
        None,
        ("preview", ".uno:PagebreakMode", "Page Break Preview", "Xem ngắt trang"),
    ]),
    "HstDataSources": ("btnDataHstOtherSources", "Other\nSources", "Nguồn\nkhác", "cmd/lc_insertexternaldatasource.png",
                       True, [
        ("external", ".uno:InsertExternalDataSource", "External Links", "Liên kết ngoài"),
        ("browser", ".uno:ViewDataSourceBrowser", "Data Sources", "Nguồn dữ liệu"),
        ("streams", ".uno:DataStreams", "Data Streams", "Luồng dữ liệu"),
        ("xml", ".uno:ManageXMLSource", "XML Source", "Nguồn XML"),
        None,
        ("provider", ".uno:DataProvider", "Data Provider", "Nhà cung cấp dữ liệu"),
        ("refresh", ".uno:DataProviderRefresh", "Refresh Data Provider", "Làm mới nhà cung cấp dữ liệu"),
    ]),
}
for _slug, _en, _vi, _names in FUNCTION_CATEGORIES:
    MENUS["HstFunctions" + _slug] = (f"btnFunctionsHst{_slug}", _en, _vi, None, False,
                                     [(n.lower(), function(n), None, None) for n in _names.split()]
                                     + [None, MORE_FUNCTIONS])


NUMBER_TO_WORDS = function("DOCTIEN")  # Công thức ▸ Đọc số
