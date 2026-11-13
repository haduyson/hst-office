# SPDX-License-Identifier: AGPL-3.0-only
"""Notice after the office repaired its settings file at start.

A power cut right after the office wrote registrymodifications.xcu can leave it empty or unreadable. The office then
keeps the damaged file as registrymodifications.xcu.hong-<time>, takes the copy it saved in user/pack at the last
normal exit (or, without one, starts from the defaults) and writes registrymodifications.xcu.hst-repaired with
"restored" or "reset" (configmgr, hst-profile-durability.patch). This start-up step tells the user once and removes
the marker.
"""
import os

MARKER = "registrymodifications.xcu.hst-repaired"
TITLE = "Cài đặt HST Office"
TEXT = {
    "restored": "Cài đặt của HST Office bị hỏng do máy tắt đột ngột. Đã lấy lại cài đặt từ bản sao lưu gần nhất. "
                "Các thay đổi cài đặt sau lần thoát bình thường cuối cùng có thể cần làm lại.",
    "reset": "Cài đặt của HST Office bị hỏng do máy tắt đột ngột và chưa có bản sao lưu nên đã trở về mặc định. "
             "Tài liệu của bạn không bị ảnh hưởng.",
}


def take_marker(user_dir):
    """The repair kind ("restored" / "reset") of a pending marker, which is removed; None when there is none."""
    path = os.path.join(user_dir, MARKER)
    try:
        with open(path, encoding="utf-8") as handle:
            kind = handle.read(64).strip()
    except OSError:
        return None
    try:
        os.remove(path)
    except OSError:
        pass
    return kind if kind in TEXT else "reset"


def show_once(ctx, parent):
    """Start-up step (startup_prompts): True when it showed the notice."""
    from .dialogs import message_box
    from .unsaved_dialog import user_dir
    kind = take_marker(user_dir(ctx))
    if kind is None:
        return False
    message_box(ctx, parent, TITLE, TEXT[kind])
    return True
