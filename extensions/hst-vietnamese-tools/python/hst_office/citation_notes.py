# SPDX-License-Identifier: AGPL-3.0-only
"""Note styles (Chicago notes and bibliography): each citation cluster is the text of one footnote.

Position of a cite, in document order: the first cite of a work prints the full note; a later one prints the short
note ("Krugman, *Return*, 12."; the Vietnamese preset: "Nguyễn Văn An, sđd, tr. 15.", "…, tlđd" for works that are
not books, with the title when the author has several cited works); a cite of the same single work as the previous
footnote prints "Ibid., 16." when the style allows ibid. A short note starts with a capital letter. The document layer
keeps every HST citation of a note style inside its own footnote (see the phase-03 plan, note-style contract).
"""
from . import citation_cite as cite_mod
from . import citation_language as language
from . import citation_render as render
from . import citation_render_fields as fields
from . import citation_render_names as render_names
from . import citation_runs as runs_mod
from .citation_terms import term


def _locator(style, cite):
    return cite_mod.locator_text(style.options, cite.get("locator"), cite.get("label", "page"), style.terms)


def _who(item, style):
    people = item.get("author") or item.get("editor")
    return render_names.cite_names(people, style.options, language.group_of(item)) if people else None


def shared_authors(clusters, items, style):
    """Short author names that more than one cited work has (their short notes add the title)."""
    works = {}
    for cluster in clusters:
        for cite in cluster.get("items", []):
            item = items.get(cite.get("id"))
            who = _who(item, style) if item else None
            if who:
                works.setdefault(who, set()).add(item["id"])
    return {who for who, ids in works.items() if len(ids) > 1}


def _one(style, item, cite, position, shared=frozenset()):
    flags = {"shared-author"} if _who(item, style) in shared else set()
    if cite.get("suppressAuthor"):
        flags.add("suppress-author")
    ctx = render.Context(style, item, position=position, locator=_locator(style, cite), flags=flags)
    if position == "ibid":
        word = term("ibid", style.options["language"], overrides=style.terms)
        loc = ctx.locator
        return [(word + (", " + loc if loc else ""), "")]
    elements = style.short_note() if position == "subsequent" else style.layout(item.get("type"), note=True)
    found = render.render(elements, ctx)
    if position == "subsequent" and found and not cite.get("prefix"):
        found = [(fields.capfirst(found[0][0]), found[0][1])] + found[1:]
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
    result, shared = [], shared_authors(clusters, items, style)
    for cluster, own in zip(clusters, positions(clusters)):
        out = runs_mod.Out()
        for index, (cite, position) in enumerate(zip(cluster.get("items", []), own)):
            item = items.get(cite.get("id"))
            if position == "ibid" and not style.options["ibid"]:
                position = "subsequent"
            if index:
                out.add("; ")
            out.extend([("?", "")] if item is None else _one(style, item, cite, position, shared))
        out.add(".")
        merged = runs_mod.merge(out.runs)
        result.append(runs_mod.quote_punctuation(merged) if style.options["punctInQuote"] else merged)
    return result
