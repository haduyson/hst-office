# SPDX-License-Identifier: AGPL-3.0-only
"""Glyphs of the Extensions tab buttons: the org.hst.office.vi: commands of the bundled HST extension.

Same construction desk and pen as Stage 1 (drawing.py). Artwork is CC-BY-4.0; script is AGPL-3.0-only.
"""
from drawing import add, p, r, c

ACCENT = '#2F7DD1'  # HST blue, the same in the light and dark theme


def hst_commands():
    # Large 32 px buttons; the contours stay open and few, so they also read at 16 px.
    # Owner's choice (2026-11-06): legacy bytes (grey boxes) become Vietnamese letters (HST blue) on the same line.
    add('convertencoding', p('M2.5 4.5h4v5h-4zM9 4.5h4v5H9z', stroke_opacity='.5') + p('M17.5 3.5v7m-2.5-2.5 2.5 2.5 2.5-2.5')
        + '<g stroke="' + ACCENT + '">' + p('M4.5 17.5a2.5 2.5 0 1 0 5 0 2.5 2.5 0 1 0-5 0M9 15.2c.9 0 1.5-.6 1.5-1.4'
                                            'M14 17.5h5a2.5 2.5 0 1 0-.8 1.9M14.8 13.2l1.7-1.7 1.7 1.7') + '</g>'
        + p('M2.5 22h19'),
        'Legacy byte boxes (grey) turned into the Vietnamese letters o-horn and e-circumflex (blue) on a text line')
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
    # Giải pháp HASON TECH (showsolutions) is not drawn here: it shows the HASON TECH trademark
    # (branding/icon-themes/hasontech-mark.svg, the "trademark" master in families.json), outside CC BY.
