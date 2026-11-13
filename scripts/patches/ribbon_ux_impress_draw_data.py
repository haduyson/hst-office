# SPDX-License-Identifier: AGPL-3.0-only
"""Strings and tables of the HST Slides and HST Draw ribbon rework (generate-ribbon-ux-impress-draw.py).

Every string is (English msgid, Vietnamese msgstr); the generator writes the English into the .ui files and the
Vietnamese into translations/source/vi/sd/messages.po. Captions and tab labels whose text changes get a new
context (CONTEXT_PREFIX), so a row of l10n/vi-overrides.jsonl for the old context cannot overwrite them.
"""

IMPRESS_UI = "sd/uiconfig/simpress/ui/notebookbar.ui"
DRAW_UI = "sd/uiconfig/sdraw/ui/notebookbar.ui"
IMPRESS_SUPPR = "solenv/sanitizers/ui/modules/simpress.suppr"
DRAW_SUPPR = "solenv/sanitizers/ui/modules/sdraw.suppr"
VI_PO = "translations/source/vi/sd/messages.po"
# new entries go before this entry of sd/messages.po (also the anchor of hst-ribbon-draw.patch)
PO_ANCHOR = 'msgctxt "insertslidesdialog|links"'

CONTEXT_PREFIX = "TabbedImpress|hstUX"
LABEL_CONTEXT = "TabbedImpress|hstRibbonLabel"
DESCRIPTION_CONTEXT = "TabbedImpress|hstRibbonDescription"

# --- ribbon-only labels (hst-ribbon-label): key -> (English, Vietnamese) ---------------------------------
LABELS = {
    "new_slide": ("New Slide", "Trang chiếu mới"),
    "layout": ("Layout", "Bố trí"),
    "from_file": ("Insert from File", "Chèn từ tệp"),
    "arrange": ("Arrange", "Sắp xếp"),
    "align": ("Align", "Căn chỉnh"),
    "fill": ("Fill", "Tô màu"),
    "outline": ("Outline", "Viền"),
    "find": ("Find", "Tìm"),
    "replace": ("Replace", "Thay thế"),
    "fontwork": ("Fontwork", "Chữ nghệ thuật"),
    "slide_number": ("Slide Number", "Số trang chiếu"),
    "date_time": ("Date and Time", "Ngày giờ"),
    "other_object": ("Other Object", "Đối tượng khác"),
    "audio_video": ("Audio and Video", "Âm thanh và video"),
    "interaction": ("Interaction", "Tương tác"),
    "slide_size": ("Slide Size", "Kích cỡ trang chiếu"),
    "format_background": ("Format Background", "Định dạng nền"),
    "change_master": ("Change Slide Master", "Đổi trang chiếu cái"),
    "master_background": ("Master Background", "Nền trang cái"),
    "master_objects": ("Master Objects", "Đối tượng trang cái"),
    "transition_pane": ("Transition Options", "Tùy chọn chuyển tiếp"),
    "animation_pane": ("Animation Pane", "Ngăn hoạt hình"),
    "from_beginning": ("From Beginning", "Từ đầu"),
    "from_current": ("From Current Slide", "Từ trang hiện tại"),
    "rehearse": ("Rehearse Timings", "Diễn tập thời gian"),
    "redact": ("Redact", "Che thông tin"),
    "normal": ("Normal", "Thường"),
    "slide_sorter": ("Slide Sorter", "Sắp xếp trang chiếu"),
    "notes_page": ("Notes Page", "Trang ghi chú"),
    "outline_view": ("Outline View", "Dàn bài"),
    "slide_master": ("Slide Master", "Trang chiếu cái"),
    "notes_master": ("Notes Master", "Ghi chú cái"),
    "handout_master": ("Handout Master", "Bản phát tay cái"),
    "grayscale": ("Grayscale", "Thang xám"),
    "run_macro": ("Run Macro", "Chạy macro"),
    "edit_macros": ("Edit Macros", "Sửa macro"),
    "manage_macros": ("Manage Macros", "Quản lý macro"),
    "macro_security": ("Macro Security", "Bảo mật macro"),
    # HST Draw
    "page_number": ("Page Number", "Số trang"),
    "date": ("Date", "Ngày"),
    "time": ("Time", "Giờ"),
    "bring_front": ("Bring to Front", "Đưa lên trước"),
    "send_back": ("Send to Back", "Gửi ra sau"),
    "merge_shapes": ("Merge Shapes", "Hợp nhất hình"),
    "combine_shapes": ("Combine Shapes", "Kết hợp hình"),
    "master_page": ("Master Page", "Trang cái"),
    "page_pane": ("Page Pane", "Ngăn trang"),
    "export_pdf": ("Export PDF", "Xuất PDF"),
    "pdf_options": ("PDF Export Options", "Tùy chọn xuất PDF"),
    "export_image": ("Export Image", "Xuất ảnh"),
    "sign_pdf": ("Sign PDF File", "Ký tệp PDF"),
    "doc_signatures": ("Document Signatures", "Chữ ký của tài liệu"),
    "text_box": ("Text Box", "Hộp văn bản"),
    "image": ("Image", "Ảnh"),
}

