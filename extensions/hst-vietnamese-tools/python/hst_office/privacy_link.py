# SPDX-License-Identifier: AGPL-3.0-only
"""The "Chính sách quyền riêng tư" / "Privacy policy" link: Tùy chọn ▸ HST Office ▸ Cập nhật, the error report
dialog and the citation source form (the About dialog has its own link, patches/libreoffice/hst-about-privacy-link.patch).

The page is https://office.hasontech.vn/quyen-rieng-tu/ with the shared UTM parameters of data/hst/solutions.json
and utm_medium naming the place clicked. Nothing is fetched by the office: a click hands the URL to the system browser
through update_ui.open_url (https links to hasontech.vn and its subdomains only).
"""
from . import diag_log
from .data_files import load_data
from .welcome_content import build_utm_url

PAGE = "https://office.hasontech.vn/quyen-rieng-tu/"
LABELS = {"vi": "Chính sách quyền riêng tư", "en": "Privacy policy"}
OPENED = []  # URLs handed to the browser (runtime check hook, as welcome_dialog.OPENED)


def url(medium):
    """The page with utm_source/utm_medium/utm_campaign; ValueError for a medium not listed in solutions.json."""
    return build_utm_url(PAGE, medium, load_data("solutions.json")["utm"])


def label(language):
    """Link text in the UI language: Vietnamese for a Vietnamese UI, English for any other."""
    return LABELS["vi" if str(language or "").lower().startswith("vi") else "en"]


def ui_label(ctx):
    from .update_texts import ui_language
    return label(ui_language(ctx))


def open_policy(ctx, medium):
    """Open the policy page in the system browser; False (and a log line) when no browser could be started."""
    target = url(medium)
    OPENED.append(target)
    try:
        from .update_ui import open_url
        open_url(ctx, target)
        return True
    except Exception:  # noqa: BLE001 - a missing browser must not break the dialog that holds the link
        diag_log.exception("privacy_link")
        return False
