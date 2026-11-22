# SPDX-License-Identifier: LicenseRef-HST-Proprietary
# Copyright (C) 2026 HASON TECH
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
        "ready_password": "Đã tải xong HST Office %s. Sau khi HST Office đóng, máy Mac sẽ hỏi mật khẩu quản trị để thay ứng dụng: hãy nhập mật khẩu, nếu bỏ qua thì bản cập nhật không được cài. Đóng HST Office để cập nhật?",
        "err_network": "Không tải được bản cập nhật. Hãy kiểm tra kết nối mạng.",
        "err_verify": "Tệp tải về không hợp lệ (sai kích thước, SHA256 hoặc chữ ký) nên không được cài. Hãy tải thủ công.",
        "err_none": "Bản này không có gói cài đặt tự động cho hệ điều hành của bạn.",
        "err_tools": "Máy này thiếu công cụ cài đặt (Linux: pkexec cùng apt-get, dnf, zypper hoặc rpm, hoặc pkcon; macOS/Windows: công cụ hệ thống). Hãy tải về và cài thủ công.",
        "err_appimage_dir": "Không ghi được vào thư mục chứa tệp AppImage của HST Office nên không tự cập nhật được. Hãy chuyển tệp AppImage vào một thư mục của bạn (ví dụ thư mục Ứng dụng trong thư mục cá nhân), hoặc bấm Tải về để tải bản mới.",
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
        "outcome_stopped": "Chưa cài được %s: trình cập nhật đã dừng trước khi cài.",
        "err_quit": "HST Office chưa đóng được nên chưa cập nhật. Hãy lưu hoặc đóng các tài liệu và đóng các hộp thoại đang mở, rồi bấm Thử lại.",
        "retry": "Thử lại",
        "installed": "Đã cập nhật lên HST Office %s.",
        "popup_text": "Đã có HST Office %s. Bạn đang dùng %s.",
        "outcome_busy": "Chưa cài được %s: HST Office vẫn đang mở khi trình cập nhật cần thay ứng dụng.",
        "helper_installing": "Đang cài bản cập nhật HST Office. Ứng dụng sẽ tự mở lại, vui lòng chờ.",
        "helper_busy": "HST Office vẫn đang mở nên chưa thay được ứng dụng. Hãy thoát HST Office để hoàn tất cập nhật.",
        "helper_busy_failed": "Chưa cài được bản cập nhật HST Office vì ứng dụng vẫn đang mở. Hãy thoát HST Office rồi cập nhật lại.",
        "helper_old_running": "Đã cài bản cập nhật HST Office. Nếu cửa sổ HST Office đang mở được mở trong lúc cập nhật, hãy thoát rồi mở lại để dùng bản mới.",
        "helper_failed": "Chưa cài được bản cập nhật HST Office. Hãy tải bản cài đặt tại office.hasontech.vn và cài thủ công.",
        "guard_updating": "HST Office đang cài bản cập nhật. Ứng dụng sẽ tự mở lại khi cài xong, vui lòng chờ.",
        "preparing": "Đang chuẩn bị bản cập nhật… HST Office sẽ đóng rồi tự mở lại ngay khi chuẩn bị xong.",
        "err_readonly": "Chưa cập nhật được: HST Office đang chạy thẳng từ tệp .dmg hoặc từ vị trí tạm của macOS, nơi không ghi được. Hãy kéo HST Office vào thư mục Ứng dụng (Applications), mở lại từ đó rồi cập nhật.",
        "err_prepare": "Chưa chuẩn bị được bản cập nhật (không gắn được tệp .dmg hoặc không chép được ứng dụng) nên chưa cài gì. Hãy tải về và cài thủ công.",
        "guard_replaced": "HST Office vừa được cập nhật lên %s trong khi bản %s đang chạy. HST Office sẽ đóng và tự mở lại bản mới.",
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
        "ready_password": "HST Office %s has been downloaded. Once HST Office closes, your Mac will ask for an administrator password to replace the app: enter it, or the update is not installed. Close HST Office to update?",
        "err_network": "The update could not be downloaded. Check your network connection.",
        "err_verify": "The downloaded file is not valid (size, SHA256 or signature) and was not installed. Download it manually.",
        "err_none": "This release has no automatic installer for your operating system.",
        "err_tools": "This computer lacks the installer tools (Linux: pkexec with apt-get, dnf, zypper or rpm, or pkcon; macOS/Windows: system tools). Download and install manually.",
        "err_appimage_dir": "The folder that holds the HST Office AppImage cannot be written, so it cannot update itself. Move the AppImage into a folder of your own (for example Applications in your home folder), or click Download to get the new version.",
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
        "outcome_stopped": "%s was not installed: the updater stopped before installing.",
        "err_quit": "HST Office could not close, so it was not updated. Save or close your documents and close any open dialogs, then click Try again.",
        "retry": "Try again",
        "installed": "HST Office has been updated to %s.",
        "popup_text": "HST Office %s is available. You are using %s.",
        "outcome_busy": "%s was not installed: HST Office was still open when the updater had to replace the app.",
        "helper_installing": "Installing the HST Office update. The app will open again by itself, please wait.",
        "helper_busy": "HST Office is still open, so the app cannot be replaced yet. Quit HST Office to finish the update.",
        "helper_busy_failed": "The HST Office update was not installed because the app is still open. Quit HST Office and update again.",
        "helper_old_running": "The HST Office update is installed. If the HST Office window that is open was opened during the update, quit it and open it again to use the new version.",
        "helper_failed": "The HST Office update could not be installed. Download the installer from office.hasontech.vn and install it manually.",
        "guard_updating": "HST Office is installing an update. The app will open again by itself when it is done, please wait.",
        "preparing": "Preparing the update… HST Office will close and open again by itself as soon as it is ready.",
        "err_readonly": "Not updated: HST Office runs straight from the .dmg or from a temporary macOS location, which cannot be written. Drag HST Office to the Applications folder, open it from there and update again.",
        "err_prepare": "The update could not be prepared (the .dmg could not be attached or the app could not be copied), so nothing was installed. Download and install manually.",
        "guard_replaced": "HST Office was updated to %s while version %s was running. HST Office will close and open the new version by itself.",
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