# --- tooltip second lines (hst-ribbon-description): command -> (English, Vietnamese) ----------------------
DESCRIPTIONS = {
    ".uno:Paste": ("Insert the contents of the clipboard.", "Chèn nội dung đã sao chép hoặc cắt."),
    ".uno:Cut": ("Remove the selection and put it on the clipboard.", "Xóa vùng chọn và giữ nó để dán ở chỗ khác."),
    ".uno:Copy": ("Put a copy of the selection on the clipboard.", "Giữ một bản sao của vùng chọn để dán ở chỗ khác."),
    ".uno:FormatPaintbrush": ("Copy the formatting of the selection and apply it to other text or objects.",
                              "Chép định dạng của vùng chọn rồi bấm vào chữ hoặc đối tượng khác để áp dụng."),
    ".uno:InsertPage": ("Add a slide after the current one; the arrow offers layouts and Duplicate Slide.",
                        "Thêm trang chiếu sau trang hiện tại; mũi tên mở các bố trí và Nhân đôi trang chiếu."),
    ".uno:AssignLayout": ("Choose how titles and content are placed on the selected slides.",
                          "Chọn cách đặt tiêu đề và nội dung trên các trang chiếu đang chọn."),
    ".uno:ImportSlideFromFile": ("Insert slides from another presentation.", "Chèn trang chiếu từ một bản trình chiếu khác."),
    ".uno:CharFontName": ("Choose a font for the selected text.", "Chọn phông chữ cho chữ đang chọn."),
    ".uno:FontHeight": ("Change the size of the selected text.", "Đổi cỡ chữ của chữ đang chọn."),
    ".uno:Bold": ("Make the selected text bold.", "Làm đậm chữ đang chọn."),
    ".uno:Italic": ("Make the selected text italic.", "Làm nghiêng chữ đang chọn."),
    ".uno:Underline": ("Underline the selected text.", "Gạch dưới chữ đang chọn."),
    ".uno:Color": ("Change the color of the selected text.", "Đổi màu chữ đang chọn."),
    ".uno:DefaultBullet": ("Start a bulleted list.", "Bắt đầu danh sách có dấu đầu dòng."),
    ".uno:DefaultNumbering": ("Start a numbered list.", "Bắt đầu danh sách đánh số."),
    ".uno:CenterPara": ("Center the paragraph.", "Căn giữa đoạn văn."),
    ".uno:LineSpacing": ("Change the space between lines of text.", "Đổi khoảng cách giữa các dòng chữ."),
    "vnd.sun.star.findbar:FocusToFindbar": ("Find text in the document.", "Tìm chữ trong tài liệu."),
    ".uno:SearchDialog": ("Find text and replace it with other text.", "Tìm chữ và thay bằng chữ khác."),
    ".uno:FillColor": ("Fill the selected shape with a color.", "Tô màu bên trong hình đang chọn."),
    ".uno:XLineColor": ("Change the color of the shape's outline.", "Đổi màu viền của hình đang chọn."),
    ".uno:ObjectPosition": ("Bring the selected objects forward or send them back.",
                            "Đưa đối tượng đang chọn lên trước hoặc ra sau các đối tượng khác."),
    ".uno:ObjectAlign": ("Line up the selected objects.", "Căn các đối tượng đang chọn theo cạnh hoặc theo giữa."),
    ".uno:InsertTable": ("Insert a table.", "Chèn một bảng."),
    ".uno:InsertGraphic": ("Insert a picture from a file.", "Chèn ảnh từ tệp."),
    ".uno:InsertObjectChart": ("Insert a chart.", "Chèn biểu đồ."),
    ".uno:Text": ("Draw a text box anywhere on the page.", "Vẽ một hộp văn bản ở chỗ bất kỳ trên trang."),
    ".uno:FontworkGalleryFloater": ("Insert decorative text.", "Chèn chữ trang trí."),
    ".uno:HyperlinkDialog": ("Link to a web page, a file or another slide.",
                             "Liên kết tới trang web, tệp hoặc trang chiếu khác."),
    ".uno:InsertAnnotation": ("Add a comment about the selection.", "Thêm chú thích cho nội dung đang chọn."),
    ".uno:InsertAVMedia": ("Insert an audio or video file.", "Chèn tệp âm thanh hoặc video."),
    ".uno:SlideSetup": ("Change the size and orientation of the slides.", "Đổi kích cỡ và hướng của trang chiếu."),
    ".uno:HstApplyTransition": ("Choose the effect shown when this slide appears.",
                                "Chọn hiệu ứng khi trang chiếu này xuất hiện."),
    ".uno:HstApplyAnimation": ("Choose how the selected object appears.", "Chọn cách đối tượng đang chọn xuất hiện."),
    ".uno:HstPreviewTransition": ("Play the transition of this slide.", "Phát hiệu ứng chuyển tiếp của trang chiếu này."),
    ".uno:HstApplyTransitionToAll": ("Give every slide the transition, duration and sound of this slide.",
                                     "Áp dụng hiệu ứng, thời lượng và âm thanh chuyển tiếp của trang này cho mọi trang chiếu."),
    ".uno:HstSetTransitionDuration": ("How long the transition lasts, in seconds.",
                                      "Thời lượng của hiệu ứng chuyển tiếp, tính bằng giây."),
    ".uno:HstSetTransitionAdvance": ("Go to the next slide by itself after the given time.",
                                     "Tự chuyển sang trang chiếu kế tiếp sau thời gian đã đặt."),
    ".uno:HstPreviewAnimation": ("Play the animations of this slide.", "Phát các hoạt hình của trang chiếu này."),
    ".uno:CustomAnimation": ("Open the list of animations of this slide.", "Mở danh sách hoạt hình của trang chiếu này."),
    ".uno:Presentation": ("Start the slide show from the first slide.", "Trình chiếu từ trang chiếu đầu tiên."),
    ".uno:PresentationCurrentSlide": ("Start the slide show from the current slide.", "Trình chiếu từ trang chiếu hiện tại."),
    ".uno:RehearseTimings": ("Run the slide show and record how long each slide stays.",
                             "Chạy thử trình chiếu và ghi lại thời gian của từng trang chiếu."),
    ".uno:HideSlide": ("Skip the selected slides in the slide show.", "Bỏ qua các trang chiếu đang chọn khi trình chiếu."),
    ".uno:SpellDialog": ("Check the spelling of the document.", "Kiểm tra chính tả của tài liệu."),
    ".uno:RedactDoc": ("Make a copy with the content you mark blacked out for good.",
                       "Tạo bản sao có phần nội dung đã đánh dấu bị che kín hoàn toàn."),
    ".uno:NormalMultiPaneGUI": ("Edit one slide with the slide pane beside it.", "Soạn từng trang chiếu, có ngăn trang chiếu bên cạnh."),
    ".uno:DiaMode": ("See every slide as a thumbnail to reorder them.", "Xem mọi trang chiếu dạng ảnh nhỏ để sắp xếp lại."),
    ".uno:SlideMasterPage": ("Edit the design shared by the slides.", "Sửa thiết kế dùng chung cho các trang chiếu."),
    # HST Draw and PDF editing
    ".uno:ExportDirectToPDF": ("Save a PDF copy at once, with the last PDF settings.",
                               "Lưu ngay một bản PDF với thiết lập PDF lần trước."),
    ".uno:ExportToPDF": ("Choose the PDF settings, then export.", "Chọn thiết lập PDF rồi xuất."),
    ".uno:ExportTo": ("Save the page as a picture (PNG, JPEG, SVG…).", "Lưu trang thành ảnh (PNG, JPEG, SVG…)."),
    ".uno:SignPDF": ("Digitally sign an existing PDF file.", "Ký số một tệp PDF có sẵn."),
    ".uno:Signature": ("See or add the digital signatures of this document.", "Xem hoặc thêm chữ ký số của tài liệu này."),
    ".uno:BringToFront": ("Put the selected object in front of all others.", "Đặt đối tượng đang chọn lên trên cùng."),
    ".uno:SendToBack": ("Put the selected object behind all others.", "Đặt đối tượng đang chọn xuống dưới cùng."),
    ".uno:PageMode": ("Edit the pages of the drawing.", "Soạn các trang của bản vẽ."),
    ".uno:MasterPage": ("Edit the design shared by the pages.", "Sửa thiết kế dùng chung cho các trang."),
}

