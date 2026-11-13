# SPDX-License-Identifier: AGPL-3.0-only
"""Update-check texts: Vietnamese or English following the office UI language (the other HST commands are always Vietnamese)."""

TEXTS = {
    "vi": {
        "title": "Kiểm tra cập nhật",
        "new": "Đã có HST Office %s — bản mới.",
        "current": "Bạn đang dùng %s.",
        "download": "Tải về", "notes": "Xem điểm mới", "skip": "Bỏ qua phiên bản này", "close": "Đóng",
        "uptodate": "Bạn đang dùng phiên bản mới nhất (%s).",
        "autocheck": "Tự động kiểm tra cập nhật khi khởi động", "locked": "Quản trị viên đã khóa cài đặt này.",
        "failed": "Không kiểm tra được cập nhật. Hãy kiểm tra kết nối mạng rồi thử lại sau.",
        "install": "Cập nhật ngay", "later": "Để sau", "cancel": "Hủy",
        "install_title": "Cập nhật HST Office", "progress_title": "Tải bản cập nhật HST Office",
        "checking": "Đang kiểm tra bản cập nhật…", "downloading": "Đang tải bản cập nhật… %d%% (%s)",
        "ready": "Đã tải xong HST Office %s. Đóng HST Office để cập nhật?",
        "err_network": "Không tải được bản cập nhật. Hãy kiểm tra kết nối mạng.",
        "err_verify": "Tệp tải về không hợp lệ (sai kích thước, SHA256 hoặc chữ ký) nên không được cài. Hãy tải thủ công.",
        "err_none": "Bản này không có gói cài đặt tự động cho hệ điều hành của bạn.",
        "err_tools": "Máy này thiếu công cụ cài đặt (Linux: pkexec và apt-get, hoặc pkcon; macOS/Windows: công cụ hệ thống). Hãy tải về và cài thủ công.",
        "err_launch": "Không khởi chạy được trình cập nhật. Hãy tải về và cài thủ công.",
        "err_elevation": "Chưa cập nhật: cài bản mới cần quyền quản trị, nhưng yêu cầu cấp quyền chưa được đồng ý. Hãy thử lại, hoặc bấm Tải về để cài thủ công.",
        "err_unexpected": "Cập nhật HST Office gặp lỗi không mong muốn nên chưa cài được gì. Hãy tải về và cài thủ công.",
        "outcome_auth": "Chưa cài được %s: máy không cấp quyền quản trị để cài đặt.",
        "outcome_install": "Chưa cài được %s: bộ cài báo lỗi (mã %d).",
        "outcome_verify": "Chưa cài được %s: tệp cài đặt không vượt qua bước kiểm tra lần cuối nên đã bị bỏ qua.",
        "outcome_tool": "Chưa cài được %s: máy thiếu công cụ cài đặt.",
        "outcome_wait": "Chưa cài được %s: HST Office không đóng hẳn trong 30 phút.",
        "outcome_readonly": "Chưa cài được %s: HST Office đang chạy thẳng từ tệp .dmg hoặc từ vị trí tạm của macOS, nơi không ghi được. Hãy kéo HST Office vào thư mục Ứng dụng (Applications), mở lại từ đó rồi cập nhật.",
        "move_title": "Chuyển HST Office vào thư mục Ứng dụng",
        "move_ask": "HST Office đang chạy từ %s nên không tự cập nhật được.\nChuyển HST Office vào thư mục Ứng dụng?",
        "move_from_volume": "tệp cài đặt .dmg", "move_from_downloads": "thư mục Tải về",
        "move_from_translocated": "một vị trí tạm của macOS",
        "move": "Chuyển", "move_exists": "Thư mục Ứng dụng đã có HST Office. Mở bản đó thay cho bản này?", "open": "Mở",
        "move_failed": "Không chuyển được HST Office vào thư mục Ứng dụng. Hãy kéo HST Office vào thư mục Ứng dụng trong Finder rồi mở lại từ đó.\nChi tiết trong nhật ký: %s",
        "move_error": "Không chuyển được HST Office vào thư mục Ứng dụng. Hãy kéo HST Office vào thư mục Ứng dụng trong Finder rồi mở lại từ đó.",
        "move_progress": "Đang chuyển HST Office vào thư mục Ứng dụng…",
        "move_slow": "Việc chép HST Office vào thư mục Ứng dụng chưa xong sau 15 phút và có thể vẫn đang chạy. Hãy đợi một lúc rồi mở HST Office từ thư mục Ứng dụng; nếu không thấy, hãy kéo HST Office vào đó trong Finder.",
        "outcome_next": "Bạn vẫn đang dùng bản cũ. Hãy thử lại sau, hoặc bấm Tải về để cài thủ công.\nChi tiết trong nhật ký: %s",
    },
    "en": {
        "title": "Check for Updates",
        "new": "HST Office %s is available — a new version.",
        "current": "You are using %s.",
        "download": "Download", "notes": "What's new", "skip": "Skip this version", "close": "Close",
        "uptodate": "You are using the latest version (%s).",
        "autocheck": "Check for updates automatically at start-up", "locked": "This setting is locked by your administrator.",
        "failed": "Could not check for updates. Check your network connection and try again later.",
        "install": "Update now", "later": "Later", "cancel": "Cancel",
        "install_title": "Update HST Office", "progress_title": "Downloading the HST Office update",
        "checking": "Checking for the update…", "downloading": "Downloading the update… %d%% (%s)",
        "ready": "HST Office %s has been downloaded. Close HST Office to update?",
        "err_network": "The update could not be downloaded. Check your network connection.",
        "err_verify": "The downloaded file is not valid (size, SHA256 or signature) and was not installed. Download it manually.",
        "err_none": "This release has no automatic installer for your operating system.",
        "err_tools": "This computer lacks the installer tools (Linux: pkexec and apt-get, or pkcon; macOS/Windows: system tools). Download and install manually.",
        "err_launch": "The updater could not be started. Download and install manually.",
        "err_elevation": "Not updated: installing the new version needs administrator permission, which was not granted. Try again, or click Download to install manually.",
        "err_unexpected": "The HST Office update hit an unexpected error, so nothing was installed. Download and install manually.",
        "outcome_auth": "%s was not installed: administrator permission was not granted.",
        "outcome_install": "%s was not installed: the installer reported an error (code %d).",
        "outcome_verify": "%s was not installed: the file failed the final check and was skipped.",
        "outcome_tool": "%s was not installed: this computer lacks the installer tools.",
        "outcome_wait": "%s was not installed: HST Office did not close within 30 minutes.",
        "outcome_readonly": "%s was not installed: HST Office runs straight from the .dmg or from a temporary macOS location, which cannot be written. Drag HST Office to the Applications folder, open it from there and update again.",
        "move_title": "Move HST Office to the Applications folder",
        "move_ask": "HST Office runs from %s, so it cannot update itself.\nMove HST Office to the Applications folder?",
        "move_from_volume": "the .dmg installer", "move_from_downloads": "the Downloads folder",
        "move_from_translocated": "a temporary macOS location",
        "move": "Move", "move_exists": "The Applications folder already has HST Office. Open that copy instead of this one?", "open": "Open",
        "move_failed": "HST Office could not be moved to the Applications folder. Drag HST Office to the Applications folder in Finder and open it from there.\nDetails in the log: %s",
        "move_error": "HST Office could not be moved to the Applications folder. Drag HST Office to the Applications folder in Finder and open it from there.",
        "move_progress": "Moving HST Office to the Applications folder…",
        "move_slow": "Copying HST Office to the Applications folder has not finished after 15 minutes and may still be running. Wait a while, then open HST Office from the Applications folder; if it is not there, drag HST Office there in Finder.",
        "outcome_next": "You are still using the old version. Try again later, or click Download to install manually.\nDetails in the log: %s",
    },
}


def ui_language(ctx):
    """'vi' when the office UI language is Vietnamese, else 'en'."""
    import uno  # imported lazily: TEXTS is unit-tested without an office
    try:
        provider = ctx.ServiceManager.createInstanceWithContext("com.sun.star.configuration.ConfigurationProvider", ctx)
        arg = uno.createUnoStruct("com.sun.star.beans.PropertyValue")
        arg.Name, arg.Value = "nodepath", "/org.openoffice.Setup/L10N"
        node = provider.createInstanceWithArguments("com.sun.star.configuration.ConfigurationAccess", (arg,))
        return "vi" if str(node.getByName("ooLocale")).lower().startswith("vi") else "en"
    except Exception:  # noqa: BLE001 - cosmetic; English is the safe fallback for non-Vietnamese systems
        return "en"


def texts(ctx=None):
    import uno  # imported lazily, as in ui_language
    return TEXTS[ui_language(ctx or uno.getComponentContext())]
