# SPDX-License-Identifier: AGPL-3.0-only
"""Chuyển TeX ⇄ công thức (org.hst.office.vi:TexToggle; Chèn ▸ Công thức, Alt+\\): the LaTeX of the selection or of
the whole document becomes formulas, a selected formula becomes LaTeX again (tex_toggle_writer). The command then
says how many spans were converted and how many stayed text."""
from . import tex_toggle_texts
from .dialogs import message_box
from .tex_toggle_texts import TEXTS


def run(host):
    if not host.is_writer():
        return message_box(host.ctx, host.peer, TEXTS["title"], TEXTS["writerOnly"])
    from . import tex_toggle_writer
    result = tex_toggle_writer.toggle(host.ctx, host.doc, host.controller, TEXTS["undo"])
    message_box(host.ctx, host.peer, TEXTS["title"], tex_toggle_texts.report(result) or TEXTS["none"])
