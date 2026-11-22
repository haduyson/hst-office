# SPDX-License-Identifier: LicenseRef-HST-Proprietary
# Copyright (C) 2026 HASON TECH
"""Strings of Chuyển TeX ⇄ công thức (Vietnamese in every UI language, as the other HST commands)."""

TEXTS = {
    "title": "Chuyển TeX ⇄ công thức",
    "undo": "Chuyển TeX ⇄ công thức",
    "writerOnly": "Lệnh này dùng trong HST Writer.",
    "none": "Không tìm thấy công thức LaTeX ($…$, $$…$$, \\(…\\), \\[…\\]) trong vùng chọn hay tài liệu.",
    "converted": "Đã chuyển %d công thức LaTeX thành công thức (Hoàn tác: Ctrl+Z).",
    "failed": "%d công thức LaTeX không chuyển được nên vẫn giữ nguyên, được tô vàng để bạn kiểm tra.",
    "reverted": "Đã chuyển %d công thức về mã LaTeX.",
    "kept": "%d công thức không chuyển được về LaTeX nên vẫn giữ nguyên.",
}


def report(result):
    """The message after a run; None when there was nothing to do."""
    lines = []
    if result.converted:
        lines.append(TEXTS["converted"] % result.converted)
    if result.failed:
        lines.append(TEXTS["failed"] % result.failed)
    if result.reverted:
        lines.append(TEXTS["reverted"] % result.reverted)
    if result.kept:
        lines.append(TEXTS["kept"] % result.kept)
    return "\n".join(lines) or None
