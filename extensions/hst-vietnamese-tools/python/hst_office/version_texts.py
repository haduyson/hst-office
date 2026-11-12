# SPDX-License-Identifier: AGPL-3.0-only
"""Vietnamese texts of "Phiên bản trước" (dialog, options page) and their pure formatting helpers (HST policy: the
HST tools speak Vietnamese in every UI language and never name another office product)."""
import time

TITLE = "Phiên bản trước"
FILE = "Tệp:"
LIST = "Các bản đã bị lưu đè, mới nhất ở trên:"
EMPTY = ("Chưa có phiên bản trước nào của tệp này.\n"
         "HST Office cất một bản mỗi khi bạn lưu đè lên tệp đã có trên đĩa. Lần lưu đầu tiên của một tệp mới "
         "chưa có bản cũ để cất.")
NOT_SAVED = "Tài liệu này chưa được lưu thành tệp nên chưa có phiên bản trước."
NOT_LOCAL = "Tài liệu này không nằm trên ổ đĩa của máy nên HST Office không cất phiên bản trước cho nó."
DISABLED = ("Tính năng đang tắt nên HST Office không cất thêm bản mới khi lưu. Bật lại trong "
            "Công cụ ▸ Tùy chọn ▸ HST Office ▸ Phiên bản trước.")
DISABLED_LOCKED = "Bộ phận CNTT đã tắt tính năng này nên HST Office không cất thêm bản mới khi lưu."
HINT = "Mở xem: mở một bản sao chỉ đọc, tệp của bạn không đổi."
OPEN = "Mở xem"
RESTORE = "Khôi phục"
CLOSE = "Đóng"
CONFIRM = ("Khôi phục bản lưu lúc %s?\nBản hiện tại trên đĩa được cất thành một phiên bản trước, rồi tệp được thay "
           "bằng bản này. Cửa sổ tài liệu sẽ đóng và mở lại.")
CONFIRM_UNSAVED = " Các thay đổi chưa lưu trong cửa sổ này sẽ bị bỏ."
CONFIRM_YES = "Khôi phục bản này"
CONFIRM_NO = "Không"
VIEW_NAME = "%s (bản %s)%s"  # stem, time, extension of the read-only copy

ERROR_TITLE = "Phiên bản trước"
ERRORS = {
    "missing": "Không tìm thấy bản đã lưu này trong kho (có thể vừa bị xóa). Hãy mở lại hộp thoại Phiên bản trước.",
    "corrupt": "Bản đã lưu này bị hỏng nên không dùng được. Tệp của bạn vẫn giữ nguyên.",
    "keep": "Không cất được bản hiện tại của tệp nên HST Office chưa khôi phục. Tệp của bạn vẫn giữ nguyên.",
    "stage": "Không ghi được vào thư mục chứa tệp (có thể ổ đĩa chỉ đọc hoặc đầy). Tệp của bạn vẫn giữ nguyên.",
    "close": "Không đóng được tài liệu để khôi phục. Tệp của bạn vẫn giữ nguyên.",
    "replace": ("Không thay được tệp (có thể tệp đang được chương trình khác mở). Tệp của bạn vẫn giữ nguyên; "
                "bản hiện tại cũng đã được cất trong Phiên bản trước."),
    "reopen": "Đã khôi phục tệp nhưng không mở lại được. Hãy mở tệp bằng Tệp tin ▸ Mở.",
    "busy": "Kho phiên bản đang bận. Hãy thử lại sau giây lát.",
    "open": "Không mở được bản đã lưu này.",
}

OPTIONS_LOCKED = "Bộ phận CNTT đã khóa cài đặt này."
USAGE_EMPTY = "Chưa có phiên bản nào được lưu."
USAGE = "Đang lưu %d phiên bản của %d tệp, tổng %s."
CLEAR_CONFIRM = "Xóa vĩnh viễn mọi phiên bản đã lưu của mọi tệp? Các tệp của bạn không bị ảnh hưởng."
CLEARED = "Đã xóa %d phiên bản."
CLEAR_FAILED = "Không xóa được vì kho phiên bản đang bận. Hãy thử lại."


def _decimal(value):
    """One decimal with a Vietnamese decimal comma, none for whole numbers: 1,2 / 15."""
    text = ("%.1f" % value).rstrip("0").rstrip(".")
    return text.replace(".", ",")


def format_size(size):
    """Vietnamese size: 512 byte, 3,4 KB, 1,2 MB, 2 GB."""
    size = max(0, int(size))
    if size < 1024:
        return "%d byte" % size
    for unit, factor in (("KB", 1024), ("MB", 1024 ** 2), ("GB", 1024 ** 3)):
        if size < factor * 1024 or unit == "GB":
            value = size / factor
            return "%s %s" % (_decimal(value) if value < 100 else "%d" % round(value), unit)
    return "%d byte" % size  # not reached


def format_time(seconds, localtime=time.localtime):
    """Local time of this computer, day first: 12/11/2026 10:15:32."""
    return time.strftime("%d/%m/%Y %H:%M:%S", localtime(seconds))


def item_label(version, localtime=time.localtime):
    return "%s · %s" % (format_time(version.saved, localtime), format_size(version.size))


def usage_label(documents, copies, total):
    return USAGE % (copies, documents, format_size(total)) if copies else USAGE_EMPTY