# --- group captions and other new or changed strings: key -> (context, English, Vietnamese) --------------
STRINGS = {
    "lbHomeSlide": (CONTEXT_PREFIX + "labelHomeSlide", "Slides", "Trang chiếu"),
    "lbHomeDrawing": (CONTEXT_PREFIX + "labelHomeDrawing", "Drawing", "Bản vẽ"),
    "lbHomeHstEditing": (CONTEXT_PREFIX + "labelHomeEditing", "Editing", "Chỉnh sửa"),
    "lbHomeHstPdfEdit": (CONTEXT_PREFIX + "labelHomePdfEdit", "Edit PDF", "Sửa PDF"),
    "lbInsertSlide": (CONTEXT_PREFIX + "labelInsertSlide", "Slides", "Trang chiếu"),
    "lbInsertText": (CONTEXT_PREFIX + "labelInsertText", "Text", "Văn bản"),
    "lbInsertLinks": (CONTEXT_PREFIX + "labelInsertLinks", "Links", "Liên kết"),
    "lbDesignCustomize": (CONTEXT_PREFIX + "labelDesignCustomize", "Customize", "Tùy chỉnh"),
    "lbPageHstRotate": (CONTEXT_PREFIX + "labelPageRotate", "Rotate", "Xoay trang"),
    "lbTransitionsHstTiming": (CONTEXT_PREFIX + "labelTransitionsTiming", "Timing", "Thời gian"),
    "lbReviewRedact": (CONTEXT_PREFIX + "labelReviewRedact", "Redact", "Che thông tin"),
    "lbViewModeImpress": (CONTEXT_PREFIX + "labelViewMode", "Presentation Views", "Dạng xem"),
    "lbViewModeDraw": (CONTEXT_PREFIX + "labelViewModeDraw", "Views", "Dạng xem"),
    "lbViewMaster": (CONTEXT_PREFIX + "labelViewMaster", "Master Views", "Dạng xem trang cái"),
    "lbViewColor": (CONTEXT_PREFIX + "labelViewColor", "Color/Grayscale", "Màu/Thang xám"),
    "lbViewGrid": (CONTEXT_PREFIX + "labelViewGrid", "Grid and Snap", "Lưới và bám dính"),
    "lbExtensionHstDeveloper": (CONTEXT_PREFIX + "labelExtensionDeveloper", "Developer", "Nhà phát triển"),
    "lbArrangePositioning": (CONTEXT_PREFIX + "labelArrangePosition", "Arrange", "Sắp xếp"),
    "lbArrangeCombination": (CONTEXT_PREFIX + "labelArrangeCombination", "Combine Shapes", "Gộp hình"),
    "lbExportPdf": (CONTEXT_PREFIX + "labelExportPdf", "PDF", "PDF"),
    "lbExportSign": (CONTEXT_PREFIX + "labelExportSign", "Digital Signature", "Ký số"),
    "ExportLabel": ("TabbedDraw|hstUXExportTabLabel", "P~DF", "P~DF"),
    # menu buttons
    "shapes": (CONTEXT_PREFIX + "shapesMenuButton", "Shapes", "Hình dạng"),
    "select": (CONTEXT_PREFIX + "selectMenuButton", "Select", "Chọn"),
    "transform": (CONTEXT_PREFIX + "transformMenuButton", "Transform", "Biến đổi"),
    "snap": (CONTEXT_PREFIX + "snapMenuButton", "Snap", "Bám dính"),
}

