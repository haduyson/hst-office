# SPDX-License-Identifier: AGPL-3.0-only
"""Names and dates of imported CSL styles (cs:names / cs:name / cs:et-al, cs:date / cs:date-part).

One deliberate difference from CSL: a Vietnamese name that is not inverted prints family name first
("Nguyễn Văn An"), as Vietnamese is written; CSL would print "Văn An Nguyễn". Pure Python (no uno)."""
from . import citation_dates as dates
from . import citation_names as names
from .citation_csl_parse import Node
from .citation_csl_terms import lookup, month
from .citation_runs import Out
from .vietnamese_text import remove_diacritics

INHERITED = ("and", "delimiter-precedes-et-al", "delimiter-precedes-last", "et-al-min", "et-al-use-first",
             "et-al-use-last", "et-al-subsequent-min", "et-al-subsequent-use-first", "initialize",
             "initialize-with", "name-as-sort-order", "sort-separator", "name-form", "name-delimiter")


def name_options(ctx, node):
    """Name attributes: style, then citation/bibliography, then the cs:name element itself."""
    options = {}
    for source in (ctx.style.root, ctx.section):
        if source is not None:
            options.update({k: v for k, v in source.attrs.items() if k in INHERITED})
    if "name-form" in options:
        options.setdefault("form", options.pop("name-form"))
    if "name-delimiter" in options:
        options.setdefault("delimiter", options.pop("name-delimiter"))
    if node is not None:
        options.update(node.attrs)
    return options


def _initials(given, options):
    mark = options.get("initialize-with")
    if mark is None or options.get("initialize") == "false":
        return given
    with_period = "." in mark
    text = names.initials(given, period=with_period, space=mark.endswith(" "))
    return text if with_period else text.replace(".", mark.strip())


def person(name, options, inverted, ctx):
    if name.get("literal"):
        return name["literal"]
    family = " ".join(p for p in (name.get("non-dropping-particle"), name.get("family")) if p)
    if options.get("form") == "short":
        return family
    if names.is_east_asian(name):
        return family + name.get("given", "")
    given = _initials(name.get("given", ""), options)
    if ctx.ascii:
        family, given = remove_diacritics(family), remove_diacritics(given)
    if not given:
        return family
    if inverted:
        return family + options.get("sort-separator", ", ") + given
    return (family + " " + given) if names.is_vietnamese(name) else (given + " " + family)


def name_list(values, options, ctx, et_al_text):
    count = len(values)
    if options.get("form") == "count":
        return str(count)
    minimum = int(options.get("et-al-min", 0) or 0)
    use = int(options.get("et-al-use-first", 1) or 1)
    if ctx.position != "first" and options.get("et-al-subsequent-min"):
        minimum = int(options["et-al-subsequent-min"])
        use = int(options.get("et-al-subsequent-use-first", use))
    order = options.get("name-as-sort-order")
    parts = [person(n, options, order == "all" or (order == "first" and i == 0), ctx) for i, n in enumerate(values)]
    delimiter = options.get("delimiter", ", ")
    if minimum and count >= minimum and use < count:
        shown = parts[:use]
        if options.get("et-al-use-last") == "true" and use + 1 < count:
            return delimiter.join(shown) + delimiter + "… " + parts[-1]
        rule = options.get("delimiter-precedes-et-al", "contextual")
        comma = rule == "always" or (rule == "contextual" and use >= 2) or (rule == "after-inverted-name" and order)
        return delimiter.join(shown) + (delimiter if comma else " ") + et_al_text
    if count == 1 or not options.get("and"):
        return delimiter.join(parts)
    word = "&" if options["and"] == "symbol" else lookup("and", "long", False, ctx.style.terms, ctx.vietnamese)
    rule = options.get("delimiter-precedes-last", "contextual")
    comma = rule == "always" or (rule == "contextual" and count >= 3) or (rule == "after-inverted-name" and order)
    return delimiter.join(parts[:-1]) + (delimiter.rstrip() if comma else "") + " " + word + " " + parts[-1]


def _part(name, value, form, ctx):
    if name == "month":
        if form in ("numeric", "numeric-leading-zeros"):
            return ("%02d" if form.endswith("zeros") else "%d") % value
        return month(value, form or "long", ctx.vietnamese)
    if name == "day":
        return ("%02d" % value) if form == "numeric-leading-zeros" else str(value)
    return str(value)[-2:] if form == "short" else str(value)


def date_text(node, ctx, render_affixes):
    """Text of a cs:date for the item; ``render_affixes(node, text)`` applies a date-part's own affixes."""
    date = ctx.item.get(node.get("variable", ""))
    if not date:
        return ""
    if "date-parts" not in date:
        return date.get("literal", "")
    if len(date["date-parts"]) > 1:
        return "–".join(str(p[0]) for p in date["date-parts"] if p) + ctx.year_suffix_for(node)
    year, month_value, day = dates.parts(date)
    wanted = {"year": ["year"], "year-month": ["year", "month"]}.get(node.get("date-parts"), ["year", "month", "day"])
    explicit = node.all("date-part")
    form = node.get("form", "text")
    if explicit:
        specs, separator = [(p.get("name"), p.get("form"), p) for p in explicit], node.get("delimiter", "")
    else:
        order = ["day", "month", "year"] if ctx.vietnamese else ["month", "day", "year"]
        specs = [(n, "numeric" if form == "numeric" else None, None) for n in order]
        separator = "/" if form == "numeric" else " "
    pieces = []
    for name, part_form, part in specs:
        value = {"year": year, "month": month_value, "day": day}.get(name)
        if not value or name not in wanted:
            continue
        text = _part(name, value, part_form, ctx) + (ctx.year_suffix_for(node) if name == "year" else "")
        pieces.append(render_affixes(part, text) if part is not None else text)
    if not explicit and form == "text" and len(pieces) == 3:
        return ("ngày %s %s năm %s" if ctx.vietnamese else "%s %s, %s") % tuple(pieces)  # May 7, 2009
    if not explicit and form == "text" and ctx.vietnamese and len(pieces) == 2:
        return "%s năm %s" % tuple(pieces)
    return separator.join(p for p in pieces if p)


def render_names(node, ctx, out, render_node):
    """cs:names: each variable's list (with its cs:label), else the first cs:substitute child that prints."""
    name_node, et_al_node, label_node = node.child("name"), node.child("et-al"), node.child("label")
    options = name_options(ctx, name_node)
    et_al = ctx.term(et_al_node.get("term", "et-al") if et_al_node is not None else "et-al")
    pieces = []
    for var in node.get("variable", "").split():
        values = ctx.item.get(var) or []
        if not values or var in ctx.used:
            continue
        text = name_list(values, options, ctx, et_al)
        if label_node is not None and options.get("form") != "count":
            label = label_node.get("prefix", "") + ctx.term(var, label_node.get("form", "long"), len(values) > 1) + \
                label_node.get("suffix", "")
            before = name_node is not None and node.children.index(label_node) < node.children.index(name_node)
            text = label + text if before else text + label
        pieces.append(text)
    if pieces:
        out.add(node.get("delimiter", ", ").join(pieces))
        return True
    substitute = node.child("substitute")
    for child in substitute.children if substitute is not None else []:
        if child.tag == "names" and not child.children:  # a bare cs:names inherits the parent's name settings
            child = Node("names", dict(node.attrs, **child.attrs), [c for c in node.children if c.tag != "substitute"],
                         "")
        piece = Out()
        if render_node(child, ctx, piece) and piece.runs:
            out.extend(piece.runs)
            ctx.used.update(child.get("variable", "").split())
            return True
    return False
