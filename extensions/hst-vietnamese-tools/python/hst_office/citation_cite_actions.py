# SPDX-License-Identifier: AGPL-3.0-only
"""Chèn trích dẫn (also edits the citation under the cursor) and Chèn lại trích dẫn (by typed number or from the
list of sources the document cites). Each insertion and the refresh after it are one Undo step."""
from . import citation_codes as codes
from . import citation_document as document
from . import citation_refresh as refresh
from . import citation_settings as settings_mod
from . import citation_ui as ui
from .citation_action_common import blocked, settings_of, texts_of


def insert_cluster(host, texts, cluster, items, undo_key, typed_length=0):
    """Insert a new citation at the cursor (replacing ``typed_length`` typed characters) and refresh."""
    settings = settings_of(host, texts)
    _fields, plan = refresh.compute(host.ctx, host.doc, settings, texts["bibliography"]["empty"])
    code = codes.encode_citation(cluster, items)
    undo = host.doc.getUndoManager()
    undo.enterUndoContext(texts["undo"][undo_key])
    try:
        if typed_length:
            document.delete_before_cursor(host.doc, typed_length)
        document.insert_field(host.ctx, host.doc, code, "[…]", "Footnote" if plan["note"] else None)
        result = refresh.refresh(host.ctx, host.doc, texts["undo"]["update"], texts["bibliography"]["empty"],
                                 settings, force=True)
    finally:
        undo.leaveUndoContext()
    if result and result.get("warnings"):
        ui.inform(host.ctx, host.peer, texts, ui.with_warnings(texts, texts["undo"][undo_key], result["warnings"]))


def insert(host):
    """Chèn trích dẫn; with the cursor in a citation: edit that citation."""
    texts = texts_of(host)
    if blocked(host, texts):
        return
    settings = settings_of(host, texts, write=False)
    fields, plan = refresh.compute(host.ctx, host.doc, settings, texts["bibliography"]["empty"])
    current = document.field_at_cursor(host.doc, [f for f in fields if f["kind"] == "citation"])
    existing = None
    if current is not None:
        try:
            existing = codes.decode_citation(current["code"])
        except codes.CodeError:
            existing = None
    from .citation_insert_dialog import run
    chosen = run(host.ctx, host.peer, texts, settings, plan, existing, refresh.document_language(host.doc))
    if chosen is None:
        return
    cluster, items = chosen
    if current is None or existing is None:
        return insert_cluster(host, texts, cluster, items, "insert")
    cluster["citationID"] = existing[0]["citationID"]
    new_code = codes.encode_citation(cluster, items)
    settings_mod.write(host.doc, settings)
    refresh.refresh(host.ctx, host.doc, texts["undo"]["edit"], texts["bibliography"]["empty"], settings,
                    new_codes={current["index"]: new_code})


def reinsert(host):
    """Chèn lại trích dẫn: "[3, tr. 15" typed before the cursor becomes a citation; otherwise pick from a list."""
    from . import citation_numbering as numbering
    texts = texts_of(host)
    if blocked(host, texts):
        return
    settings = settings_of(host, texts, write=False)
    _fields, plan = refresh.compute(host.ctx, host.doc, settings, texts["bibliography"]["empty"])
    if not plan["order"]:
        return ui.inform(host.ctx, host.peer, texts, texts["blockers"]["noCitations"])
    typed = numbering.parse_typed(document.text_before_cursor(host.doc, document.scan(host.doc)))
    if typed:
        ids, missing = numbering.ids_for_numbers(typed["numbers"], plan["order"])
        if missing:
            return ui.inform(host.ctx, host.peer, texts, texts["blockers"]["numbers"] % ", ".join(map(str, missing)))
        cluster = numbering.cluster_for(ids, typed["locator"], typed["label"])
        return insert_cluster(host, texts, cluster, plan["items"], "reinsert", typed["length"])
    from .citation_reinsert_dialog import run
    chosen = run(host.ctx, host.peer, texts, plan["entries"])
    if chosen is not None:
        ids, locator = chosen
        insert_cluster(host, texts, numbering.cluster_for(ids, locator), plan["items"], "reinsert")