# the ND 30 wizard opens a new Writer document; org.hst.office.vi commands show this (Vietnamese) .ui label
ND30_LABEL = "Văn bản\nhành chính mới"
ND30_TOOLTIP = "Tạo văn bản hành chính mới (HST Writer) theo Nghị định 30/2020/NĐ-CP"

# commands of the "Hình dạng ▾" menu; the *Shapes and *Toolbox ones open their shapes as a submenu (Controller.xcu,
# ToolbarAsMenuController); Line and DrawCaption (callout) draw directly
SHAPE_MENU = (".uno:Line", ".uno:ArrowsToolbox", ".uno:LineToolbox", ".uno:BasicShapes", ".uno:SymbolShapes",
              ".uno:ArrowShapes", ".uno:FlowChartShapes", ".uno:CalloutShapes", ".uno:StarShapes", ".uno:ConnectorToolbox",
              ".uno:Objects3DToolbox", ".uno:DrawCaption")
SELECT_MENU = (".uno:SelectAll", ".uno:SelectObject")
TRANSFORM_MENU = (".uno:Shear", ".uno:CrookSlant")
SNAP_TOGGLES = (".uno:GridVisible", ".uno:GridUse", ".uno:HelplinesVisible", ".uno:HelplinesUse",
                ".uno:HelplinesMove", ".uno:SnapBorder", ".uno:SnapFrame", ".uno:SnapPoints", ".uno:CapturePoint")
