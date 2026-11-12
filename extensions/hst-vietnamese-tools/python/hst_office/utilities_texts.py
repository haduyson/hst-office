# SPDX-License-Identifier: AGPL-3.0-only
"""Messages of the Vietnamese utilities (Sheets and Writer); Vietnamese in every UI language (HST policy)."""

TITLE = "Tiện ích tiếng Việt"
UNDO = {"diacritics": "Bỏ dấu", "split": "Tách họ tên", "sort": "Sắp xếp theo tên", "blank": "Xóa dòng trống",
        "words": "Đổi số thành chữ", "toText": "Đổi hàm HST thành chữ"}
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
}
HEADER_FAMILY, HEADER_GIVEN = "Họ đệm", "Tên"
DIALOG = {
    "title": "Đọc số thành chữ",
    "writerTitle": "Đổi số thành chữ",
    "source": "Ô chứa số:", "target": "Ghi vào ô:", "number": "Số được chọn:",
    "kind": "Đọc thành:", "kinds": ("Số (hàm DOCSO)", "Số tiền (hàm DOCTIEN)"), "writerKinds": ("Số", "Số tiền"),
    "unitPreset": "Đơn vị tiền:", "presets": ("đồng", "dollar / cent", "Tùy chỉnh"),
    "unit": "Đơn vị:", "subUnit": "Đơn vị lẻ:",
    "thousand": "Hàng nghìn:", "thousands": ("nghìn", "ngàn"),
    "odd": "Số 0 hàng chục:", "odds": ("lẻ (một trăm lẻ năm)", "linh (một trăm linh năm)"),
    "four": "Số 4 sau mươi:", "fours": ("bốn (hai mươi bốn)", "tư (hai mươi tư)"),
    "language": "Ngôn ngữ:", "languages": ("Tiếng Việt", "Tiếng Anh"),
    "output": "Ghi kết quả:", "outputs": ("Chữ (giữ nguyên khi mở bằng Excel)", "Công thức (tự cập nhật, chỉ HST Office hiểu)"),
    "preview": "Xem trước:", "insert": "Chèn", "replace": "Thay thế",
}
# unit, sub-unit of each preset; "đồng" reads whole đồng (to read "xu", choose "Tùy chỉnh" and type it)
PRESETS = (("đồng", ""), ("dollar", "cent"))
# Saving an Excel file with cells that use the HST functions (save_format_check.py)
SAVE_TITLE = "Lưu tệp Excel"
SAVE_TEXT = ("Microsoft Excel sẽ không hiểu các hàm riêng của HST Office (%s): trong Excel, %d ô dùng các hàm này sẽ "
             "báo lỗi #NAME?.\n\nChọn “Đổi thành chữ rồi lưu” để tệp Excel chứa kết quả bằng chữ; các công thức vẫn giữ "
             "trong bảng tính đang mở, trừ khi bạn đánh dấu ô bên dưới.")
SAVE_IN_DOCUMENT = "Đổi luôn thành chữ trong bảng tính đang mở"
SAVE_BUTTONS = ("Đổi thành chữ rồi lưu", "Vẫn lưu", "Hủy")
