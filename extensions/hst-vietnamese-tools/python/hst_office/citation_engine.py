# SPDX-License-Identifier: AGPL-3.0-only
"""Public entry point of the citation formatter (the document layer calls only this module and citation_runs).

    style = citation_style.load_style("vn-so", options=doc_opts)      # or a preset / the user's own style
    result = citation_engine.process(style, items_by_id, clusters, uncited_ids=(), document_language="vi-VN")

``clusters`` are the document's citation fields in document order (footnotes and frames by their anchor):
{"citationID": str, "items": [{"id", "locator", "label", "prefix", "suffix", "suppressAuthor", "authorOnly"}],
"mode": "normal" | "narrative"}. The result is JSON-safe:
{"citations": [{"citationID", "runs", "text", "html", "note"}],
 "bibliography": {"title", "numbered", "hangingIndent",
                  "groups": [{"language", "heading", "entries": [{"id", "number", "label", "runs", "text", "html"}]}]},
 "numbers": {id: n}, "missing": [ids], "warnings": [str]}
``runs`` are citation_runs.to_public dicts. Pure Python (no uno).
"""
import copy

from . import citation_bib_order as bib_order
from . import citation_cite as cite_mod
from . import citation_language as language
from . import citation_notes as notes
from . import citation_render as render
from . import citation_runs as runs_mod
from .citation_terms import LOCATOR_LABELS, localize

MAX_CLUSTERS = 20_000
MAX_TEXT = 200


def clean_cite(raw):
    """A cite as read from a document field; ValueError when it is not usable."""
    if not isinstance(raw, dict) or not isinstance(raw.get("id"), str) or not raw["id"]:
        raise ValueError("trích dẫn thiếu id")
    cite = {"id": raw["id"]}
    for key in ("locator", "prefix", "suffix"):
        if isinstance(raw.get(key), str) and raw[key]:
            cite[key] = raw[key][:MAX_TEXT]
    cite["label"] = raw.get("label") if raw.get("label") in LOCATOR_LABELS else "page"
    for key in ("suppressAuthor", "authorOnly"):
        if raw.get(key) is True:
            cite[key] = True
    return cite


def clean_cluster(raw):
    if not isinstance(raw, dict) or not isinstance(raw.get("items"), list) or not raw["items"]:
        raise ValueError("cụm trích dẫn phải có ít nhất một mục")
    mode = raw.get("mode") if raw.get("mode") in ("normal", "narrative") else "normal"
    return {"citationID": str(raw.get("citationID", "")), "items": [clean_cite(c) for c in raw["items"]],
            "mode": mode}


def _public(runs):
    runs = runs_mod.merge(runs)  # merging twice changes nothing, so the helpers below find little to do
    return {"runs": runs_mod.to_public(runs), "text": runs_mod.plain(runs), "html": runs_mod.to_html(runs)}


def _cluster_runs(style, clusters, items, number_of, suffixes, arranged, initials_for):
    if style.kind == "csl":
        return style.clusters(clusters, items, number_of, suffixes)
    if style.cls == "note":
        return notes.note_clusters(clusters, items, style)
    if style.cls == "numeric":
        return [cite_mod.numeric_cluster(c["items"], number_of, style) for c in clusters]
    ambiguous = set()
    if not style.options["citeYear"]:  # MLA: a short title tells apart two works of one author
        counts = {}
        for _, group in arranged:
            for item in group:
                if item.get("author"):
                    who = cite_mod.render_names.cite_names(item["author"], style.options, language.group_of(item))
                    counts[who] = counts.get(who, 0) + 1
        ambiguous = {who for who, count in counts.items() if count > 1}
    return [cite_mod.author_date_cluster(c["items"], items, suffixes, style, c["mode"] == "narrative", ambiguous,
                                         initials_for) for c in clusters]


def entry_runs(style, item, number=None, year_suffix="", subsequent_author=False):
    """Runs of one bibliography entry (also used for the preview in dialogs)."""
    if style.kind == "csl":
        return style.entry(item, number, year_suffix)
    ctx = render.Context(style, item, year_suffix=year_suffix, number=number, subsequent_author=subsequent_author)
    return render.render(style.layout(item.get("type")), ctx)


