# SPDX-License-Identifier: AGPL-3.0-only
"""Values of template variables: names (with substitution and labels), dates, pages, editions, DOI, publisher."""
from . import citation_render_dates as render_dates
from . import citation_render_fields as fields
from . import citation_render_names as render_names
from .citation_model import DATE_VARS, NAME_VARS
from .citation_render_context import variable_text
from .citation_runs import Out


def _names(element, ctx, render_element):
    var = element["v"]
    values = ctx.item.get(var) or []
    if not values:
        for sub in element.get("substitute", []):
            out = Out()
            if render_element(sub, ctx, out):
                ctx.used.add(sub.get("v", ""))
                return out.runs
        return []
    et_al = ctx.opts.get(element["etAl"]) if element.get("etAl") else None
    if element.get("form") == "short":
        text = render_names.cite_names(values, ctx.opts, ctx.term_lang, et_al or ctx.opts.get("noteEtAl"))
    elif ctx.subsequent_author and var == "author":
        text = ctx.opts["subsequentAuthor"]
    else:
        text = render_names.bibliography_names(values, ctx.opts, ctx.term_lang, element.get("nameForm"),
                                               element.get("viName"), et_al=et_al, and_comma=element.get("andComma"))
    if element.get("label"):
        label = ctx.term(element["label"], plural=len(values) > 1)
        text = render_names.label_text(text, label, element.get("labelPos", "after"))
    return [(text, "")]


def variable_runs(element, ctx, render_element):
    """Runs of a variable; ``render_element`` renders substitutes (passed in to avoid an import cycle)."""
    var = element["v"]
    if var in ctx.used:
        return []
    if var in NAME_VARS:
        return _names(element, ctx, render_element)
    opts = ctx.opts
    if var in DATE_VARS:
        date = ctx.item.get(var)
        suffix = ctx.year_suffix if var == "issued" else ""
        text = render_dates.format_date(date, element.get("form", "year"), ctx.term_lang, suffix)
        if not text and element.get("noDate"):
            text = ctx.term("no-date") + ("-" + suffix if suffix else "")
        return [(text, "")] if text else []
    value = variable_text(var, ctx)
    if var in ("title", "container-title") and element.get("form") == "short":
        value = ctx.item.get(var + "-short") or value.split(": ")[0]
    if not value:
        value = ctx.term(element["fallbackTerm"]) if element.get("fallbackTerm") else ""
    if not value:
        return []
    if var == "page":
        value = fields.page_range(value, opts["pageRange"], opts["pageDash"])
    elif var == "edition":
        value = fields.edition(value, ctx.term_lang, ctx.style.terms)
    elif var == "DOI":
        value = fields.doi(value, opts["doiPrefix"])
    elif var == "publisher" and element.get("form") == "prefixed":
        prefix = ctx.text("@publisherPrefix")  # "Nxb " for Vietnamese items; a typed "NXB"/"Nhà xuất bản" gives way
        value = prefix + fields.publisher(value, prefix)
    if var in ("title", "container-title", "title-or-short") and opts["titleCase"] == "title-en" and ctx.lang == "en":
        value = fields.title_case(value)
    return [(value, "")]
