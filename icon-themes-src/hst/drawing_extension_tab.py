# SPDX-License-Identifier: AGPL-3.0-only
"""Glyphs of the Extensions tab buttons: the org.hst.office.vi: commands of the bundled HST extension.

Same construction desk and pen as Stage 1 (drawing.py). Artwork is CC-BY-4.0; script is AGPL-3.0-only.
"""
from drawing import add, p, r, c


def hst_commands():
    # Large 32 px buttons; the contours stay open and few, so they also read at 16 px.
    add('convertencoding', p('m2 21 4-11 4 11M3.3 17.5h5.4M14 21l4-11 4 11M15.3 17.5h5.4M16 7l2-2 2 2M3 4.5h7m-2.5-2.5 2.5 2.5-2.5 2.5'),
        'Plain A converted to A with circumflex: legacy Vietnamese text to Unicode')
    add('numbertowords', p('M3 4.5 5 3v7M8 5c0-2.6 4-2.6 4 0 0 1.8-4 3-4 5h4M14.5 6.5h6.5m-2.5-2.5 2.5 2.5-2.5 2.5M3 14h18M3 17.5h18M3 21h11'),
        'Digits 1 2 turned into lines of words')
    add('formatdate', r(3, 5, 18, 16, 2)+p('M3 10h18M8 3v4M16 3v4M7 14h1.5m2.75 0h1.5m2.75 0h1.5M7 17.5h1.5m2.75 0h1.5'),
        'Calendar page with day cells')
    add('formatvnd', c(9.5, 14, 4.5)+p('M14 4v14.5M11.5 6.5h5M5 21.5h13'),
        'Dong sign: d with a bar, on its base line')
    add('importcsv', r(8, 3, 13, 18, 1.5)+p('M8 9h13M8 15h13M14.5 3v18M2 12h8.5m-3-3 3 3-3 3'),
        'Arrow bringing rows into a sheet')
    add('removediacritics', p('m2 21 5-14 5 14M4 16h6M6 4.5l2.5-2.5M15 4l5 5m0-5-5 5'),
        'A whose tone mark is crossed off')
    add('splitname', r(3, 3, 18, 6, 1)+r(3, 15, 8, 6, 1)+r(13, 15, 8, 6, 1)+p('M12 9v2.5M7 15v-2.5h10V15'),
        'One cell forking into two cells')
    add('sortbygivenname', c(7, 7, 3)+p('M2 20c0-4.5 2.2-7 5-7s5 2.5 5 7M18 3v18m-3-3 3 3 3-3'),
        'Person beside a downward sort arrow')
    add('deleteblankrows', r(3, 3, 13, 18, 1)+p('M3 9h13M3 15h13M6 6h7M6 18h7M18.5 12h4'),
        'Table whose empty middle row is removed')
    add('showsolutions', p('M12 3 2.5 20.5h19ZM9 13h6M6.8 17h10.4'),
        'Triangular HASON TECH mark with two bars')