def with_document_language(style, document_language):
    """A copy of the style whose citation words follow the Writer document's language ("vi" -> Vietnamese,
    anything else -> English); the style itself is left unchanged."""
    if not document_language:
        return style
    clone = copy.copy(style)
    code = "vi" if str(document_language).lower().startswith("vi") else "en"
    clone.options = dict(style.options, language=code)
    return clone


def process(style, items, clusters, uncited_ids=(), document_language=None):
    """Format every citation and the bibliography (see the module docstring). ``document_language`` is the
    language of the Writer document (e.g. "vi-VN", "en-US"); None keeps the style's ``language`` option."""
    style = with_document_language(style, document_language)
    if isinstance(items, list):
        items = {item["id"]: item for item in items}
    if len(clusters) > MAX_CLUSTERS:
        raise ValueError("quá nhiều trích dẫn trong một tài liệu")
    warnings = list(getattr(style, "warnings", []))
    clean = []
    for raw in clusters:
        try:
            clean.append(clean_cluster(raw))
        except ValueError as exc:
            warnings.append(str(exc))
            clean.append({"citationID": str(raw.get("citationID", "")) if isinstance(raw, dict) else "",
                          "items": [], "mode": "normal"})
    first_index, missing = {}, []
    for cluster in clean:
        for cite in cluster["items"]:
            if cite["id"] not in items:
                if cite["id"] not in missing:
                    missing.append(cite["id"])
            first_index.setdefault(cite["id"], len(first_index))
    listed = [items[i] for i in first_index if i in items]
    listed += [items[i] for i in uncited_ids if i in items and i not in first_index]
    arranged = style.arrange(listed, first_index) if style.kind == "csl" else \
        bib_order.arrange(listed, style, first_index)
    number_of = bib_order.numbers(arranged)
    initials_for = bib_order.initials_needed(arranged, style)
    suffixes = bib_order.year_suffixes(arranged, style, initials_for) if style.cls == "author-date" else {}
    repeated = bib_order.same_author_as_previous(arranged, style) if style.kind == "json" else set()
    citations = []
    for cluster, found in zip(clean, _cluster_runs(style, clean, items, number_of, suffixes, arranged, initials_for)):
        entry = {"citationID": cluster["citationID"], "note": style.cls == "note"}
        entry.update(_public(found if cluster["items"] else [("?", "")]))
        citations.append(entry)
    numbered = style.cls == "numeric"
    label_format = style.options.get("bibLabel", "") if numbered else ""
    groups = []
    for code, group in arranged:
        heading = None
        if code and style.options.get("groupHeadings"):
            heading = language.heading(code, style.options["language"])
        entries = []
        for item in group:
            number = number_of[item["id"]]
            found = entry_runs(style, item, number, suffixes.get(item["id"], ""), item["id"] in repeated)
            entry = {"id": item["id"], "number": number if numbered else None,
                     "label": (label_format % number) if label_format else ""}
            entry.update(_public(found))
            entries.append(entry)
        groups.append({"language": code, "heading": heading, "entries": entries})
    bibliography = {"title": localize(style.options.get("bibTitle", ""), style.options["language"]),
                    "numbered": numbered, "hangingIndent": bool(style.options.get("hangingIndent")),
                    "groups": groups}
    if missing:
        warnings.append("không tìm thấy dữ liệu của %d nguồn được trích" % len(missing))
    return {"citations": citations, "bibliography": bibliography, "numbers": number_of if numbered else {},
            "missing": missing, "warnings": warnings}


def preview(style, item, locator="", label="page", document_language=None):
    """{"citation": public, "entry": public} for one item, e.g. while the user fills in the insert dialog."""
    cluster = {"citationID": "preview", "items": [{"id": item["id"], "locator": locator, "label": label}]}
    result = process(style, {item["id"]: item}, [cluster], document_language=document_language)
    first = result["bibliography"]["groups"][0]["entries"][0] if result["bibliography"]["groups"] else {}
    return {"citation": result["citations"][0], "entry": first}
