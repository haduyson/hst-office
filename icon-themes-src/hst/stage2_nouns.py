# SPDX-License-Identifier: AGPL-3.0-only
"""Shared visual nouns of the stage 2 ribbon icon recipes."""
from drawing import add, p, r, c, transform, arrow, grid, page, slide, plus, cross, check, badge, GLYPHS



def lines():
    return p('M8 8h8M8 12h8M8 16h5')


def pencil():
    return p('m4 16 12-13 5 5L8 21H3zm9-10 5 5M4 16l4 5')


def small_pen():
    return p('m13 19 7-7 3 3-7 7h-3z')


def lock():
    return r(5,10,14,11,2)+p('M8 10V6a4 4 0 0 1 8 0v4M12 15v2')


def bubble():
    return p('M3 3h18v14H10l-7 5zM7 7h10M7 11h7')


def eye():
    return p('M2 12Q12-2 22 12Q12 26 2 12z')+c(12,12,3)


def image_frame():
    return r(3,3,18,18,1.5)+c(8,8,1.5)+p('m3 18 5-5 4 4 4-7 5 7')


def book():
    return p('M12 5C8 2 4 2 2 3v17c4-2 7-1 10 1 3-2 6-3 10-1V3c-4-1-7-1-10 2zm0 0v16')


def chart():
    return p('M3 3v18h18M7 17v-6m5 6V7m5 10V3')


def gear():
    return p('m9 2 6 0 1 4 4 1 2 5-3 3v4l-5 3-3-3H6l-3-5 2-3-1-5 5-1z')+c(12,12,3)


def clock_face():
    return c(12,12,9)+p('M12 6v6l4 3')


def refresh():
    return p('M3 10A9 9 0 0 1 19 6m-4 0h4V2M21 14A9 9 0 0 1 5 18m4 0H5v4')


def letter(letter, x=4, y=4, scale=1):
    # Original single-stroke mathematical/field symbols, not font outlines.
    paths={
        'A':'M0 12 4 0 8 12M2 8h4', 'B':'M0 0v12h4c5 0 5-6 0-6H0h4c4 0 4-6 0-6z',
        'C':'M8 2C-2-6-2 18 8 10', 'F':'M0 12V0h8M0 5h6', 'I':'M0 0h6M3 0v12M0 12h6',
        'N':'M0 12V0l8 12V0', 'P':'M0 12V0h4c6 0 6 6 0 6H0',
        'T':'M0 0h8M4 0v12', 'Z':'M0 0h8L0 12h8', 't':'M4 0v10q0 3 4 1M0 4h8',
        'x':'M0 3 8 12M8 3 0 12', 'f':'M8 0Q3-2 3 3v9q0 3-3 1M0 5h7',
        '0':'M4 0C-1 0-1 12 4 12S9 0 4 0z', '1':'M1 3 4 0v12M1 12h6',
        '2':'M0 3C0-2 8-1 8 3c0 3-8 5-8 9h8', '3':'M0 0h8L3 6q9-1 5 5-5 3-8-1',
        '7':'M0 0h8L2 12', '#':'M3 0 1 12M8 0 6 12M0 4h10M0 8h10',
        '?':'M0 3c0-5 8-4 8 0 0 3-4 3-4 6m0 3v.1',
    }
    return transform(p(paths[letter]),f'translate({x} {y}) scale({scale})')


def circle_mark():
    return c(17,16,1.5)
