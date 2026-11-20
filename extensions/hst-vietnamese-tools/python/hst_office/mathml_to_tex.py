# SPDX-License-Identifier: AGPL-3.0-only
"""Chuyển TeX ⇄ công thức: a formula back to LaTeX from its MathML (no UNO), for formulas the toggle did not make or
that were edited since. Exam-paper LaTeX: \\frac, \\sqrt, scripts, \\left…\\right, \\begin{array} (cases are \\left\\{
with an array, as in Vietnamese papers), \\text, \\mathbb. tex(mathml) raises TexBackError for MathML it cannot write."""
import re
import xml.etree.ElementTree as ET

from .mathml_tex_symbols import (ACCENTS, ALIGN, BIG, FENCES, FUNCTIONS, LIMITS, NS, SIMPLE_BASE, SYMBOLS,
                                 TEXT_ESCAPES, decode_entities)


class TexBackError(ValueError):  # MathML the converter cannot write as LaTeX
    pass


def tex(mathml):
    """The LaTeX of a MathML document (bytes or text)."""
    if isinstance(mathml, bytes):
        mathml = mathml.decode("utf-8")
    mathml = decode_entities(mathml)
    try:
        root = ET.fromstring(mathml)
    except ET.ParseError as error:
        raise TexBackError(str(error)) from error
    children = [c for c in root if _name(c) != "annotation"]
    if len(children) == 1 and _name(children[0]) == "semantics":
        children = [c for c in children[0] if not _name(c).startswith("annotation")]
    result = _join(_node(c) for c in children).strip()
    if not result:
        raise TexBackError("empty formula")
    return result


def _name(element):
    return element.tag.replace(NS, "")


def _join(parts):
    """Concatenate LaTeX pieces, with a space where a command name would run into a letter."""
    out = ""
    for part in parts:
        if not part:
            continue
        if re.search(r"\\[A-Za-z]+$", out) and part[0].isalpha():
            out += " "
        out += part
    return out


def _arg(element):
    return "{%s}" % _node(element)


def _text(element):  # an element's own text, trimmed
    return (element.text or "").strip()


def _symbols(text):
    return _join(SYMBOLS.get(c, c) for c in text)


def _content(element):
    return _join(_node(c) for c in element)


def _node(element):
    name = _name(element)
    handler = HANDLERS.get(name)
    if handler is None:
        raise TexBackError("<%s>" % name)
    return handler(element)


def _mi(element):
    text = _text(element)
    if text in LIMITS:
        return LIMITS[text]
    if text in FUNCTIONS:
        return "\\" + text
    if text.isalpha() and (len(text) > 1 or text.isascii()) and element.get("mathvariant") == "normal":
        return "\\mathrm{%s}" % text
    return _symbols(text)


def _mn(element):
    return _text(element).replace(",", "{,}")


def _mo(element):
    return _symbols(_text(element))


def _mtext(element):
    if (element.text or "") == "°":
        return "^{\\circ}"
    return "\\text{%s}" % (element.text or "").translate(TEXT_ESCAPES)


def _mspace(element):
    width = re.match(r"([0-9.]+)", element.get("width") or "0.5")
    em = float(width.group(1)) if width else 0.5
    return "\\," if em < 1 else ("\\quad " if em < 3 else "\\qquad ")


def _mrow(element):
    children = list(element)
    if not children:
        return "{}"
    first, last = children[0], children[-1]
    opening = _fence(first, "prefix")
    closing = _fence(last, "postfix") if len(children) > 1 or opening is None else None
    if opening is None and closing is None:
        return _content(element)
    inner = children[(1 if opening is not None else 0):(len(children) - 1 if closing is not None else None)]
    stretchy = any(f is not None and f[1] for f in (opening, closing))
    body = _join(_node(c) for c in inner)
    if stretchy:
        return "\\left%s %s\\right%s" % (opening[0] if opening else ".", body, closing[0] if closing else ".")
    return (opening[0] if opening else "") + body + (closing[0] if closing else "")


def _fence(element, form):
    """(LaTeX fence, stretchy) when element is an <mo> fence of that form, else None."""
    if _name(element) != "mo" or element.get("form") != form or element.get("fence") != "true":
        return None
    fence = FENCES.get(_text(element), "." if not _text(element) else None)
    return None if fence is None else (fence, element.get("stretchy") == "true")


def _scripts(element):
    children = list(element)
    if len(children) < 2:
        raise TexBackError("script without base")
    base = _node(children[0])
    if not SIMPLE_BASE.fullmatch(base):
        base = "{%s}" % base
    name = _name(element)
    sub = sup = None
    if name in ("msub", "munder"):
        sub = children[1]
    elif name in ("msup", "mover"):
        sup = children[1]
    else:
        sub, sup = children[1], children[2] if len(children) > 2 else None
    return base + ("_" + _arg(sub) if sub is not None else "") + ("^" + _arg(sup) if sup is not None else "")


def _under_over(element):
    children = list(element)
    base = children[0]
    base_text = _text(base) if _name(base) in ("mi", "mo") else ""
    if base_text in BIG or base_text in FUNCTIONS or base_text in LIMITS:
        return _scripts(element)
    if _name(element) == "mover" and len(children) == 2 and _name(children[1]) == "mo":
        accent = ACCENTS.get((_text(children[1]), children[1].get("stretchy") == "true"))
        if accent == "\\overarc":
            return "\\overset{\\frown}%s" % _arg(base)
        if accent:
            return accent + _arg(base)
    if _name(element) == "munder" and len(children) == 2 and _text(children[1]) in ("_", "̲", "‾"):
        return "\\underline" + _arg(base)
    if _name(element) == "mover":
        return "\\overset%s%s" % (_arg(children[1]), _arg(base))
    if _name(element) == "munder":
        return "\\underset%s%s" % (_arg(children[1]), _arg(base))
    return "\\overset%s{\\underset%s%s}" % (_arg(children[2]), _arg(children[1]), _arg(base))


def _mtable(element):
    rows = [r for r in element if _name(r) in ("mtr", "mlabeledtr")]
    width = max((len(list(r)) for r in rows), default=0)
    if not width:
        raise TexBackError("empty table")
    aligns = ["c"] * width
    for row in rows:
        for index, cell in enumerate(row):
            if cell.get("columnalign"):
                aligns[index] = ALIGN.get(cell.get("columnalign"), "c")
    lines = [" & ".join(_content(cell) for cell in row) for row in rows]
    return "\\begin{array}{%s}%s\\end{array}" % ("".join(aligns), "\\\\ ".join(lines))


def _mstyle(element):
    body = _content(element)
    variant = element.get("mathvariant")
    if variant == "bold":
        return "\\mathbf{%s}" % body
    if variant == "normal" and not body.startswith("\\"):
        return "\\mathrm{%s}" % body
    return body


HANDLERS = {"mi": _mi, "mn": _mn, "mo": _mo, "mtext": _mtext, "ms": _mtext, "mspace": _mspace, "mrow": _mrow,
            "msub": _scripts, "msup": _scripts, "msubsup": _scripts, "munder": _under_over, "mover": _under_over,
            "munderover": _under_over, "mtable": _mtable, "mstyle": _mstyle, "mpadded": _content, "math": _content,
            "mfrac": lambda e: "\\frac%s%s" % (_arg(e[0]), _arg(e[1])), "msqrt": lambda e: "\\sqrt{%s}" % _content(e),
            "mroot": lambda e: "\\sqrt[%s]%s" % (_node(e[1]), _arg(e[0])), "semantics": _content,
            "mphantom": lambda e: "\\phantom{%s}" % _content(e)}
