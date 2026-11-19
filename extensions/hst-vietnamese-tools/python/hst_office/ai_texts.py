# SPDX-License-Identifier: AGPL-3.0-only
"""Vietnamese texts and prompts of the Trợ lý AI (the HST tools speak Vietnamese whatever the UI language). Pure."""

COMMON = ("Bạn là Trợ lý AI tích hợp trong HST Office, bộ ứng dụng văn phòng tiếng Việt (HST Writer, HST Sheets, "
          "HST Slides, HST Draw) dựa trên LibreOffice và tương thích Microsoft Office. Trả lời bằng tiếng Việt có dấu, "
          "ngắn gọn và chính xác. Không bịa đặt; nếu không chắc thì nói rõ.")

FORMULA_WRITE = COMMON + (
    " Nhiệm vụ: viết MỘT công thức bảng tính theo mô tả của người dùng. Dòng đầu tiên của câu trả lời chỉ chứa công "
    "thức, bắt đầu bằng dấu =, theo cú pháp Excel: tên hàm tiếng Anh, dấu phẩy ngăn cách đối số, dấu chấm thập phân, "
    "tham chiếu dạng A1 (trang tính khác viết 'Tên trang'!A1). Không dùng khối mã hay dấu `. Bỏ một dòng trống rồi "
    "giải thích ngắn cách công thức hoạt động.")
FORMULA_EXPLAIN = COMMON + (
    " Nhiệm vụ: giải thích công thức bảng tính người dùng gửi cho người không chuyên: công thức tính gì, từng hàm và "
    "đối số, các lỗi có thể gặp (#N/A, #VALUE!...). Nếu có cách viết gọn hoặc an toàn hơn thì gợi ý. Không dùng Markdown.")
HELP = COMMON + (
    " Nhiệm vụ: hướng dẫn cách dùng HST Office theo câu hỏi. Hướng dẫn từng bước, theo giao diện thanh công cụ dạng "
    "thẻ (ribbon) với tên thẻ, nhóm và lệnh tiếng Việt; phím tắt giống Microsoft Office. Nếu không chắc tên chính xác "
    "của một lệnh, hãy nói vậy và gợi ý tìm lệnh bằng ô \"Tìm tính năng\" (Alt+Q). Không dùng Markdown.")
HELP_WITH_MAP = (
    " Khi chỉ chỗ một lệnh, ghi đường dẫn đúng như bản đồ ribbon bên dưới, dạng Thẻ › Nhóm › Lệnh (lệnh trong danh "
    "sách thả xuống: Thẻ › Nhóm › Nút ▾ › Mục). Chỉ dùng tên có trong bản đồ, không tự đặt tên khác. Thẻ [ngữ cảnh] chỉ "
    "hiện khi chọn đối tượng tương ứng (bảng, ảnh, biểu đồ...): nói rõ cần chọn gì trước. Nếu tính năng không có trên "
    "ribbon, nói vậy rồi gợi ý menu chuột phải hoặc ô \"Tìm tính năng\" (Alt+Q).\n\n")


def help_system(ribbon_map):
    """System text of "Hỏi cách dùng": the task plus the ribbon map of the current app when it could be read."""
    return HELP + HELP_WITH_MAP + ribbon_map if ribbon_map else HELP


WRITING = COMMON + (
    " Nhiệm vụ: %s. Chỉ trả về văn bản kết quả: không lời dẫn, không giải thích, không dùng Markdown; giữ nguyên các "
    "ngắt đoạn của văn bản gốc.")

# (label shown in the list, task inserted into WRITING); "custom" takes the user's own instruction
WRITING_MODES = (
    ("Sửa lỗi chính tả và ngữ pháp", "sửa lỗi chính tả, dấu câu và ngữ pháp, giữ nguyên ý và văn phong"),
    ("Viết lại trang trọng (văn phong hành chính)",
     "viết lại theo văn phong hành chính trang trọng, phù hợp Nghị định 30/2020/NĐ-CP về công tác văn thư"),
    ("Viết lại ngắn gọn hơn", "viết lại ngắn gọn hơn, giữ đủ ý chính"),
    ("Viết lại dễ hiểu hơn", "viết lại rõ ràng, dễ hiểu hơn cho người đọc phổ thông"),
    ("Tóm tắt", "tóm tắt các ý chính thành một đoạn ngắn"),
    ("Viết tiếp", "viết tiếp đoạn văn một cách tự nhiên, cùng văn phong (chỉ trả về phần viết thêm)"),
    ("Dịch sang tiếng Anh", "dịch sang tiếng Anh tự nhiên, chính xác"),
    ("Dịch sang tiếng Việt", "dịch sang tiếng Việt tự nhiên, chính xác"),
    ("Theo yêu cầu riêng…", None),
)
CUSTOM_TASK = "làm theo yêu cầu sau của người dùng đối với văn bản: %s"

