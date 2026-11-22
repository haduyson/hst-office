# SPDX-License-Identifier: LicenseRef-HST-Proprietary
# Copyright (C) 2026 HASON TECH
"""Lines, piles and matrices; operand fix-ups StarMath needs."""
from mtef5_tables import *  # noqa: F401,F403  (shared tables)


class LayoutMixin:
    def objs(self, objs):
        out = []          # output tokens of this line
        scripted = set()  # indices of tokens that already carry a post-script
        prescripts = []

        def push(tok):
            nonlocal prescripts
            if prescripts and tok:
                if tok in BINARY:
                    # scripts written before an operator: keep them on an empty base
                    out.append('{} ' + ' '.join(prescripts))
                else:
                    tok = '{' + tok + '} ' + ' '.join(prescripts)
                prescripts = []
            out.append(tok)

        i = 0
        while i < len(objs):
            o = objs[i]
            t = o['t']
            if o.get('nudge'):
                self.eq.issue('nudge')
            if t == 'char':
                # group runs of characters with the same role
                j = i
                run = []
                while j < len(objs) and objs[j]['t'] == 'char' and self.role(objs[j]) == self.role(o) \
                        and not objs[j]['emb'] and (j == i or not objs[j]['func'] or objs[j - 1]['func']):
                    run.append(objs[j])
                    j += 1
                if not run:
                    run, j = [o], i + 1
                if self.role(o) == 'sym':
                    for c in run:
                        push(self.run([c]))
                else:
                    push(self.run(run))
                i = j
                continue
            if t == 'tmpl':
                s, kind = self.tmpl(o)
                if kind == 'pre':
                    if s:
                        prescripts.append(s)
                elif kind == 'post':
                    if not out or not out[-1]:
                        out.append('{}')
                    if len(out) - 1 in scripted:
                        out[-1] = '{' + out[-1] + '}'
                    if s:
                        out[-1] = out[-1] + ' ' + s
                        scripted.add(len(out) - 1)
                else:
                    push(s)
            elif t == 'pile':
                push(self.pile(o))
            elif t == 'matrix':
                push(self.matrix(o))
            elif t == 'line':
                push('{' + self.objs(o['objs']) + '}')
            elif t == 'size':
                if o.get('explicit'):
                    self.eq.issue('size-override')
            elif t == 'color':
                cd = self.eq.color_defs[o['i'] - 1] if 0 < o['i'] <= len(self.eq.color_defs) else None
                if cd and any(cd[0][:3]):
                    self.eq.issue('color')
            elif t == 'ruler':
                self.eq.issue('tab-align')
            i += 1
        if prescripts:
            out.append('{} ' + ' '.join(prescripts))
        # StarMath needs an operand on both sides of a relation/binary operator
        merged = []
        for tok in (x for x in out if x):
            # 4 "," 6 -> 4,6 (one number, decimal comma or point)
            if tok.isdigit() and len(merged) >= 2 and merged[-1] in (',', '","', '.', '"."') \
                    and merged[-2].replace(',', '').replace('.', '').isdigit():
                sep = merged.pop().strip('"')
                merged[-1] = merged[-1] + sep + tok
                continue
            merged.append(tok)
        fixed = []
        for tok in merged:
            if tok in BINARY and (not fixed or fixed[-1] in BINARY or fixed[-1] in UNARY):
                fixed.append('{}')
            fixed.append(tok)
        if fixed and fixed[-1] in BINARY | UNARY:
            fixed.append('{}')
        return ' '.join(fixed)

    def pile(self, p):
        self.eq.constructs.add('pile')
        if p.get('ruler'):
            self.eq.issue('tab-align')
        lines = []
        for ln in p['lines']:
            if ln['t'] == 'line':
                if ln.get('ruler'):
                    self.eq.issue('tab-align')
                lines.append('{' + self.objs(ln['objs']) + '}')
            elif ln['t'] in ('pile', 'matrix'):
                lines.append('{' + (self.pile(ln) if ln['t'] == 'pile' else self.matrix(ln)) + '}')
        if len(lines) == 1:
            return lines[0]
        al = {1: 'alignl ', 3: 'alignr '}.get(p['ha'], '')
        if p['ha'] in (4, 5):
            self.eq.issue('tab-align')
        return 'stack{' + ' # '.join(al + x for x in lines) + '}'

    def matrix(self, m):
        self.eq.constructs.add('matrix')
        if m['partitions']:
            self.eq.issue('matrix-lines')
        cells = []
        for c in m['cells']:
            if c['t'] == 'line':
                cells.append('{' + self.objs(c['objs']) + '}')
            elif c['t'] == 'pile':
                cells.append('{' + self.pile(c) + '}')
        rows, cols = m['rows'], m['cols']
        if rows * cols != len(cells):
            self.eq.issue('matrix-shape', 'fail')
            return 'matrix{' + ' # '.join(cells) + '}'
        return 'matrix{' + ' ## '.join(' # '.join(cells[r * cols:(r + 1) * cols]) for r in range(rows)) + '}'
