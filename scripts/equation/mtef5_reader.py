# SPDX-License-Identifier: LicenseRef-HST-Proprietary
# Copyright (C) 2026 HASON TECH
"""Record reader of the prototype MTEF v5 (MathType 4-7, "Equation.DSMT4") reader and StarMath writer.

Feasibility harness only: it parses an OLE "Equation Native" stream into a record tree,
writes LibreOffice Math (StarMath 5) source and records every construct and every place
where the conversion is approximate ("minor") or impossible ("fail").
"""
import struct

from mtef5_state_records import ParseError, read_ruler, read_state_record

class Reader:
    def __init__(self, b, pos=0):
        self.b, self.p = b, pos

    def u8(self):
        if self.p >= len(self.b):
            raise ParseError('eof')
        v = self.b[self.p]
        self.p += 1
        return v

    def u16(self):
        if self.p + 2 > len(self.b):
            raise ParseError('eof')
        v = struct.unpack_from('<H', self.b, self.p)[0]
        self.p += 2
        return v

    def mtuint(self):
        v = self.u8()
        return self.u16() if v == 0xFF else v

    def stringz(self):
        e = self.b.find(b'\0', self.p)
        if e < 0:
            raise ParseError('eof in string')
        s = self.b[self.p:e].decode('latin1')
        self.p = e + 1
        return s

    def nudge(self):
        dx, dy = self.u8(), self.u8()
        if dx == 128 and dy == 128:
            self.u16()
            self.u16()


OPT_NUDGE = 0x08
OPT_CHAR_EMBELL, OPT_CHAR_FUNC, OPT_CHAR_8, OPT_CHAR_16, OPT_CHAR_NOMT = 0x01, 0x02, 0x04, 0x10, 0x20
OPT_LINE_NULL, OPT_LINE_LSPACE, OPT_LP_RULER = 0x01, 0x04, 0x02


class Equation:
    def __init__(self):
        self.enc_defs, self.font_defs, self.font_style_defs, self.color_defs = [], [], [], []
        self.body = []
        self.issues = {}      # name -> 'minor' | 'fail'
        self.typeface_fonts = {}
        self.typeface_styles = {}
        self.constructs = set()

    def issue(self, name, sev='minor'):
        if self.issues.get(name) != 'fail':
            self.issues[name] = sev


def read_list(r, eq, depth):
    out = []
    while True:
        tag = r.u8()
        if tag == 0:
            return out
        out.append(read_record(r, tag, eq, depth))


def read_record(r, tag, eq, depth):
    if depth > 200:
        raise ParseError('too deep')
    if tag == 1:  # LINE
        o = r.u8()
        n = {'t': 'line', 'nudge': bool(o & OPT_NUDGE)}
        if o & OPT_NUDGE:
            r.nudge()
        if o & OPT_LINE_LSPACE:
            r.u16()
            n['lspace'] = True
        if o & OPT_LP_RULER:
            n['ruler'] = read_ruler(r)
        n['null'] = bool(o & OPT_LINE_NULL)
        n['objs'] = [] if n['null'] else read_list(r, eq, depth + 1)
        return n
    if tag == 2:  # CHAR
        o = r.u8()
        n = {'t': 'char', 'nudge': bool(o & OPT_NUDGE), 'func': bool(o & OPT_CHAR_FUNC)}
        if o & OPT_NUDGE:
            r.nudge()
        n['tf'] = r.u8() - 128
        n['mt'] = None if o & OPT_CHAR_NOMT else r.u16()
        n['fp'] = r.u8() if o & OPT_CHAR_8 else (r.u16() if o & OPT_CHAR_16 else None)
        n['emb'] = []
        if o & OPT_CHAR_EMBELL:
            for e in read_list(r, eq, depth + 1):
                if e['t'] == 'embell':
                    n['emb'].append(e['k'])
        return n
    if tag == 3:  # TMPL
        o = r.u8()
        n = {'t': 'tmpl', 'nudge': bool(o & OPT_NUDGE)}
        if o & OPT_NUDGE:
            r.nudge()
        n['sel'] = r.u8()
        v1 = r.u8()
        v = v1 & 0x7F
        if v1 & 0x80:
            v |= r.u8() << 8
        n['var'] = v
        n['topt'] = r.u8()
        n['slots'] = read_list(r, eq, depth + 1)
        return n
    if tag == 4:  # PILE
        o = r.u8()
        n = {'t': 'pile', 'nudge': bool(o & OPT_NUDGE)}
        if o & OPT_NUDGE:
            r.nudge()
        n['ha'], n['va'] = r.u8(), r.u8()
        if o & OPT_LP_RULER:
            n['ruler'] = read_ruler(r)
        n['lines'] = read_list(r, eq, depth + 1)
        return n
    if tag == 5:  # MATRIX
        o = r.u8()
        n = {'t': 'matrix', 'nudge': bool(o & OPT_NUDGE)}
        if o & OPT_NUDGE:
            r.nudge()
        n['va'], n['hj'], n['vj'], n['rows'], n['cols'] = r.u8(), r.u8(), r.u8(), r.u8(), r.u8()
        parts = [r.u8() for _ in range((2 * (n['rows'] + 1) + 7) // 8)]
        parts += [r.u8() for _ in range((2 * (n['cols'] + 1) + 7) // 8)]
        n['partitions'] = any(parts)
        n['cells'] = read_list(r, eq, depth + 1)
        return n
    if tag == 6:  # EMBELL
        o = r.u8()
        if o & OPT_NUDGE:
            r.nudge()
        return {'t': 'embell', 'k': r.u8()}
    return read_state_record(r, tag, eq)


def parse(b):
    """b = whole Equation Native stream (28-byte OLE header + MTEF)."""
    hdr = struct.unpack_from('<H', b, 0)[0]
    r = Reader(b, hdr)
    ver = r.u8()
    if ver != 5:
        raise ParseError('mtef v%d' % ver)
    r.u8(), r.u8(), r.u8(), r.u8()
    eq = Equation()
    eq.appkey = r.stringz()
    eq.inline = r.u8()
    eq.body = read_list(r, eq, 0)
    return eq
