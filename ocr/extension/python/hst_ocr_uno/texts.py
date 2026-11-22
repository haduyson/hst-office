# SPDX-License-Identifier: LicenseRef-HST-Proprietary
"""Vietnamese UI texts of the OCR extension; ERRORS is keyed by the core's stable error codes (protocol.py)."""

TEXTS = {
    "title": "Nhận dạng chữ từ ảnh",
    "pickTitle": "Chọn ảnh cần nhận dạng chữ",
    "running": "Đang nhận dạng chữ từ ảnh…",
    "undo": "Nhận dạng chữ từ ảnh",
    "writerOnly": "Lệnh này dùng trong HST Writer.",
    "nothing": "Không tìm thấy chữ nào trong ảnh.",
}

ERRORS = {
    "engine-missing": "Chưa cài bộ nhận dạng chữ. Hãy cài lại tiện ích Nhận dạng chữ HST.",
    "engine-config": "Cấu hình bộ nhận dạng chữ không hợp lệ.",
    "engine-failed": "Bộ nhận dạng chữ gặp lỗi khi đọc ảnh này.",
    "model-missing": "Thiếu tệp mô hình nhận dạng. Hãy cài lại tiện ích Nhận dạng chữ HST.",
    "timeout": "Ảnh quá lớn hoặc máy đang bận: nhận dạng chưa xong sau 5 phút.",
    "image-missing": "Không tìm thấy tệp ảnh.",
    "image-unreadable": "Không đọc được tệp ảnh này. Hãy dùng ảnh PNG, JPG hoặc TIFF.",
    "image-too-large": "Ảnh quá lớn. Hãy dùng ảnh nhỏ hơn 60 triệu điểm ảnh.",
    "no-content": "Không tìm thấy nội dung nào trong ảnh.",
    "internal": "Bộ nhận dạng chữ gặp lỗi.",
}
