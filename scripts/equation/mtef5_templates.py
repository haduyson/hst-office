# SPDX-License-Identifier: LicenseRef-HST-Proprietary
# Copyright (C) 2026 HASON TECH
"""MTEF templates (fractions, roots, fences, scripts, big operators ...)."""
from mtef5_tables import *  # noqa: F401,F403  (shared tables)


class TemplateMixin:
    def slots(self, t):
        return [s for s in t['slots'] if s['t'] in ('line', 'pile')]

    def slot(self, t, i):
        sl = self.slots(t)
        if i >= len(sl):
            return '{}'
        s = sl[i]
        if s['t'] == 'pile':
            return '{' + self.pile(s) + '}'
        return '{' + self.objs(s['objs']) + '}'

    def empty(self, t, i):
        sl = self.slots(t)
        return i >= len(sl) or (sl[i]['t'] == 'line' and (sl[i]['null'] or not sl[i]['objs']))

    def tmpl(self, t):
        eq, sel, v = self.eq, t['sel'], t['var']
        if t['nudge']:
            eq.issue('nudge')
        body = lambda i: self.slot(t, i)  # noqa: E731
        if sel <= 9:  # fences
            eq.constructs.add('fence')
            pairs = {0: ('langle', 'rangle'), 1: ('(', ')'), 2: ('lbrace', 'rbrace'), 3: ('[', ']'),
                     4: ('lline', 'rline'), 5: ('ldline', 'rdline'), 6: ('lfloor', 'rfloor'),
                     7: ('lceil', 'rceil'), 8: ('ldbracket', 'rdbracket')}
            if sel == 9:
                l = {0x0: '(', 0x1: '[', 0x2: ']', 0x3: ')'}
                lo, ro = l.get(v & 0x3, '['), l.get((v >> 4) & 0x3, ']')
                fl, fr = lo, ro
                fl = {'[': '[', ']': ']', '(': '(', ')': ')'}[fl]
                return 'left %s %s right %s' % (fl if fl != ']' else 'rbrack' if False else fl, body(0), fr), 'atom'
            lft, rgt = pairs[sel]
            if not (v & 0x3):
                v |= 0x3
            return 'left %s %s right %s' % (lft if v & 1 else 'none', body(0), rgt if v & 2 else 'none'), 'atom'
        if sel == 10:
            eq.constructs.add('root')
            if v & 1 and not self.empty(t, 1):
                return 'nroot %s %s' % (body(1), body(0)), 'atom'
            return 'sqrt %s' % body(0), 'atom'
        if sel == 11:
            eq.constructs.add('frac')
            if v & 1:
                eq.issue('small-frac')
            if v & 2:
                return '%s wideslash %s' % (body(0), body(1)), 'atom'
            return '{%s over %s}' % (body(0), body(1)), 'atom'
        if sel in (12, 13):
            eq.constructs.add('embell')
            if v & 1:
                eq.issue('double-bar')
            return '%s %s' % ('underline' if sel == 12 else 'overline', body(0)), 'atom'
        if sel == 14:
            eq.constructs.add('arrow')
            top, bot = (not self.empty(t, 0)), (not self.empty(t, 1))
            arrow = '"⇌"' if v & 0x3 else ('"←"' if v & 0x10 and not v & 0x20 else 'toward')
            eq.issue('arrow-text-width')  # StarMath has no extensible arrow under/over text
            s = arrow
            if top:
                s += ' csup %s' % body(0)
            if bot:
                s += ' csub %s' % body(1)
            return '{' + s + '}', 'atom'
        if 15 <= sel <= 22:
            eq.constructs.add('bigop')
            if sel == 15:
                op = {1: 'int', 2: 'iint', 3: 'iiint'}.get(v & 0x3, 'int')
                if v & 0xC:
                    op = {1: 'lint', 2: 'llint', 3: 'lllint'}.get(v & 0x3, 'lint')
            elif sel in (21, 22):
                # big operator whose glyph is the 4th slot (often a plain letter used as a base)
                sub_kw, sup_kw = ('csub', 'csup') if v & 0x40 else ('rsub', 'rsup')
                s = '{' + body(3) + '}'
                if not self.empty(t, 1):
                    s += ' %s %s' % (sub_kw, body(1))
                if not self.empty(t, 2):
                    s += ' %s %s' % (sup_kw, body(2))
                eq.issue('custom-bigop-size')
                return '{%s %s}' % (s, body(0)), 'atom'
            else:
                op = {16: 'sum', 17: 'prod', 18: 'coprod', 19: 'Union', 20: 'Intersection'}[sel]
            s = op
            if not self.empty(t, 1):
                s += ' from %s' % body(1)
            if not self.empty(t, 2):
                s += ' to %s' % body(2)
            return '{%s %s}' % (s, body(0)), 'atom'
        if sel == 23:
            eq.constructs.add('bigop')
            main = body(0)
            s = main
            if not self.empty(t, 1):
                s += ' csub %s' % body(1)
            if not self.empty(t, 2):
                s += ' csup %s' % body(2)
            return '{' + s + '}', 'atom'
        if sel in (24, 25):
            eq.constructs.add('embell')
            if sel == 25:
                eq.issue('hbracket')
            return '{%s %s %s}' % (body(0), 'overbrace' if v & 1 else 'underbrace', body(1)), 'atom'
        if sel == 26:
            eq.issue('long-division', 'fail')
            return '{%s}' % body(0), 'atom'
        if sel in (27, 28, 29):
            eq.constructs.add('script')
            parts = []
            pre = bool(v & 1)
            if sel in (27, 29) and not self.empty(t, 0):
                parts.append(('lsub' if pre else 'rsub') + ' ' + body(0))
            if sel in (28, 29) and not self.empty(t, 1):
                parts.append(('lsup' if pre else 'rsup') + ' ' + body(1))
            return ' '.join(parts) or '', ('pre' if pre else 'post')
        if sel == 30:
            eq.constructs.add('fence')
            l = body(0) if v & 1 else ''
            r = body(1) if v & 2 else ''
            return 'langle %s mline %s rangle' % (l or '{}', r or '{}'), 'atom'
        if 31 <= sel <= 34:
            eq.constructs.add('embell')
            if sel == 31:
                if v & 0x4 or (v & 0x1 and not v & 0x2):
                    eq.issue('vector-variant')
                return ('wideharpoon %s' if v & 0x8 else 'widevec %s') % body(0), 'atom'
            if sel == 34:
                eq.issue('arc')  # no over-arc in StarMath
                return 'widehat %s' % body(0), 'atom'
            return ('widetilde %s' if sel == 32 else 'widehat %s') % body(0), 'atom'
        if sel == 35:
            eq.issue('jstatus', 'fail')
            return body(0), 'atom'
        if sel == 36:
            if v & 1:
                return 'overstrike %s' % body(0), 'atom'
            eq.issue('diagonal-strike')
            return body(0), 'atom'
        if sel == 37:
            eq.issue('box')
            return body(0), 'atom'
        eq.issue('tmpl:%d' % sel, 'fail')
        return '{}', 'atom'
