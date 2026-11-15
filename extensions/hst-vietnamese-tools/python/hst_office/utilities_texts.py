# SPDX-License-Identifier: AGPL-3.0-only
"""Messages of the Vietnamese utilities (Sheets and Writer); Vietnamese in every UI language (HST policy)."""

TITLE = "Tiện ích tiếng Việt"
UNDO = {"diacritics": "Bỏ dấu", "split": "Tách họ tên", "sort": "Sắp xếp theo tên", "blank": "Xóa dòng trống",
        "words": "Đọc số thành chữ"}
NUMBER_ERRORS = {
    "too-many-digits": "Số có hơn 15 chữ số phần nguyên: bảng tính không lưu chính xác số lớn như vậy, nên không đọc.",
    "not-a-number": "Không đọc được số: %s",
    "bad-option": "Cách đọc không hợp lệ: %s",
}
MESSAGES = {
    "protected": "Trang tính đang được bảo vệ.",
    "no-cells": "Hãy chọn ô trước.",
    "one-range": "Hãy chọn một vùng ô liền nhau.",
    "one-column": "Hãy chọn một cột chứa họ tên (có thể chọn cả dòng tiêu đề).",
    "diacritics-done": "Đã bỏ dấu %d ô. Công thức và số không thay đổi.",
    "diacritics-none": "Vùng chọn không có ô văn bản có dấu.",
    "split-done": "Đã tách %d họ tên vào hai cột mới “Họ đệm” và “Tên” bên phải.",
    "sort-done": "Đã sắp xếp %d dòng theo tên, rồi theo họ đệm (cột %s).",
    "sort-none": "Không tìm thấy cột họ tên. Hãy chọn bảng có tiêu đề như “Họ và tên” hoặc “Tên”.",
    "blank-done": "Đã xóa %d dòng trống.",
    "blank-none": "Không có dòng trống trong vùng này.",
    "writer-selection": "Hãy chọn (bôi đen) một số trong văn bản, ví dụ 1.250.000.",
    "writer-protected": "Vùng chọn nằm trong phần được bảo vệ hoặc chỉ đọc.",
    "bad-cell": "Địa chỉ ô không hợp lệ: %s",
    "empty-cell": "Ô %s không chứa số.",
    "number-column": "Hãy chọn một ô hoặc một cột chứa số (một hay nhiều dòng): chữ được ghi vào cột bên phải.",
    "target-overlap": "Ô ghi kết quả nằm trong vùng chứa số. Hãy chọn ô ở cột khác.",
    "target-outside": "Cột ghi kết quả không đủ dòng cho vùng chứa số.",
    "range-done": "Đã ghi %d ô.",
    "range-skipped": "Đã ghi %d ô, bỏ qua %d ô không phải số (hoặc có hơn 15 chữ số).",
    "range-none": "Vùng %s không có ô số nào để đọc (bỏ qua %d ô).",
    "write-failed": "Không ghi được vào cột kết quả (trang tính được bảo vệ hoặc tệp chỉ đọc).",
    "file-default-failed": "Đã ghi kết quả, nhưng không lưu được đơn vị mặc định vào tệp này.",
}
HEADER_FAMILY, HEADER_GIVEN = "Họ đệm", "Tên"
DIALOG = {
    "title": "Đọc số thành chữ",
    "writerTitle": "Đọc số thành chữ",  # one name in every app, as the HST menu shows it
    "source": "Ô chứa số:", "target": "Ghi vào ô:", "number": "Số được chọn:",
    "kind": "Đọc thành:", "kinds": ("Số (hàm DOCSO)", "Số tiền (hàm DOCTIEN)"), "writerKinds": ("Số", "Số tiền"),
    "unitPreset": "Đơn vị tiền:", "presets": ("đồng", "dollar / cent", "Tùy chỉnh"),
    "unit": "Đơn vị:", "subUnit": "Đơn vị lẻ:",
    "thousand": "Hàng nghìn:", "thousands": ("nghìn", "ngàn"),
    "odd": "Số 0 hàng chục:", "odds": ("lẻ (một trăm lẻ năm)", "linh (một trăm linh năm)"),
    "four": "Số 4 sau mươi:", "fours": ("bốn (hai mươi bốn)", "tư (hai mươi tư)"),
    "language": "Ngôn ngữ:", "languages": ("Tiếng Việt", "Tiếng Anh"),
    "output": "Ghi kết quả:", "outputs": ("Chữ (giữ nguyên khi mở bằng phần mềm khác)", "Công thức (tự cập nhật, chỉ HST Office hiểu)"),
    "preview": "Xem trước:", "insert": "Chèn", "replace": "Thay thế",
    "fileDefault": "Dùng làm mặc định cho tệp này", "fileDefaultHint": "Đang dùng mặc định của tệp",
    "occupied": "%d ô ở cột ghi kết quả đã có dữ liệu. Bấm “Ghi đè” để thay thế, hoặc đổi ô ghi.",
    "overwrite": "Ghi đè",
}
# Tùy chọn ▸ HST Office ▸ Đọc số và tiền: the short entries of its lists (number_words_defaults.CHOICES order)
OPTIONS_PAGE = {"thousand": ("nghìn", "ngàn"), "odd": ("lẻ", "linh"), "four": ("bốn", "tư"),
                "language": DIALOG["languages"]}
# unit, sub-unit of each preset; "đồng" reads whole đồng (to read "xu", choose "Tùy chỉnh" and type it)
PRESETS = (("đồng", ""), ("dollar", "cent"))
# the warning before a Sheets document with HST functions is saved as .xlsx/.xls (save_format_check.py); %s of the
# title and the text's second %s are the file extension, e.g. ".xlsx". No product of another vendor is named.
SAVE_TITLE = "Lưu sang định dạng %s"
SAVE_TEXT = ("Các hàm %s chỉ có trong HST Office: nếu tệp định dạng %s được mở bằng phần mềm bảng tính khác, %d ô "
             "dùng các hàm này sẽ báo lỗi #NAME?.\n\nChọn “Chuyển thành giá trị khi lưu” để tệp được lưu chứa kết quả "
             "hiện tại của các ô đó; công thức trong bảng tính đang mở vẫn giữ nguyên.")
SAVE_DONT_ASK = "Không hỏi lại"
SAVE_BUTTONS = ("Chuyển thành giá trị khi lưu", "Vẫn lưu", "Hủy")
# Tùy chọn ▸ HST Office ▸ Đọc số và tiền: the remembered answer (save_format_prefs.PAGE_ORDER order)
SAVE_OPTIONS = ("Hỏi mỗi lần", "Chuyển thành giá trị khi lưu", "Vẫn lưu công thức")
