# SPDX-License-Identifier: AGPL-3.0-only
"""Evaluate the rendering elements of an imported CSL style for one item: cs:text, cs:number, cs:label, cs:names,
cs:date, cs:group, cs:choose and the formatting attributes (prefix, suffix, delimiter, font-style, font-weight,
vertical-align, text-case, quotes, strip-periods). Output goes into citation_runs.Out. Pure Python (no uno)."""
import re

from . import citation_csl_names as csl_names
from . import citation_render_fields as fields
from .citation_csl_terms import lookup
from .citation_runs import Out
from .citation_terms import term_language

_ROMAN = ((1000, "m"), (900, "cm"), (500, "d"), (400, "cd"), (100, "c"), (90, "xc"), (50, "l"), (40, "xl"), (10, "x"),
          (9, "ix"), (5, "v"), (4, "iv"), (1, "i"))


class Context:
    def __init__(self, style, item, section, position="first", locator="", label="page", number=None,
                 range_end=None, year_suffix=""):
        self.style, self.item, self.section = style, item, section
        self.vietnamese = term_language(style.default_locale) == "vi"
        self.position, self.locator, self.label = position, locator, label
        self.number, self.range_end, self.year_suffix = number, range_end, year_suffix
        self.ascii, self.used, self.suffix_done = False, set(), False

    def term(self, name, form="long", plural=False):
        return lookup(name, form or "long", plural, self.style.terms, self.vietnamese)

    def year_suffix_for(self, node):
        if node.get("variable") != "issued" or self.suffix_done or self.style.explicit_year_suffix:
            return ""
        self.suffix_done = True
        return self.year_suffix


def value_of(name, ctx, form=None):
    if name in ctx.used:
        return ""
    if name == "citation-number":
        return "%s–%s" % (ctx.number, ctx.range_end) if ctx.range_end else str(ctx.number or "")
    if name == "year-suffix":
        return ctx.year_suffix
    if name == "locator":
        return ctx.locator
    if form == "short" and ctx.item.get(name + "-short"):
        return str(ctx.item[name + "-short"])
    value = ctx.item.get(name, "")
    return str(value) if not isinstance(value, (dict, list)) else ("x" if value else "")


def _test(node, ctx):
    checks = []
    for attr in ("type", "variable", "is-numeric", "locator", "position", "is-uncertain-date", "disambiguate"):
        for wanted in (node.get(attr) or "").split():
            if attr == "type":
                checks.append(ctx.item.get("type") == wanted)
            elif attr == "variable":
                checks.append(bool(value_of(wanted, ctx)))
            elif attr == "is-numeric":
                checks.append(bool(re.fullmatch(r"\d+(\s*[-–&,]\s*\d+)*", value_of(wanted, ctx))))
            elif attr == "locator":
                checks.append(ctx.label == wanted.replace("sub-verbo", "sub verbo"))
            elif attr == "position":
                checks.append(ctx.position == wanted or (wanted == "subsequent" and ctx.position == "ibid"))
            else:
                checks.append(False)
    match = node.get("match", "all")
    if not checks:
        return node.tag == "else"
    return all(checks) if match == "all" else any(checks) if match == "any" else not any(checks)


def _case(text, case):
    if case == "lowercase":
        return text.lower()
    if case == "uppercase":
        return text.upper()
    if case == "capitalize-first":
        return fields.capfirst(text)
    if case == "capitalize-all":
        return " ".join(fields.capfirst(w) for w in text.split(" "))
    if case == "title":
        return fields.title_case(text)
    if case == "sentence":
        return fields.sentence_case(text) if fields.is_all_caps(text) else fields.capfirst(text)
    return text


def _ordinal(value, ctx, form):
    if not value.isdigit():
        return value
    if form == "roman":
        number, text = int(value), ""
        for amount, letters in _ROMAN:
            while number >= amount:
                text, number = text + letters, number - amount
        return text
    if form in ("ordinal", "long-ordinal") and not ctx.vietnamese:
        number = int(value)
        key = "ordinal-%02d" % (number % 100) if 11 <= number % 100 <= 13 else "ordinal-%02d" % (number % 10)
        return value + (ctx.term(key) if number % 10 in (1, 2, 3) and not 11 <= number % 100 <= 13 else ctx.term("ordinal"))
    return value


def _content(node, ctx, out):
    """Render node content into out; True when a variable produced text."""
    tag = node.tag
    if tag == "text":
        if node.get("macro"):
            return render_children(ctx.style.macros[node.get("macro")], ctx, out)
        if node.get("variable"):
            name = node.get("variable")
            value = value_of(name, ctx, node.get("form"))
            if name == "page" and value:
                value = fields.page_range(value, "minimal" if ctx.style.root.get("page-range-format") == "minimal"
                                          else "expanded", "–")
            out.add(value)
            return bool(value)
        out.add(ctx.term(node.get("term"), node.get("form"), node.get("plural") == "true") if node.get("term")
                else node.get("value", ""))
        return False
    if tag == "number":
        value = value_of(node.get("variable", ""), ctx)
        out.add(_ordinal(value, ctx, node.get("form", "numeric")))
        return bool(value)
    if tag == "label":
        name = node.get("variable", "")
        value = value_of(name, ctx)
        if not value:
            return False
        plural = node.get("plural", "contextual") == "always" or (node.get("plural", "contextual") == "contextual"
                                                                     and fields.is_range(value))
        out.add(ctx.term(ctx.label if name == "locator" else name, node.get("form", "long"), plural))
        return False
    if tag == "names":
        return csl_names.render_names(node, ctx, out, render_node)
    if tag == "date":
        text = csl_names.date_text(node, ctx, lambda part, piece: _affixed(part, piece))
        out.add(text)
        return bool(text)
    if tag == "group":
        mark = out.mark()
        printed = render_children(node, ctx, out, node.get("delimiter", ""))
        if not printed and _has_variables(node, ctx):
            out.truncate(mark)
        return printed
    if tag == "choose":
        for branch in node.children:
            if _test(branch, ctx):
                return render_children(branch, ctx, out)
    return False


def _has_variables(node, ctx):
    if node.get("variable") or node.tag in ("names", "date", "number") or (node.tag == "text" and node.get("macro")):
        return True
    return any(_has_variables(child, ctx) for child in node.children)


def _affixed(node, text):
    return (node.get("prefix", "") + text + node.get("suffix", "")) if text else ""


def render_node(node, ctx, out):
    inner = Out()
    printed = _content(node, ctx, inner)
    runs = inner.runs
    if not runs or node.tag in ("macro",):
        return printed
    if node.get("strip-periods") == "true":
        runs = [(t.replace(".", ""), f) for t, f in runs]
    if node.get("text-case"):
        runs = [(_case(t, node.get("text-case")), f) for t, f in runs]
    if node.get("quotes") == "true":
        runs = [("“", "")] + runs + [("”", "")]
    flags = ("i" if node.get("font-style") == "italic" else "") + ("b" if node.get("font-weight") == "bold" else "") \
        + ("s" if node.get("vertical-align") == "sup" else "")
    out.add(node.get("prefix", ""))
    out.extend(runs, flags)
    out.add(node.get("suffix", ""))
    return printed


def render_children(node, ctx, out, delimiter=""):
    printed, first = False, True
    for child in node.children:
        piece = Out()
        printed = render_node(child, ctx, piece) or printed
        if piece.runs:
            if not first and delimiter:
                out.add(delimiter)
            out.extend(piece.runs)
            first = False
    return printed
