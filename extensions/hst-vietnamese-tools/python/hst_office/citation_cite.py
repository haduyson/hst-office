# SPDX-License-Identifier: AGPL-3.0-only
"""In-text citation clusters of numeric and author–date styles. Pure Python (no uno).

A cluster is what one citation field shows: ``[15, tr. 314–315]``, ``[5, 21, 49]``, ``[7–11]``, ``[19], [25]``,
superscript ``¹⁻³`` (AMA), ``(Nguyễn Văn An, 2010; Smith & Doe, 2020)``, narrative ``Nguyễn Văn An (2010)``,
MLA ``(Smith 15)``. Each cite is {"id", "locator", "label", "prefix", "suffix", "suppressAuthor", "authorOnly"}.
"""
from . import citation_bib_order as bib_order
from . import citation_language as language
from . import citation_render_fields as fields
from . import citation_render_names as render_names
from .citation_render_dates import year_text
from .citation_terms import LOCATOR_LABELS, term

_ITALIC_TITLES = frozenset(("book", "report", "thesis", "webpage", "legislation", "dataset", "software",
                            "document", "manuscript", "patent", "post-weblog"))


def locator_text(opts, locator, label="page", overrides=None, compact=False):
    """"tr. 314–315", "pp. 5–7", "p. 5", "chương 3", or the bare range when the style omits the page label."""
    locator = (locator or "").strip()
    if not locator:
        return ""
    label = label if label in LOCATOR_LABELS else "page"
    lang = opts["language"]
    value = fields.page_range(locator, "expanded", opts["pageDash"]) if label == "page" else locator
    if label == "page" and not opts["locatorLabel"]:
        return value
    word = term(label, lang, plural=fields.is_range(locator), overrides=overrides)
    return word + ("" if compact and label == "page" else " ") + value  # AMA superscript "12(p34)"


def _compress(numbers, separate, dash):
    """[3, 4, 5, 7] -> ["3–5", "7"] (runs of three or more become ranges); IEEE style ranges keep brackets."""
    pieces, index = [], 0
    while index < len(numbers):
        end = index
        while end + 1 < len(numbers) and numbers[end + 1] == numbers[end] + 1:
            end += 1
        if end - index >= 2:
            first, last = str(numbers[index]), str(numbers[end])
            pieces.append(("[%s]%s[%s]" % (first, dash, last)) if separate else first + dash + last)
            index = end + 1
        else:
            pieces.append(("[%d]" if separate else "%d") % numbers[index])
            index += 1
    return pieces


def numeric_cluster(cites, number_of, style):
    """Runs of a numeric cluster; ``number_of`` maps item id -> bibliography number (missing ids print "?")."""
    opts = style.options
    sup, separate = opts["brackets"] == "sup", opts["multiCite"] == "separate" and opts["brackets"] == "[]"
    entries = []
    for cite in cites:
        number = number_of.get(cite.get("id"))
        loc = locator_text(opts, cite.get("locator"), cite.get("label", "page"), style.terms, compact=sup)
        entries.append((number, loc, cite.get("prefix", ""), cite.get("suffix", "")))
    if opts["citeSort"]:
        entries.sort(key=lambda e: (e[0] is None, e[0] or 0))
    plain = [e[0] for e in entries if e[0] is not None and not (e[1] or e[2] or e[3])]
    plain = sorted(set(plain), key=plain.index)
    dash = opts["pageDash"]
    pieces = _compress(plain, separate, dash) if opts["compress"] else [("[%d]" if separate else "%d") % n for n in plain]
    for number, loc, prefix, suffix in entries:
        if number is not None and not (loc or prefix or suffix):
            continue
        body = prefix + ("?" if number is None else str(number))
        body += ("(%s)" % loc if sup else opts["locatorSep"] + loc) if loc else ""
        body += suffix
        pieces.append("[%s]" % body if separate else body)
    if sup:
        return [(",".join(pieces), "s")]
    if separate:
        return [(", ".join(pieces), "")]
    delimiter = "; " if any(e[1] for e in entries) else ", "
    opening, closing = ("(", ")") if opts["brackets"] == "()" else ("[", "]")
    return [(opening + delimiter.join(pieces) + closing, "")]


def _who(item, opts, lang):
    people = bib_order.creators(item)
    if people:
        return [(render_names.cite_names(people, opts, lang), "")]
    title = item.get("title-short") or item.get("title", "").split(": ")[0] or "?"
    if item.get("type") in _ITALIC_TITLES:
        return [(title, "i")]
    return [(fields.quote(title, opts["quotes"] if opts["quotes"] != "none" else "curly"), "")]


def _year(item, opts, suffix):
    text = year_text(item.get("issued"), suffix)
    return text or term("no-date", opts["language"]) + ("-" + suffix if suffix else "")


def author_date_cluster(cites, items, suffixes, style, narrative=False, ambiguous_authors=()):
    """Runs of an author–date (or MLA author–page) cluster."""
    opts = style.options
    prepared = []
    for cite in cites:
        item = items.get(cite.get("id"))
        if item is None:
            prepared.append((cite, None, [("?", "")], ""))
            continue
        lang = opts["language"] if opts["termLanguage"] == "document" else language.group_of(item)
        who = _who(item, opts, lang)
        prepared.append((cite, item, who, _year(item, opts, suffixes.get(item["id"], ""))))
    if opts["citeSort"] and not narrative:
        prepared.sort(key=lambda p: bib_order.alpha_key(p[1], opts) if p[1] else ((), 0, ()))
    pieces, previous = [], None
    for cite, item, who, year in prepared:
        loc = locator_text(opts, cite.get("locator"), cite.get("label", "page"), style.terms)
        name_text = "".join(t for t, _ in who)
        piece = [(cite.get("prefix", ""), "")]
        if (opts["collapseYears"] and pieces and previous == name_text and not cite.get("suppressAuthor")
                and not narrative and opts["citeYear"]):
            pieces[-1] += [(", " + year + (opts["locatorSep"] + loc if loc else ""), "")]
            continue
        previous = name_text
        show_author = not cite.get("suppressAuthor")
        tail = []
        if opts["citeYear"] and not cite.get("authorOnly"):
            tail.append(year)
        elif item is not None and item.get("author") and name_text in ambiguous_authors:
            short = item.get("title-short") or item.get("title", "").split(": ")[0]
            piece_title = [(", ", ""), (short, "i" if item.get("type") in _ITALIC_TITLES else "")]
            who = who + piece_title
        if loc:
            tail.append(loc)
        if narrative and show_author:
            piece += who + [(" (" + opts["locatorSep"].join(tail) + ")" if tail else "", "")]
        else:
            if show_author:
                piece += who
            sep = opts["citeYearSep"] if opts["citeYear"] else " "
            joined = opts["locatorSep"].join(tail) if opts["citeYear"] else " ".join(tail)
            if joined:
                piece.append(((sep if show_author else "") + joined, ""))
        piece.append((cite.get("suffix", ""), ""))
        pieces.append(piece)
    result = []
    for index, piece in enumerate(pieces):
        if index:
            result.append((", " if narrative else opts["citeItemSep"], ""))
        result += piece
    if narrative or all(c.get("authorOnly") for c in cites):  # "Smith" written before "(2020)" by hand
        return [r for r in result if r[0]]
    return [("(", "")] + [r for r in result if r[0]] + [(")", "")]
