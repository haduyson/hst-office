# SPDX-License-Identifier: AGPL-3.0-only
"""Prototype MTEF v5 (MathType 4-7, "Equation.DSMT4") reader and StarMath writer.

Feasibility harness only: it parses an OLE "Equation Native" stream into a record tree,
writes LibreOffice Math (StarMath 5) source and records every construct and every place
where the conversion is approximate ("minor") or impossible ("fail").
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from mtef5_reader import Equation, Reader, parse  # noqa: E402,F401
from mtef5_state_records import ParseError  # noqa: E402,F401
from mtef5_fonts import FontMixin  # noqa: E402
from mtef5_text import TextMixin  # noqa: E402
from mtef5_templates import TemplateMixin  # noqa: E402
from mtef5_layout import LayoutMixin  # noqa: E402


class Writer(FontMixin, TextMixin, TemplateMixin, LayoutMixin):
    def __init__(self, eq):
        self.eq = eq


def detect_chem(eq, sm):
    """Heuristic: chemical formulae/reactions (element symbol followed by a numeric subscript,
    or a reaction arrow template)."""
    import re
    if 'arrow' in eq.constructs:
        return True
    return bool(re.search(r'(?<![A-Za-z])(?:H|O|C|N|S|P|K|Na|Ca|Mg|Al|Fe|Cu|Zn|Cl|Br|Ba|Ag|Mn|Cr|Pb)\s*'
                          r'(?:"[^"]*"\s*)?rsub\s*\{\s*\d', sm))


def convert(b):
    eq = parse(b)
    w = Writer(eq)
    top = [o for o in eq.body if o['t'] in ('line', 'pile', 'matrix', 'tmpl', 'char', 'size', 'color', 'ruler')]
    parts = []
    for o in top:
        if o['t'] == 'pile':
            parts.append(w.pile(o))
        elif o['t'] == 'line':
            parts.append(w.objs(o['objs']))
        else:
            parts.append(w.objs([o]))
    sm = ' '.join(p for p in parts if p).strip() or '{}'
    if detect_chem(eq, sm):
        eq.constructs.add('chem')
    return sm, eq


def expected_chars(eq):
    """Letters, digits and = + of the equation, from the record tree (independent of the writer)."""
    w = Writer(Equation())
    w.eq.font_defs, w.eq.font_style_defs = eq.font_defs, eq.font_style_defs
    out = []

    w.eq.typeface_fonts = eq.typeface_fonts

    def walk(objs, in_tmpl_slot=False):
        run = []
        for o in list(objs) + [{'t': 'end'}]:
            t = o['t']
            if t == 'char' and o['tf'] not in (22, 23, 24) and not in_tmpl_slot:
                run.append(o)
                continue
            if run:
                txt = w.decode_chars(run) or ''
                out.extend(ch for ch in txt if ch.isalnum() or ch in '=+')
                run = []
            if t == 'char':
                continue
            elif t == 'line':
                walk(o['objs'])
            elif t == 'pile':
                walk(o['lines'])
            elif t == 'matrix':
                walk(o['cells'])
            elif t == 'tmpl':
                for s in o['slots']:
                    if s['t'] == 'char':
                        continue
                    walk([s])
    walk(eq.body)
    return ''.join(out)
