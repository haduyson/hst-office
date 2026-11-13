# SPDX-License-Identifier: AGPL-3.0-only
"""Render one reference with an HST style layout (the template language is described in citation_style_check).

Affixes of an element that prints nothing vanish with it, so "tập (số)" style punctuation never dangles; groups
print only when a variable inside them printed. A variable used as a substitute (a title in the author position)
is not printed again. Pure Python (no uno).
"""
from . import citation_render_fields as fields
from . import citation_runs as runs_mod
from .citation_render_context import Context, condition
from .citation_render_variables import variable_runs
from .citation_runs import Out

__all__ = ["Context", "render", "render_element", "render_list"]
_WRAPS = {"()": ("(", ")"), "[]": ("[", "]"), "<>": ("<", ">")}


def _content(element, ctx, out):
    """Render the element body into ``out``; True when a variable printed."""
    if "v" in element:
        found = variable_runs(element, ctx, render_element)
        out.extend(found)
        return bool(found)
    if "group" in element:
        return render_list(element["group"], ctx, out, ctx.text(element.get("delimiter", "")), group=True)
    if "macro" in element:
        return render_list(ctx.style.macros[element["macro"]], ctx, out, ctx.text(element.get("delimiter", "")))
    if "term" in element:
        out.add(ctx.term(element["term"], element.get("plural", False)))
    else:
        out.add(ctx.text(element["text"]))
    return False


def _case(found, case):
    convert = {"upper": str.upper, "lower": str.lower, "capfirst": fields.capfirst, "title": fields.title_case}[case]
    if case == "capfirst":
        return [(convert(found[0][0]), found[0][1])] + found[1:] if found else found
    return [(convert(text), flags) for text, flags in found]


def render_element(element, ctx, out):
    if "if" in element and not condition(element["if"], ctx):
        alternative = element.get("else")
        if alternative is None:
            return False
        return render_list(alternative if isinstance(alternative, list) else [alternative], ctx, out)
    inner = Out()
    printed = _content(element, ctx, inner)
    found = inner.runs
    if not found:
        return False
    if element.get("case"):
        found = _case(found, element["case"])
    if element.get("wrap"):
        opening, closing = _WRAPS[element["wrap"]]
        found = [(opening, "")] + found + [(closing, "")]
    if element.get("quotes"):
        opening, closing = fields.QUOTES[ctx.opts["quotes"]]
        found = [(opening, "")] + found + [(closing, "")]
    flags = "".join(f for f, key in (("i", "italic"), ("b", "bold"), ("s", "sup")) if element.get(key))
    out.add(ctx.text(element.get("prefix", "")))
    out.extend(found, flags)
    out.add(ctx.text(element.get("suffix", "")))
    return printed


def render_list(elements, ctx, out, delimiter="", group=False):
    printed, start = False, out.mark()
    for element in elements:
        piece = Out()
        if render_element(element, ctx, piece):
            printed = True
        if piece.runs:
            if delimiter and out.mark() > start:
                out.add(delimiter)
            out.extend(piece.runs)
    if group and not printed:
        out.truncate(start)
    return printed


def render(elements, ctx):
    """Runs of a whole layout, punctuation tidied (American quote punctuation when the style asks for it)."""
    out = Out()
    render_list(elements, ctx, out)
    found = runs_mod.merge(out.runs)
    return runs_mod.quote_punctuation(found) if ctx.opts["punctInQuote"] else found
