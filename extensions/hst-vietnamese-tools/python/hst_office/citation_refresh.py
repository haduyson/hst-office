# SPDX-License-Identifier: AGPL-3.0-only
"""Refresh every HST citation and the bibliography of a document (UNO orchestration).

Runs after each HST citation command, from "Cập nhật trích dẫn", and before a save (citation_save_job). It never
runs in the background and never on documents without HST citation settings. Steps: read the settings, scan the
fields, compute the plan (citation_refresh_plan, pure), write only when something changed, in one Undo step.
"""
import types

from . import citation_document as document
from . import citation_refresh_plan as refresh_plan
from . import citation_settings as settings_mod


def engine():
    """The formatter functions the plan needs (imported on use: documents without citations never load them)."""
    from . import citation_engine, citation_model, citation_style
    return types.SimpleNamespace(
        process=citation_engine.process, modified=citation_model.modified,
        load_style=lambda style_id, options, preset: citation_style.load_style(style_id, options, preset,
                                                                               user_dir=_USER_DIR.get("path")))


_USER_DIR = {}


class StyleMissing(Exception):
    """The document's style is not on this computer (a user's own style): results are kept as they are."""


def document_language(doc):
    """The language of the document's default paragraph style ("vi", "en", …): international styles take their
    terms from it ("tr."/"p.", "và cộng sự"/"et al."; owner decision 13/11/2026)."""
    try:
        style = doc.getStyleFamilies().getByName("ParagraphStyles").getByName("Standard")
        return style.CharLocale.Language or "vi"
    except Exception:  # noqa: BLE001 - no styles (closing document): HST's default language
        return "vi"


def user_dir(ctx):
    """The office user profile folder (its hst-citations/ holds the library and the user's styles)."""
    if "path" not in _USER_DIR:
        import uno
        subst = ctx.ServiceManager.createInstanceWithContext("com.sun.star.util.PathSubstitution", ctx)
        _USER_DIR["path"] = uno.fileUrlToSystemPath(subst.substituteVariables("$(user)", True))
    return _USER_DIR["path"]


def is_writable(doc):
    try:
        return doc.supportsService("com.sun.star.text.TextDocument") and not doc.isReadonly()
    except Exception:  # noqa: BLE001 - a document that is closing
        return False


def compute(ctx, doc, settings=None, empty_text="—", new_codes=None):
    """(fields, plan) of the document as it is now; plan is None when the document has no citation settings.
    ``new_codes`` = {raw index: code} replaces the code of edited citations before formatting."""
    user_dir(ctx)
    settings = settings or settings_mod.read(doc)
    fields = document.scan(doc)
    for field in fields:
        if new_codes and field["index"] in new_codes:
            field["code"] = new_codes[field["index"]]
    if settings is None:
        return fields, None
    from .citation_style import StyleError
    try:
        return fields, refresh_plan.plan(fields, settings, engine(), empty_text, document_language(doc))
    except StyleError as exc:
        raise StyleMissing(str(exc)) from exc


def refresh(ctx, doc, undo_title, empty_text="—", settings=None, force=False, new_codes=None):
    """Write the citations and bibliography; returns the plan (None without settings) with "written": bool."""
    fields, plan = compute(ctx, doc, settings, empty_text, new_codes)
    force = force or bool(new_codes)
    if plan is None:
        return None
    plan["written"] = document.apply_plan(ctx, doc, plan, undo_title, force=force)
    plan["fields"] = len(fields)
    return plan
