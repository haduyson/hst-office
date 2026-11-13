# SPDX-License-Identifier: AGPL-3.0-only
"""What a citation refresh writes into the document, computed without touching it. Pure Python (no uno).

Input: the document's HST fields as citation_document.scan lists them, each
    {"index": raw position, "rank": reading position, "kind": "citation"|"bibliography", "code", "result"}
and the document settings. Steps: decode codes; give copies of a citation (copy and paste) a new citationID;
keep, for every source cited twice with different data, the newest copy (custom.hst.modified) everywhere; format
all citations in reading order with the engine; build the bibliography. The output lists updates in raw field
order, which is what .uno:TextFormFields walks (every field gets a code and a result; see phase 04 of the plan).
``engine`` provides process(style, items, clusters), load_style(id, options, preset) and modified(item).
"""
import html

from . import citation_codes as codes


def _plain_html(text):
    return html.escape(text or "", quote=False)


def _decode_all(fields, warnings):
    """[(field, cluster, items)] of the citations in reading order; undecodable ones get cluster None."""
    out = []
    for field in sorted((f for f in fields if f["kind"] == "citation"), key=lambda f: f["rank"]):
        try:
            cluster, items = codes.decode_citation(field["code"])
        except codes.CodeError as exc:
            warnings.append(str(exc))
            cluster, items = None, {}
        out.append((field, cluster, items))
    return out


def _newest_items(decoded, modified):
    """{id: itemData}: the newest copy of each source (the first in reading order on a tie)."""
    best = {}
    for _field, cluster, items in decoded:
        for item_id, data in items.items():
            if item_id not in best or modified(data) > modified(best[item_id]):
                best[item_id] = data
    return best


def bibliography_paragraphs(bibliography, empty_text):
    """[(role, html, plain)] of the bibliography: title, group headings, entries ("[1] text")."""
    paragraphs = []
    if bibliography.get("title"):
        paragraphs.append(("title", _plain_html(bibliography["title"]), bibliography["title"]))
    for group in bibliography.get("groups", []):
        if group.get("heading"):
            paragraphs.append(("heading", _plain_html(group["heading"]), group["heading"]))
        for entry in group.get("entries", []):
            label = entry.get("label") or ""
            lead = (label + " ") if label else ""
            paragraphs.append(("entry", _plain_html(lead) + entry["html"], lead + entry["text"]))
    if not any(role == "entry" for role, _h, _p in paragraphs):
        paragraphs.append(("entry", _plain_html(empty_text), empty_text))
    return paragraphs


def plan(fields, settings, engine, empty_text="—", document_language=None):
    """See the module docstring. Returns {"citations": [(code, html)] in raw order, "citations_changed": n,
    "bibliography": [(code, html)] in raw order, "bib_roles": [roles], "bib_changed": bool, "order": [ids in
    bibliography order], "entries": [{"id", "number", "label", "text"}], "note": bool, "count": n, "warnings"}.
    ``document_language`` ("vi", "en", …) picks the terms of international styles ("tr." or "p.")."""
    warnings = []
    style = engine.load_style(settings["style"], settings.get("opts") or {}, settings.get("preset"))
    decoded = _decode_all(fields, warnings)
    seen, new_codes = set(), {}
    newest = _newest_items(decoded, engine.modified)
    clusters = []
    for field, cluster, items in decoded:
        if cluster is None:
            continue
        rewrite = False
        if not cluster["citationID"] or cluster["citationID"] in seen:  # a pasted copy: it becomes its own citation
            cluster["citationID"] = codes.new_citation_id()
            rewrite = True
        seen.add(cluster["citationID"])
        for item_id in list(items):
            if newest.get(item_id) is not None and newest[item_id] != items[item_id]:
                items[item_id] = newest[item_id]
                rewrite = True
        if rewrite:
            new_codes[field["index"]] = codes.encode_citation(cluster, items)
        clusters.append((field, cluster))
    result = engine.process(style, newest, [c for _f, c in clusters], document_language=document_language)
    warnings += result.get("warnings", [])
    formatted = {f["index"]: c for (f, _cl), c in zip(clusters, result["citations"])}
    updates, changed = [], 0
    for field in sorted((f for f in fields if f["kind"] == "citation"), key=lambda f: f["index"]):
        code = new_codes.get(field["index"], field["code"])
        found = formatted.get(field["index"])
        if found is None:  # unreadable code: kept as it is, its text too
            updates.append((code, _plain_html(field["result"])))
            continue
        if code != field["code"] or found["text"] != field["result"]:
            changed += 1
        updates.append((code, found["html"]))
    paragraphs = bibliography_paragraphs(result["bibliography"], empty_text)
    # The last entry is not closed by </p>: pasting a closing </p> leaves an empty paragraph inside the field.
    bib_html = "".join("<p>%s</p>" % h for _r, h, _p in paragraphs[:-1]) + "<p>%s" % paragraphs[-1][1]
    bib_plain = "\n".join(p for _r, _h, p in paragraphs)
    bib_fields = sorted((f for f in fields if f["kind"] == "bibliography"), key=lambda f: f["index"])
    entries, order = [], []
    for group in result["bibliography"].get("groups", []):
        for entry in group.get("entries", []):
            order.append(entry["id"])
            entries.append({"id": entry["id"], "number": len(order), "label": entry.get("label") or "",
                            "text": entry["text"]})
    return {"citations": updates, "citations_changed": changed,
            "bibliography": [(f["code"], bib_html) for f in bib_fields], "bib_roles": [r for r, _h, _p in paragraphs],
            "bib_changed": any(f["result"].rstrip("\n") != bib_plain for f in bib_fields),
            "order": order, "entries": entries, "items": newest, "note": style.cls == "note",
            "hanging": bool(result["bibliography"].get("hangingIndent")), "count": len(clusters),
            "warnings": warnings}
