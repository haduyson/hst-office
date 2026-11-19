# SPDX-License-Identifier: AGPL-3.0-only
"""MTEF v5 records that carry no layout: rulers, sizes, colours, fonts, preferences."""


class ParseError(Exception):
    pass


def read_ruler(r):
    n = r.u8()
    for _ in range(n):
        r.u8()
        r.u16()
    return n


def read_state_record(r, tag, eq):
    if tag == 7:  # RULER
        return {'t': 'ruler', 'n': read_ruler(r)}
    if tag == 8:  # FONT_STYLE_DEF
        eq.font_style_defs.append((r.mtuint(), r.u8()))
        return {'t': 'state'}
    if tag == 9:  # SIZE
        s = r.u8()
        if s == 101:
            r.u16()
        elif s == 100:
            r.u8()
            r.u16()
        else:
            r.u8()
        return {'t': 'size', 'explicit': s in (100, 101)}
    if 10 <= tag <= 14:  # FULL SUB SUB2 SYM SUBSYM
        return {'t': 'size', 'explicit': False, 'k': tag}
    if tag == 15:  # COLOR
        return {'t': 'color', 'i': r.mtuint()}
    if tag == 16:  # COLOR_DEF
        o = r.u8()
        vals = [r.u16() for _ in range(4 if o & 1 else 3)]
        name = r.stringz() if o & 4 else ''
        eq.color_defs.append((vals, name, bool(o & 1)))
        return {'t': 'state'}
    if tag == 17:  # FONT_DEF
        eq.font_defs.append((r.mtuint(), r.stringz()))
        return {'t': 'state'}
    if tag == 18:  # EQN_PREFS
        r.u8()
        for _ in range(2):
            cnt = r.u8()
            nib = []

            def nibble():
                if not nib:
                    b = r.u8()
                    nib.extend([b >> 4, b & 0xF])
                return nib.pop(0)
            for _ in range(cnt):
                nibble()  # unit
                while nibble() != 0xF:
                    pass
        cnt = r.u8()
        eq.typeface_fonts = {}
        for k in range(cnt):
            fd = r.u8()
            if fd != 0:
                eq.typeface_styles[k + 1] = r.u8()  # bit 0 bold, bit 1 italic
                eq.typeface_fonts[k + 1] = fd   # typeface k+1 uses FONT_DEF fd (1-based)
        return {'t': 'state'}
    if tag == 19:  # ENCODING_DEF
        eq.enc_defs.append(r.stringz())
        return {'t': 'state'}
    if tag >= 100:  # FUTURE / comment: length-prefixed, skip
        ln = r.mtuint()
        r.p += ln
        return {'t': 'state'}
    raise ParseError('unknown record %d' % tag)
