# SPDX-License-Identifier: AGPL-3.0-only
"""Update-check texts: Vietnamese or English following the office UI language (the other HST commands are always Vietnamese)."""
import uno

TEXTS = {
    "vi": {
        "title": "Kiểm tra cập nhật",
        "new": "Đã có HST Office %s — bản mới.",
        "current": "Bạn đang dùng %s.",
        "download": "Tải về", "notes": "Xem điểm mới", "skip": "Bỏ qua phiên bản này", "close": "Đóng",
        "uptodate": "Bạn đang dùng phiên bản mới nhất (%s).",
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
    },
    "en": {
        "title": "Check for Updates",
        "new": "HST Office %s is available — a new version.",
        "current": "You are using %s.",
        "download": "Download", "notes": "What's new", "skip": "Skip this version", "close": "Close",
        "uptodate": "You are using the latest version (%s).",
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
    },
}


def ui_language(ctx):
    """'vi' when the office UI language is Vietnamese, else 'en'."""
    try:
        provider = ctx.ServiceManager.createInstanceWithContext("com.sun.star.configuration.ConfigurationProvider", ctx)
        arg = uno.createUnoStruct("com.sun.star.beans.PropertyValue")
        arg.Name, arg.Value = "nodepath", "/org.openoffice.Setup/L10N"
        node = provider.createInstanceWithArguments("com.sun.star.configuration.ConfigurationAccess", (arg,))
        return "vi" if str(node.getByName("ooLocale")).lower().startswith("vi") else "en"
    except Exception:  # noqa: BLE001 - cosmetic; English is the safe fallback for non-Vietnamese systems
        return "en"


def texts(ctx=None):
    return TEXTS[ui_language(ctx or uno.getComponentContext())]
