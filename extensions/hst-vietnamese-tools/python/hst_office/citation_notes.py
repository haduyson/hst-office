# SPDX-License-Identifier: AGPL-3.0-only
"""Note styles (Chicago notes and bibliography): each citation cluster is the text of one footnote.

Position of a cite, in document order: the first cite of a work prints the full note; a later one prints the short
note (Vietnamese works: "Nguyễn Văn An, Sđd, tr. 15." when ``shortNoteVi`` is "sdd"); a cite of the same single
work as the previous footnote prints "Ibid., 16." / "Tlđd, tr. 16." when the style allows ibid. The document layer
keeps every HST citation of a note style inside its own footnote (see the phase-03 plan, note-style contract).
"""
from . import citation_cite as cite_mod
from . import citation_render as render
from . import citation_runs as runs_mod
from .citation_terms import term


def _locator(style, cite):
    return cite_mod.locator_text(style.options, cite.get("locator"), cite.get("label", "page"), style.terms)


def _one(style, item, cite, position):
    ctx = render.Context(style, item, position=position, locator=_locator(style, cite))
    if position == "ibid":
        word = term("ibid", style.options["language"], overrides=style.terms)
        loc = ctx.locator
        return [(word + (", " + loc if loc else ""), "")]
    elements = style.short_note() if position == "subsequent" else style.layout(item.get("type"), note=True)
    found = render.render(elements, ctx)
    return [(cite.get("prefix", ""), "")] + found + [(cite.get("suffix", ""), "")]


def positions(clusters):
    """[[position of each cite]] for clusters in document order: first, subsequent or ibid."""
    seen, previous, result = set(), None, []
    for cluster in clusters:
        cites = cluster.get("items", [])
        own = []
        for cite in cites:
            item_id = cite.get("id")
            if len(cites) == 1 and previous == item_id:
                own.append("ibid")
            elif item_id in seen:
                own.append("subsequent")
            else:
                own.append("first")
            seen.add(item_id)
        previous = cites[0].get("id") if len(cites) == 1 else None
        result.append(own)
    return result


def note_clusters(clusters, items, style):
    """Runs of each footnote (cites joined by "; ", ending with a period)."""
    result = []
    for cluster, own in zip(clusters, positions(clusters)):
        out = runs_mod.Out()
        for index, (cite, position) in enumerate(zip(cluster.get("items", []), own)):
            item = items.get(cite.get("id"))
            if position == "ibid" and not style.options["ibid"]:
                position = "subsequent"
            if index:
                out.add("; ")
            out.extend([("?", "")] if item is None else _one(style, item, cite, position))
        out.add(".")
        merged = runs_mod.merge(out.runs)
        result.append(runs_mod.quote_punctuation(merged) if style.options["punctInQuote"] else merged)
    return result
