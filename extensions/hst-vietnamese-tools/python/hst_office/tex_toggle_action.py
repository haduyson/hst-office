# SPDX-License-Identifier: LicenseRef-HST-Proprietary
# Copyright (C) 2026 HASON TECH
"""Chuyển TeX ⇄ công thức (org.hst.office.vi:TexToggle; Chèn ▸ Công thức, Alt+\\): the LaTeX of the selection or of
the whole document becomes formulas, a selected formula becomes LaTeX again (tex_toggle_writer). The command then
says on the status bar, never in a dialog (tex_toggle_notice), how many spans were converted and how many stayed
text, so typing and Ctrl+Z work at once."""
from . import tex_toggle_notice, tex_toggle_texts
from .dialogs import message_box
from .tex_toggle_texts import TEXTS


def run(host):
    if not host.is_writer():
        return message_box(host.ctx, host.peer, TEXTS["title"], TEXTS["writerOnly"])
    from . import tex_toggle_writer
    result = tex_toggle_writer.toggle(host.ctx, host.doc, host.controller, TEXTS["undo"])
    tex_toggle_notice.show(host.ctx, host.frame, tex_toggle_texts.report(result) or TEXTS["none"])
