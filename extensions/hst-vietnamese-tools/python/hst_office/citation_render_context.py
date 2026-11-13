# SPDX-License-Identifier: AGPL-3.0-only
"""Rendering context of one reference and the template conditions (see citation_style_check for the grammar)."""
from . import citation_language as language
from . import citation_terms as terms
from .citation_model import DATE_VARS, NAME_VARS


class Context:
    """State of one rendering: the item, the style, its language and what was already printed."""

    def __init__(self, style, item, year_suffix="", position="first", locator="", label="page", number=None,
                 subsequent_author=False, flags=()):
        """``locator`` is already formatted with its label ("tr. 15", "15") by citation_cite.locator_text."""
        self.style, self.item, self.opts = style, item, style.options
        self.lang = language.group_of(item)
        self.term_lang = self.lang if self.opts["termLanguage"] == "item" else self.opts["language"]
        self.year_suffix, self.position, self.locator, self.label = year_suffix, position, locator, label
        self.number, self.subsequent_author = number, subsequent_author
        self.flags = frozenset(flags)  # "shared-author", "suppress-author" (note styles)
        self.used = set()

    def term(self, name, plural=False):
        return terms.term(name, self.term_lang, plural, self.style.terms)

    def text(self, value):
        """Localized literal: "@option" reads a style option; {"vi": …, "other": …} follows the item's language."""
        if isinstance(value, str) and value.startswith("@"):
            value = self.opts[value[1:]]
        if not isinstance(value, dict):
            return value or ""
        # Vietnamese thesis styles: words follow the item ("Nxb" only for Vietnamese books); international styles
        # (termLanguage "document"): words follow the document
        return terms.localize(value, self.term_lang if self.opts["termLanguage"] == "document" else self.lang)


def condition(cond, ctx):
    for part in cond if isinstance(cond, list) else [cond]:
        negate = part.startswith("!")
        body = part[1:] if negate else part
        if body.startswith("type"):
            ok = ctx.item.get("type") in body.split("=", 1)[1].split(",")
            negate = negate or "!=" in body
        elif body.startswith("lang"):
            ok = ctx.lang == body.split("=", 1)[1]
            negate = negate or "!=" in body
        elif body.startswith("opt."):
            name, _, wanted = body[4:].partition("=")
            ok = str(ctx.opts.get(name)) == wanted if wanted else bool(ctx.opts.get(name))
        elif body.startswith("pos="):
            ok = ctx.position in body[4:].split("|")
        elif body == "loc":
            ok = bool(ctx.locator)
        elif body in ("shared-author", "suppress-author"):
            ok = body in ctx.flags
        elif body.startswith("day="):
            parts = ((ctx.item.get(body[4:]) or {}).get("date-parts") or [[]])[0]
            ok = len(parts) >= 3
        else:
            ok = bool(variable_text(body, ctx)) if body not in ctx.used else False
        if ok == negate:
            return False
    return True


def variable_text(name, ctx):
    """Plain value of a text variable as stored (used by conditions and simple variables)."""
    if name == "title-or-short":
        return ctx.item.get("title-short") or ctx.item.get("title", "").split(": ")[0]
    if name in NAME_VARS:
        return "x" if ctx.item.get(name) else ""
    if name in DATE_VARS:
        return "x" if ctx.item.get(name) else ""
    if name == "locator":
        return ctx.locator
    if name == "citation-number":
        return str(ctx.number or "")
    if name == "year-suffix":
        return ctx.year_suffix
    return str(ctx.item.get(name, "") or "")