ACTIONS = {
    "FormulaWrite": "Viết công thức từ mô tả",
    "FormulaExplain": "Giải thích công thức",
    "Writing": "Hỗ trợ viết",
    "Help": "Hỏi cách dùng HST Office",
}

TEXT = {
    "title": "Trợ lý AI",
    "off": "Trợ lý AI đang tắt. Bật và chọn nhà cung cấp tại Công cụ ▸ Tùy chọn ▸ HST Office ▸ Trợ lý AI.",
    "open_options": "Mở Tùy chọn",
    "close": "Đóng",
    "send": "Gửi",
    "preview": "Xem nội dung sẽ gửi",
    "preview_title": "Nội dung sẽ gửi",
    "preview_intro": "Đúng nội dung dưới đây (cùng tên mô hình và khóa API của bạn) sẽ được gửi tới %s khi bấm Gửi:",
    "sending": "Đang gửi tới %s… (có thể mất đến 2 phút)",
    "done": "Đã nhận câu trả lời từ %s.",
    "truncated": " Câu trả lời bị cắt vì quá dài.",
    "using": "Nhà cung cấp: %s · Mô hình: %s",
    "privacy": ("Chỉ khi bấm Gửi, nội dung trong ô trên (và mô tả nhiệm vụ) mới được gửi tới %s bằng khóa API của bạn; "
                "không gửi phần nào khác của tài liệu, tên tệp hay thông tin máy. Chi phí do nhà cung cấp tính theo khóa."),
    "input_formula": "Mô tả công thức cần viết (ví dụ: tổng cột C nếu cột B là \"Đã thu\"):",
    "input_explain": "Công thức cần giải thích:",
    "input_writing": "Văn bản (lấy từ vùng chọn, có thể sửa trước khi gửi):",
    "input_help": "Câu hỏi về cách dùng HST Office:",
    "instruction": "Yêu cầu riêng:",
    "mode": "Việc cần làm:",
    "answer": "Câu trả lời:",
    "insert_formula": "Chèn vào ô %s",
    "replace": "Thay vùng chọn",
    "insert_after": "Chèn sau vùng chọn",
    "empty": "Hãy nhập nội dung trước khi gửi.",
    "too_long": "Nội dung quá dài (tối đa %d ký tự). Hãy chọn đoạn ngắn hơn.",
    "no_formula": "Câu trả lời không có công thức bắt đầu bằng dấu =.",
    "formula_failed": "Không chèn được công thức vào ô. Bạn có thể sao chép công thức từ câu trả lời.",
    "applied": "Đã cập nhật tài liệu (Ctrl+Z để hoàn tác).",
    "undo": "Trợ lý AI",
}

ERRORS = {
    "provider": "Chưa chọn nhà cung cấp. Chọn tại Tùy chọn ▸ HST Office ▸ Trợ lý AI.",
    "nokey": "Chưa có khóa API của nhà cung cấp này. Nhập khóa tại Tùy chọn ▸ HST Office ▸ Trợ lý AI.",
    "key": "Khóa API không hợp lệ hoặc không có quyền dùng mô hình này.",
    "quota": "Nhà cung cấp từ chối vì vượt hạn mức hoặc hết tiền trong tài khoản. Hãy thử lại sau hoặc kiểm tra tài khoản.",
    "model": "Không tìm thấy mô hình này. Chọn mô hình khác trong Tùy chọn (nút \"Tải danh sách\").",
    "request": "Nhà cung cấp không nhận yêu cầu.",
    "server": "Máy chủ của nhà cung cấp đang lỗi hoặc quá tải. Hãy thử lại sau.",
    "blocked": "Nhà cung cấp từ chối trả lời nội dung này.",
    "network": "Không kết nối được tới nhà cung cấp. Kiểm tra mạng, tường lửa hoặc proxy rồi thử lại.",
    "timeout": "Nhà cung cấp không trả lời trong 2 phút. Hãy thử lại hoặc chọn mô hình nhanh hơn.",
    "reply": "Câu trả lời của nhà cung cấp không đọc được.",
    "apply": "Không cập nhật được tài liệu (tài liệu chỉ đọc, vùng được bảo vệ hoặc không còn vùng chọn).",
}


def error_text(error):
    """Vietnamese message of an ai_providers.AiError, with the provider's own reason when it gave one."""
    text = ERRORS.get(error.kind, ERRORS["reply"])
    detail = (error.detail or "").strip()
    return text + ("\n(%s)" % detail if detail else "")


def writing_system(mode_index, instruction=""):
    """System text of the writing help for the chosen mode (WRITING_MODES index)."""
    label, task = WRITING_MODES[mode_index]
    if task is None:
        task = CUSTOM_TASK % instruction.strip()
    return WRITING % task


def extract_formula(answer):
    """The first line of `answer` that is a formula (starts with '='), without code fences or backticks."""
    for line in answer.splitlines():
        line = line.strip().strip("`").strip()
        if line.startswith("="):
            return line
    return None
