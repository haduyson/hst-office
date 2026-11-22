# SPDX-License-Identifier: LicenseRef-HST-Proprietary
# Copyright (C) 2026 HASON TECH
"""Office side of the macOS app launchers in /Applications (logic: hst_office/mac_app_launchers.py).

sync_at_startup() copies or refreshes them at every start of an installed HST Office (startup_prompts, before the
questions); notice_once() is the one-time start-up notice that says where they went and how to remove them (Vietnamese
or English with the UI). Neither runs off macOS, in a copy started from the .dmg, ~/Downloads or a translocated path
(mac_app_location.MOVABLE), nor when other software started the office (headless, --accept, conversions:
automation_start). remove_from_options() and add_from_options() are the "Gỡ biểu tượng ứng dụng" and "Thêm lại biểu
tượng ứng dụng" buttons of Tùy chọn ▸ HST Office ▸ Mở tài liệu (app_shortcuts_ui).
"""
import platform

from . import diag_log
from . import mac_app_launchers as launchers

NAMES_VI = "HST Writer, HST Sheets, HST Slides, HST Draw và HST PDF"
NAMES_EN = "HST Writer, HST Sheets, HST Slides, HST Draw and HST PDF"
REMOVE_PATH = "Tùy chọn ▸ HST Office ▸ Mở tài liệu ▸ Gỡ biểu tượng ứng dụng"
TEXTS = {
    "vi": {
        "title": "Biểu tượng ứng dụng",
        "notice": "Đã thêm %s vào %%s. Bạn có thể mở từng ứng dụng từ Launchpad, Spotlight hoặc Finder.\n"
                  "Muốn gỡ: %s." % (NAMES_VI, REMOVE_PATH),
        "system": "thư mục Ứng dụng (/Applications)",
        "user": "thư mục Ứng dụng của bạn (~/Applications)",
        "close": "Đóng",
    },
    "en": {
        "title": "App icons",
        "notice": "%s were added to %%s. You can open each app from Launchpad, Spotlight or Finder.\n"
                  "To remove them: Options ▸ HST Office ▸ Mở tài liệu ▸ Gỡ biểu tượng ứng dụng." % NAMES_EN,
        "system": "the Applications folder (/Applications)",
        "user": "your Applications folder (~/Applications)",
        "close": "Close",
    },
}
OPTIONS = {
    "remove_ask": "Gỡ %s khỏi Launchpad và thư mục Ứng dụng?\nHST Office vẫn được giữ nguyên." % NAMES_VI,
    "remove_button": "Gỡ",
    "removed": "Đã gỡ biểu tượng %s. Bạn có thể thêm lại bất cứ lúc nào." % NAMES_VI,
    "none": "Không có biểu tượng ứng dụng nào để gỡ. HST Office sẽ không tự thêm lại.",
    "added": "Đã thêm %s vào %%s." % NAMES_VI,
    "failed": "Không thực hiện được: %s",
}


def folder_label(folder, language="vi"):
    """How the notice names the folder (pure)."""
    return TEXTS[language]["system" if folder == launchers.SYSTEM_FOLDER else "user"]


def notice_text(folder, language="vi"):
    return TEXTS[language]["notice"] % folder_label(folder, language)


def _automated():
    try:
        from .automation_start import started_by_automation
    except ImportError:  # a build without the automation check: a person's start
        return False
    return started_by_automation()


def _installed_bundle(ctx):
    """The running bundle when it is an installed copy, else None (.dmg, ~/Downloads, translocated)."""
    from .mac_app_location import MOVABLE, _running_bundle, locate
    bundle = _running_bundle(ctx)
    return None if locate(bundle)["kind"] in MOVABLE else bundle


def sync_at_startup(ctx):
    """Copy or refresh the launchers (see mac_app_launchers.sync). Never raises; False when nothing was done."""
    if platform.system() != "Darwin":
        return False
    try:
        bundle = None if _automated() else _installed_bundle(ctx)
        return bool(bundle and launchers.sync(bundle))
    except Exception:  # noqa: BLE001 - never break start-up; the next start tries again
        diag_log.exception("mac_app_launchers")
        return False


def _show_notice(ctx, folder):
    from .mac_app_location import _peer
    from .update_install import _ask
    from .update_texts import ui_language
    language = ui_language(ctx)
    text = TEXTS[language]
    _ask(ctx, _peer(ctx), text["title"], notice_text(folder, language), [(text["close"], "close")], text_height=48)


def notice_once(ctx):
    """Start-up question step: True when the one-time notice was shown. Never raises."""
    if platform.system() != "Darwin":
        return False
    try:
        state = launchers.load_state()
        if state.get("notice") != "pending" or state.get("removed") or _automated():
            return False
        launchers.save_state(dict(state, notice="shown"))  # shown once, even when the office ends during it
        _show_notice(ctx, state.get("folder"))
        return True
    except Exception:  # noqa: BLE001 - never break start-up
        diag_log.exception("mac_app_launchers")
        return False


def remove_from_options(ctx, message):
    """"Gỡ biểu tượng ứng dụng": asks, deletes the copies and stops the copying at later starts.
    `message(text, ask=False, button=None)` shows a message and returns True for the first button."""
    bundle = _installed_bundle(ctx)
    from .app_shortcuts_ui import MOVE_FIRST
    if bundle is None:
        return message(MOVE_FIRST)
    host_id, version = launchers.host_identity(bundle)
    if not any(launchers.present(folder, host_id) for folder in launchers.folders()):
        launchers.set_removed(True, version)
        return message(OPTIONS["none"])
    if not message(OPTIONS["remove_ask"], ask=True, button=OPTIONS["remove_button"]):
        return False
    launchers.remove(host_id)
    launchers.set_removed(True, version)
    return message(OPTIONS["removed"])


def add_from_options(ctx, message):
    """"Thêm lại biểu tượng ứng dụng": copies all five again and keeps them fresh at later starts."""
    bundle = _installed_bundle(ctx)
    from .app_shortcuts_ui import MOVE_FIRST
    if bundle is None:
        return message(MOVE_FIRST)
    _host_id, version = launchers.host_identity(bundle)
    folder, _copied = launchers.install(bundle)
    launchers.set_removed(False, version, folder)
    return message(OPTIONS["added"] % folder_label(folder))
