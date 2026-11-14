# SPDX-License-Identifier: AGPL-3.0-only
"""E-mail fallback of the error report: a mailto: link to lienhe@hasontech.vn with the report as readable text.

Offered when the server is busy (429), fails (5xx) or cannot be reached. The user's mail program opens with the
text prefilled; the user reviews it and sends it, or not. Mail programs and Windows' ShellExecute cut long mailto
links, so the encoded link is kept under MAX_URL by shortening the text (the end goes first, diagnostics before
the description) and saying so.
"""
import urllib.parse

from .error_report_apps import app_name

ADDRESS = "lienhe@hasontech.vn"
MAX_URL = 1900
CUT_NOTE = "\n… (đã rút gọn)"
DIAGNOSTIC_TITLES = (("systemInfo", "Thông tin hệ thống"), ("crash", "Lần đóng đột ngột"), ("log", "Nhật ký lỗi HST"))


def subject(payload):
    kind = "Báo sự cố" if payload["kind"] == "crash" else "Báo lỗi"
    return "%s HST Office %s" % (kind, payload["product"]["version"])


def summary_lines(payload):
    """Version, OS and app lines, as the dialog's read-only summary shows them: the HST Office version only."""
    product, system = payload["product"], payload["os"]
    return ["Phiên bản: HST Office %s (bản dựng %s)" % (product["version"], product["build"]),
            "Hệ điều hành: %s (%s)" % (system["version"], system["arch"]),
            "Ứng dụng: %s" % (payload.get("appName") or app_name(payload["app"]))]


def plain_text(payload):
    """The report as text: description, contact, summary, ids (the install ID when sent), then the diagnostics."""
    lines = [payload.get("description") or "(không có mô tả)", ""]
    if payload.get("contactEmail"):
        lines.append("Thư điện tử liên hệ: " + payload["contactEmail"])
    lines += summary_lines(payload)
    lines += ["Mã báo cáo trong máy: " + payload["reportId"], "Thời điểm (UTC): " + payload["createdAt"]]
    if payload.get("installId"):
        lines.append("Mã máy ẩn danh: " + payload["installId"])
    for name, title in DIAGNOSTIC_TITLES:
        value = payload.get("diagnostics", {}).get(name)
        if value:
            lines += ["", "[%s]" % title, value]
    return "\n".join(lines)


def _url(subject_text, body):
    query = urllib.parse.urlencode({"subject": subject_text, "body": body}, quote_via=urllib.parse.quote)
    return "mailto:%s?%s" % (ADDRESS, query)


def mailto_url(payload, limit=MAX_URL):
    """mailto: link whose encoded length is at most `limit`; the text is shortened from the end when needed."""
    text, title = plain_text(payload), subject(payload)
    if len(_url(title, text)) <= limit:
        return _url(title, text)
    low, high = 0, len(text)
    while low < high:  # longest prefix that still fits together with the note
        middle = (low + high + 1) // 2
        if len(_url(title, text[:middle].rstrip() + CUT_NOTE)) <= limit:
            low = middle
        else:
            high = middle - 1
    return _url(title, text[:low].rstrip() + CUT_NOTE)
