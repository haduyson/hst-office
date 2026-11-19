# SPDX-License-Identifier: AGPL-3.0-only
"""Fonts of MTEF characters and TCVN3/VNI decoding."""
from mtef5_tables import *  # noqa: F401,F403  (shared tables)


class FontMixin:
    def font_of(self, tf):
        """Explicit font name for a negative typeface (FONT_STYLE_DEF index) or None."""
        if tf >= 0:
            fd = self.eq.typeface_fonts.get(tf, 0) - 1
            return self.eq.font_defs[fd][1] if 0 <= fd < len(self.eq.font_defs) else None
        i = -tf - 1
        if 0 <= i < len(self.eq.font_style_defs):
            fd = self.eq.font_style_defs[i][0] - 1
            if 0 <= fd < len(self.eq.font_defs):
                return self.eq.font_defs[fd][1]
        return '?'

    def char_text(self, c):
        """Unicode text of a CHAR record, decoding legacy Vietnamese fonts."""
        eq = self.eq
        font = self.font_of(c['tf'])
        if font and font != '?':
            low = font.lower()
            if False:
                eq.constructs.add('legacyfont')
                enc = legacy_maps()['tcvn3' if low.startswith('.vn') else 'vni']
                b = c['fp'] if c['fp'] is not None else c['mt']
                if b is not None and b < 256:
                    hx = '%02X' % b
                    if enc['kind'] == 'byte' and hx in enc['map']:
                        return enc['map'][hx]
                    if enc['kind'] == 'sequence' and hx in enc['map']:
                        return enc['map'][hx]
                    return chr(b)
            elif not any(low.startswith(k) for k in ('times', 'symbol', 'mt extra', 'euclid', 'courier', 'arial',
                                                     'cambria', 'calibri')):
                eq.constructs.add('fonts')
        if c['mt'] is None:
            eq.issue('no-mtcode-char', 'fail')
            return None
        return chr(c['mt'])

    def legacy_encoding(self, c):
        font = self.font_of(c['tf'])
        if font and font != '?':
            low = font.lower()
            if low.startswith('.vn'):
                return 'tcvn3'
            if low.startswith('vni'):
                return 'vni'
        return None

    def decode_chars(self, chars):
        """Unicode text of consecutive CHAR records; TCVN3/VNI font runs are decoded from their bytes."""
        out, i = [], 0
        while i < len(chars):
            enc = self.legacy_encoding(chars[i])
            if not enc:
                ch = self.char_text(chars[i])
                if ch is None:
                    return None
                out.append(ch)
                i += 1
                continue
            j, raw = i, []
            while j < len(chars) and self.legacy_encoding(chars[j]) == enc:
                c = chars[j]
                if c['fp'] is not None and c['fp'] < 256:
                    raw.append(c['fp'])
                else:
                    try:
                        raw.append(chr(c['mt']).encode('cp1252')[0])
                    except (UnicodeEncodeError, TypeError, ValueError):
                        raw.append(None)
                j += 1
            m = legacy_maps()[enc]['map']
            if any(b is not None and b >= 0x80 for b in raw):
                self.eq.constructs.add('legacyfont')
            k = 0
            while k < len(raw):
                b = raw[k]
                if b is None:
                    out.append(self.char_text(chars[i + k]) or '')
                    k += 1
                    continue
                if k + 1 < len(raw) and raw[k + 1] is not None and '%02X%02X' % (b, raw[k + 1]) in m:
                    out.append(m['%02X%02X' % (b, raw[k + 1])])
                    k += 2
                    continue
                out.append(m.get('%02X' % b, bytes([b]).decode('cp1252', 'replace')))
                k += 1
            i = j
        return ''.join(out)
