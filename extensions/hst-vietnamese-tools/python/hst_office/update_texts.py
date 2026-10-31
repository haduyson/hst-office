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
    },
    "en": {
        "title": "Check for Updates",
        "new": "HST Office %s is available — a new version.",
        "current": "You are using %s.",
        "download": "Download", "notes": "What's new", "skip": "Skip this version", "close": "Close",
        "uptodate": "You are using the latest version (%s).",
        "failed": "Could not check for updates. Check your network connection and try again later.",
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
