# SPDX-License-Identifier: AGPL-3.0-only
"""Shared checks of the citation commands (UNO): strings in the UI language, when a command cannot run here, the
document's settings (a new citation document gets the default style of the UI language)."""
from . import citation_refresh as refresh
from . import citation_settings as settings_mod
from . import citation_texts
from . import citation_ui as ui


def texts_of(host):
    return citation_texts.load(host.ctx)


def blocked(host, texts, cursor=True):
    """The reason this command cannot run here, said to the user; True when blocked."""
    reason = None
    if not host.is_writer():
        reason = "notWriter"
    elif not refresh.is_writable(host.doc):
        reason = "readOnly"
    elif cursor:
        view = host.controller.getViewCursor()
        selection = host.doc.getCurrentSelection()
        if selection is not None and selection.supportsService("com.sun.star.text.TextRanges") \
                and selection.getCount() > 1:
            reason = "selection"
        elif not view.isCollapsed() and "\n" in view.getString():
            reason = "selection"
    if reason:
        ui.inform(host.ctx, host.peer, texts, texts["blockers"][reason])
    return reason is not None


def settings_of(host, texts, write=True):
    """The document's settings; a document without them gets the default for the UI language."""
    found = settings_mod.read(host.doc)
    if found is None:
        found = settings_mod.default_settings(texts["language"])
        if write:
            settings_mod.write(host.doc, found)
    return found


def report(host, texts, plan, done_text):
    if plan is not None:
        ui.inform(host.ctx, host.peer, texts, ui.with_warnings(texts, done_text, plan.get("warnings")))
