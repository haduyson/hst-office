# SPDX-License-Identifier: AGPL-3.0-only
"""Character runs: variables, numbers, text, functions, symbols, embellishments."""
from mtef5_tables import *  # noqa: F401,F403  (shared tables)


class TextMixin:
    def role(self, c):
        tf = c['tf']
        if tf < 0:
            return 'text'   # explicit font style: treat as text run
        return {1: 'text', 2: 'func', 3: 'var', 4: 'var', 5: 'ucg', 8: 'num', 7: 'vec', 9: 'text', 10: 'text',
                12: 'text', 24: 'space', 23: 'marker'}.get(tf, 'sym')

    def run(self, run):
        role = self.role(run[0])
        s = self.decode_chars(run)
        if s is None:
            return '{}'
        if any(is_viet(ch) for ch in s):
            self.eq.constructs.add('viet')
        res = self.run_text(role, run, s)
        c0 = run[-1]
        for e in c0['emb']:
            res = self.embellish(res, e)
        return res

    def run_text(self, role, run, s):
        eq = self.eq
        if role == 'space':
            return ' '.join(MT_PUA.get(ord(ch), '`') for ch in s if MT_PUA.get(ord(ch), '`'))
        if role == 'marker':
            eq.issue('tab-align')
            return ''
        if role == 'text':
            eq.constructs.add('text')
            if s.strip() == '':
                return ' '.join('`' for _ in s)  # a text-style space is narrow in MathType
            return quote(s)
        if role == 'func':
            if s in SM_FUNCS:
                return s
            if s in FUNCS:
                return 'func ' + s
            if s.isalpha() and s.isascii():
                return 'func ' + s
            return quote(s)
        if role == 'num':
            out, cur = [], ''
            for ch in s:
                if ch.isdigit():
                    cur += ch
                else:
                    if cur:
                        out.append(cur)
                        cur = ''
                    out.append(self.sym(ch))
            if cur:
                out.append(cur)
            return ' '.join(out)
        if role in ('var', 'ucg', 'vec'):
            parts = []
            for ch in s:
                if ch in GREEK_UC:
                    parts.append('%' + GREEK_UC[ch])
                elif ch.isalpha() and ch.isascii():
                    parts.append(ch)
                elif ch.isalpha():
                    parts.append(ch if role != 'ucg' else 'nitalic ' + ch)
                else:
                    parts.append(self.sym(ch))
            # consecutive letters become one identifier unless that spells a StarMath keyword
            words = []
            for x in parts:
                if words and len(x) == 1 and x.isalpha() and words[-1].isalpha() \
                        and (words[-1] + x).lower() not in KEYWORDS:
                    words[-1] += x
                else:
                    words.append(x)
            res = ' '.join(words)
            st = self.eq.typeface_styles.get(run[0]['tf'])
            if role == 'var' and st is not None and not st & 2:
                res = ' '.join('nitalic ' + x if x.isalpha() else x for x in words)
            if role == 'vec' or (st is not None and st & 1):
                return 'bold {' + res + '}'
            return res
        return ' '.join(self.sym(ch) for ch in s)

    def sym(self, ch):
        o = ord(ch)
        if ch in SYMBOLS:
            return SYMBOLS[ch]
        if o in MT_PUA:
            return MT_PUA[o]
        if 0xE000 <= o <= 0xF8FF:
            self.eq.issue('pua-char:%04X' % o, 'fail')
            return '{}'
        if ch.isdigit():
            return ch
        if ch.isalpha():
            return ch if ch.isascii() else ch
        if ch.isspace():
            return '~'
        # any other printable symbol: show the glyph as text (correct look, operator spacing may differ)
        self.eq.issue('sym-as-text')
        return quote(ch)

    def embellish(self, res, e):
        self.eq.constructs.add('embell')
        if e in EMBELL:
            return '%s {%s}' % (EMBELL[e], res)
        if e in PRIMES:
            return '{%s} rsup {%s}' % (res, '′' * len(PRIMES[e]))
        if e == 10 and res.strip() == '=':
            return '<>'
        self.eq.issue('embell:%d' % e)
        return res
