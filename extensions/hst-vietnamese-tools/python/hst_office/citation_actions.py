# SPDX-License-Identifier: AGPL-3.0-only
"""The six citation commands (org.hst.office.vi:Citation*), called by actions.COMMANDS with an actions.Host.

Every command that writes into the document refreshes all citations and the bibliography afterwards, inside the
same Undo step. Dialogs are imported on use. Strings follow the UI language (citation_texts).
"""
from . import citation_cite_actions as cite_actions
from . import citation_codes as codes
from . import citation_command_names as names
from . import citation_document as document
from . import citation_refresh as refresh
from . import citation_settings as settings_mod
from . import citation_ui as ui
from .citation_action_common import blocked, report, settings_of, texts_of

NAMES = names.NAMES


def bibliography(host):
    """Chèn danh mục tài liệu tham khảo at the cursor (or update the one the document has)."""
    texts = texts_of(host)
    if blocked(host, texts):
        return
    settings = settings_of(host, texts)
    fields = document.scan(host.doc)
    if any(f["kind"] == "bibliography" for f in fields):
        refresh.refresh(host.ctx, host.doc, texts["undo"]["update"], texts["bibliography"]["empty"], settings)
        return ui.inform(host.ctx, host.peer, texts, texts["done"]["bibliographyUpdated"])
    undo = host.doc.getUndoManager()
    undo.enterUndoContext(texts["undo"]["bibliography"])
    try:
        view = host.controller.getViewCursor()
        if document.text_before_cursor(host.doc):  # the list starts a paragraph of its own
            view.gotoEndOfLine(False)
            view.getText().insertControlCharacter(view, 0, False)  # PARAGRAPH_BREAK
        document.insert_field(host.ctx, host.doc, codes.encode_bibliography(),
                              "<p>%s</p>" % texts["bibliography"]["empty"])
        refresh.refresh(host.ctx, host.doc, texts["undo"]["update"], texts["bibliography"]["empty"], settings,
                        force=True)
    finally:
        undo.leaveUndoContext()


def update(host):
    """Cập nhật trích dẫn: renumber, reformat, rebuild the bibliography."""
    texts = texts_of(host)
    if blocked(host, texts, cursor=False):
        return
    if settings_mod.read(host.doc) is None and not document.scan(host.doc):
        return ui.inform(host.ctx, host.peer, texts, texts["blockers"]["noCitations"])
    plan = refresh.refresh(host.ctx, host.doc, texts["undo"]["update"], texts["bibliography"]["empty"],
                           settings_of(host, texts))
    done = texts["done"]["updated"] % plan["count"] if plan["written"] else texts["done"]["current"]
    report(host, texts, plan, done)


def style(host):
    """Kiểu trích dẫn: choose the style and its options for this document, then reformat everything."""
    texts = texts_of(host)
    if blocked(host, texts, cursor=False):
        return
    from .citation_style_dialog import run
    current = settings_of(host, texts, write=False)
    fields, plan = refresh.compute(host.ctx, host.doc, current, texts["bibliography"]["empty"])
    chosen = run(host.ctx, host.peer, texts, current, plan["items"], refresh.document_language(host.doc))
    if chosen is None:
        return
    new_note = refresh.engine().load_style(chosen["style"], chosen["opts"], chosen["preset"]).cls == "note"
    undo = host.doc.getUndoManager()
    undo.enterUndoContext(texts["undo"]["style"])
    try:
        if new_note != plan["note"] and any(f["kind"] == "citation" for f in fields):
            from .citation_note_switch import switch  # note styles keep each citation in its own footnote
            switch(host.ctx, host.doc, new_note)
        settings_mod.write(host.doc, chosen)
        plan = refresh.refresh(host.ctx, host.doc, texts["undo"]["update"], texts["bibliography"]["empty"], chosen,
                               force=True)
    finally:
        undo.leaveUndoContext()
    if plan and plan.get("warnings"):
        report(host, texts, plan, texts["undo"]["style"])


def library(host):
    """Quản lý tài liệu tham khảo (also from the Start Center: no document needed for the library itself)."""
    texts = texts_of(host)
    from .citation_library_dialog import run
    plan, settings = None, settings_mod.read(host.doc) if host.is_writer() else None
    if settings is not None:
        plan = refresh.compute(host.ctx, host.doc, settings, texts["bibliography"]["empty"])[1]
    else:
        settings = settings_mod.default_settings(texts["language"])
    style = refresh.engine().load_style(settings["style"], settings["opts"], settings.get("preset"))
    language = refresh.document_language(host.doc) if host.is_writer() else texts["language"]
    run(host.ctx, host.peer, texts, plan["items"] if plan else {}, style, language)


def _guarded(command):
    """Expected failures (a style missing on this computer, a damaged code, settings too long) become a message."""
    def run(host):
        try:
            return command(host)
        except (refresh.StyleMissing, codes.CodeError, settings_mod.SettingsError) as exc:
            texts = texts_of(host)
            ui.inform(host.ctx, host.peer, texts, texts["common"]["error"] % exc)
    return run


COMMANDS = {name: _guarded(command) for name, command in (
    ("CitationInsert", cite_actions.insert), ("CitationReinsert", cite_actions.reinsert), ("CitationBibliography", bibliography),
    ("CitationUpdate", update), ("CitationStyle", style), ("CitationLibrary", library))}
