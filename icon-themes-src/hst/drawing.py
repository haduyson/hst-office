#!/usr/bin/env python3
# SPDX-License-Identifier: AGPL-3.0-only
"""HST's original geometric construction desk. No imported icon artwork.

Writes editable SVG masters; generate.py exports those masters, independently.
Artwork emitted by this script is CC-BY-4.0; script is AGPL-3.0-only.
"""
from pathlib import Path
import argparse
import json

ROOT = Path(__file__).resolve().parent
GLYPHS = {}


def p(d, **attrs):
    return '<path d="' + d + '"' + ''.join(f' {k.replace("_", "-")}="{v}"' for k, v in attrs.items()) + '/>'


def r(x, y, w, h, radius=0):
    return f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="{radius}"/>'


def c(x, y, radius):
    return f'<circle cx="{x}" cy="{y}" r="{radius}"/>'


def transform(body, value):
    # Compensate uniform construction scaling so small badges keep the same pen.
    import re
    match = re.search(r'scale\((\.?[0-9.]+)\)', value)
    pen = f' stroke-width="{1.65/float(match[1]):.6g}"' if match else ''
    return f'<g transform="{value}"{pen}>{body}</g>'


def add(name, body, concept):
    assert name not in GLYPHS, name
    GLYPHS[name] = (body, concept)


def arrow(direction, x=12, y=12, length=14):
    a = p(f'M{x-length/2} {y}h{length}m-4-4 4 4-4 4')
    return transform(a, f'rotate({dict(right=0, down=90, left=180, up=270)[direction]} {x} {y})')


def grid():
    return r(3, 3, 18, 18, 1) + p('M3 9h18M3 15h18M9 3v18M15 3v18')


def page():
    return p('M5 2.5h9l5 5v14H5zM14 2.5V8h5')


def slide():
    return r(2.5, 4, 19, 14, 1.5)


def plus(x=18, y=18):
    return p(f'M{x-3} {y}h6m-3-3v6')


def cross(x=18, y=18):
    return p(f'm{x-2.5} {y-2.5} 5 5m0-5-5 5')


def check(x=17, y=18):
    return p(f'm{x-4} {y} 3 3 6-7')


def badge(body, mark):
    # Top-left base and open lower-right quadrant keep signs legible at 16 px.
    return transform(body, 'translate(0 0) scale(.75)') + mark


def stage1():
    # HST mockup language: open rounded contours, short terminals, 1.65-unit stroke.
    add('paste', p('M8 5H5v16h14V5h-3') + r(8, 2.5, 8, 5, 1.5) + p('M8 12h8m-8 4h6'), 'Clipboard with clipped paper')
    add('cut', c(6, 17.5, 3) + c(18, 17.5, 3) + p('m8 15 10-12M16 15 6 3'), 'Scissors, two separated finger loops')
    add('copy', r(8, 7, 12, 14, 1.5) + p('M5 17H3V3h12v1M11 11h6m-6 4h5'), 'Two overlapping sheets')
    # Original splayed brush: golden head, short rounded handle, one bristle split; 45-degree edges stay crisp at 16 px.
    add('formatpaintbrush', p('M8.5 10 15 16.5 10.5 21.5 2.5 14.5Z', fill='#E2B741')
                           + p('M8.5 10 11 7.5Q11.5 7 12.5 7.5L14.5 8.5 19 4C20.5 2.5 23 5 21.5 6.5L17 11 18 13Q18.5 14 17.5 14.5L15 16.5M11 7.5 17.5 14.5M6.5 18 8.5 15.5'),
                           'Diagonal splayed paintbrush with short rounded handle and golden bristles')
    add('resetattributes', p('m3 15 9-11 8 6-9 11H8zm4 3 9-11M14 21h7'), 'Eraser and cleared baseline')
    add('clearcontents', r(3, 3, 18, 18, 1) + p('M3 9h18M9 3v18m4-8 5 5m0-5-5 5'), 'Cell grid with clear cross')
    add('bold', p('M7 3v18h6c7 0 7-9 0-9H7h5c6 0 6-9 0-9H7', stroke_width=2.4), 'Hand-drawn bold B')
    add('italic', p('M10 3h9M5 21h9M15 3 9 21'), 'Slanted I with terminals')
    add('underline', p('M6 3v9a6 6 0 0 0 12 0V3M5 21h14'), 'U above underline')
    add('strikeout', p('M18 5C14 1 5 3 8 8c2 3 8 2 9 6 2 7-8 8-11 4M3 12h18'), 'S crossed by horizontal strike')
    add('subscript', p('m3 5 9 11M12 5 3 16m13 0c0-4 5-4 5-1 0 2-5 3-5 6h5'), 'x and lowered 2')
    add('superscript', p('m3 9 9 11M12 9 3 20m13-16c0-4 5-4 5-1 0 2-5 3-5 6h5'), 'x and raised 2')
    add('spacing', p('m3 14 4-10 4 10M4.5 11h5M13 4l3.5 10L20 4M3 20h18m-3-2 3 2-3 2M6 18l-3 2 3 2'), 'AV with width arrows')
    add('backcolor', p('m7 14 9-11 5 4-9 11zm-1 2 6 4H4z') + '<path data-state="highlight" d="M3 22h18" stroke="#E2B741" stroke-width="2.5"/>', 'Highlighter nib and selected-colour bar')
    add('color', p('m5 17 7-14 7 14M8 12h8') + '<path data-state="font-color" d="M4 22h16" stroke="#B65A62" stroke-width="2.5"/>', 'A and selected-font-colour bar')
    add('grow', p('m3 20 6-14 6 14M6 14h6M18 8V2m-3 3h6'), 'A with plus')
    add('shrink', p('m3 20 6-14 6 14M6 14h6M15 4h6'), 'A with minus')
    add('defaultbullet', c(3.5, 5, .9)+c(3.5,12,.9)+c(3.5,19,.9)+p('M8 5h13M8 12h13M8 19h13'), 'Three bullets and text lines')
    add('defaultnumbering', p('m2 3 2-1v6M2 8h4M2 16c0-4 5-4 5-1 0 2-5 3-5 6h5M11 5h10m-10 7h10m-10 7h10'), 'Hand-drawn 1 and 2 beside list lines')
    add('setoutline', r(2,3,3,3)+r(6,10,3,3)+r(10,17,3,3)+p('M10 4.5h11m-7 7h7m-3 7h3'), 'Stepped outline levels')
    for name, xs in [('alignleft',[3,3,3,3]),('alignhorizontalcenter',[3,6,3,6]),('alignright',[3,9,3,9]),('alignblock',[3,3,3,3])]:
        add(name, ''.join(p(f'M{x} {4+5*i}h{18 if i%2==0 or name=="alignblock" else 12}') for i,x in enumerate(xs)), 'Paragraph '+name)
    for name, y in [('aligntop',3),('alignverticalcenter',12),('alignbottom',21)]:
        yy=6 if y==3 else 3 if y==21 else 5
        hh=15 if y==3 else 15 if y==21 else 14
        body=p(f'M3 {y}h18') if y!=12 else p('M2 12h2M11 12h2M20 12h2')
        body+=r(6, yy, 4, hh)+r(14, yy if y==3 else yy+6 if y==21 else yy+3,4,hh-6)
        add(name,body,'Two objects aligned to '+name)
    for name, direction in [('incrementindent','right'),('decrementindent','left')]:
        add(name,p('M3 4h18M11 9h10M11 14h10M3 20h18')+transform(arrow(direction,5,12,6),'translate(0 0)'), 'Text indent '+direction)
    add('hangingindent',p('M3 4h18M10 9h11M10 14h11M10 19h11m-7-7h4m-2-2 2 2-2 2'), 'Full first line, indented following lines')
    pilcrow=p('M13 13H9A5 5 0 0 1 9 3h11M13 3v18m5-18v18')
    add('controlcodes',pilcrow,'Paragraph mark')
    for name, direction in [('paralefttoright','right'),('pararighttoleft','left')]:
        add(name,transform(pilcrow,'translate(4 0) scale(.8 1)')+arrow(direction,6,18,8), 'Paragraph direction '+direction)
    add('spacepara15',p('M12 5h10M12 12h10M12 19h10M5 3v18m-3-3 3 3 3-3M2 6l3-3 3 3'), 'Line spacing with vertical arrows')
    for name, inward in [('paraspaceincrease',False),('paraspacedecrease',True)]:
        add(name,p('M10 3h11M10 7h8M10 17h11M10 21h8')+arrow('down' if inward else 'up',5,6,6)+arrow('up' if inward else 'down',5,18,6),'Paragraph gap '+('decrease' if inward else 'increase'))
    add('backgroundcolor',p('m3 12 9-9 8 8-9 9zm1 0h15M9 2l5 5m6 8s-4 4-2 6c3 3 6-1 2-6'),'Fill bucket with droplet')
    add('searchdialog', c(8,8,5)+p('m12 12 4 4M4 20h17m-3-3 3 3-3 3'),'Find and replace arrow')
    # Tìm tính năng and the sidebar's Tìm deck share this key. A shell prompt read as a terminal or macro
    # console; a magnifier over menu lines searches commands and stays apart from Tìm và thay thế (magnifier + arrow).
    add('recsearch',p('M3 4.5h11M3 9.5h7M3 14.5h5')+c(15.5,13.5,4.5)+p('m18.8 16.8 3.7 3.7'),
        'Magnifier over menu lines: find a feature')
    add('insertdoc',page()+p('M8 12h8m-8 4h6'),'Administrative document')
    add('menubar',r(3,4,18,16,2)+p('M3 9h18M7 6.5h1m3 0h1m3 0h1'),'Window with menu strip')
    add('open',p('M3 8V3h7l3 4h7v3M3 10h19l-4 11H3z'),'Open folder')
    add('save',p('M3 3h14l4 4v14H3zM7 3v6h9V3M7 21v-8h10v8M13 4v3'),'Floppy disk save')
    add('undo',p('M3 10h9c7 0 9 10 1 11M3 10l6-6m-6 6 6 6'),'Return arrow to left')
    add('redo',p('M21 10h-9c-7 0-9 10-1 11m10-11-6-6m6 6-6 6'),'Return arrow to right')
    add('print',p('M7 9V2h10v7M6 18H3V9h18v9h-3M7 15h10v7H7zm10-3h1'),'Printer with paper')
    add('arrowshapes',p('M3 8h10V3l9 9-9 9v-5H3z'),'Outlined block arrow')
    add('graphic',r(3,3,11,11,1)+c(16,16,5),'Rectangle and circle shape family')
    add('autoformat',r(3,3,12,15,1)+p('M3 8h12M3 13h8M8 3v15m5 3 8-10m-4 0 4 3'), 'Table formatting wand beside grid')
    add('conditionalformatdialog',r(3,3,18,18,1)+p('M3 9h18M9 3v18m3-4 3 3 5-6'),'Grid with condition check')
    add('autosum',p('M20 3H5l8 9-8 9h15'),'Summation sigma')
    add('datafilterautofilter',p('M3 3h18l-7 9v8l-4 2V12z'),'Funnel')
    add('setborderstyle',r(3,3,18,18)+p('M3 12h18M12 3v18'),'Four border cells')
    for name, axis in [('entirecolumn','col'),('entirerow','row')]:
        body=r(3,3,18,18,1)
        body+=r(9,3,6,18)+p('M3 9h6m6 0h6M3 15h6m6 0h6') if axis=='col' else r(3,9,18,6)+p('M9 3v6m0 6v6M15 3v6m0 6v6')
        add(name,body,'Whole '+axis+' selection')
    for name, col, remove in [('insertcolumnsbefore',True,False),('insertrowsbefore',False,False),('deletecolumns',True,True),('deleterows',False,True)]:
        body=r(3,3,18,12,1)+p('M9 3v12M15 3v12') if col else r(3,3,12,18,1)+p('M3 9h12M3 15h12')
        body+=p('M9 20h6') if col and remove else plus(12,20) if col else p('M18 12h4') if remove else plus(20,12)
        add(name,body,('Remove' if remove else 'Insert before')+(' column' if col else ' row'))
    add('filldown',r(3,3,18,18,1)+p('M3 8h18M12 10v9m-3-3 3 3 3-3'),'Cells filled downward')
    add('togglemergecells',r(2.5,4,19,16,1)+p('M12 4v3m0 10v3M5 12h5m-2-2 2 2-2 2m11-2h-5m2-2-2 2 2 2'),'Two cells with inward arrows')
    add('wraptext',p('M3 4h18M3 9h15a4 4 0 0 1 0 8h-5m3-3-3 3 3 3M3 14h5m-5 5h5'),'Text line wrapping back')
    add('insert',page()+plus(12,15),'Insert sheet')
    add('name',r(3,4,18,16,1)+p('M7 8h10M12 8v8m-3 0h6'),'Sheet with name caret')
    add('numberformatcurrency',p('M17 6c-3-4-10-2-10 2 0 5 10 2 10 7 0 5-8 6-11 2M12 2v20'),'Currency symbol')
    add('numberformatpercent',c(6,6,3)+c(18,18,3)+p('M4 21 20 3'),'Percent')
    add('numberformatdecimal',r(3,5,6,14,3)+c(13,18,.7)+r(17,5,4,14,2),'Decimal number 0.0')
    for name, d in [('numberformatdecdecimals','left'),('numberformatincdecimals','right')]:
        add(name,c(4,10,.7)+r(8,3,5,9,2.5)+(r(17,3,5,9,2.5) if d=='right' else '')+arrow(d,12,19,16),'Decimal places '+('increase' if d=='right' else 'decrease'))
    add('sortascending',p('M3 5h4m-4 6h8m-8 6h11M19 3v18m-3-3 3 3 3-3'),'Ascending length bars and down arrow')
    add('objectalignleft',p('M3 2v20')+r(6,4,14,6,1)+r(6,14,9,6,1),'Objects against left guide')
    add('objectposition',r(8,8,8,8,1)+p('M12 2v4m-2-2 2-2 2 2M12 18v4m-2-2 2 2 2-2M2 12h4m-2-2-2 2 2 2M18 12h4m-2-2 2 2-2 2'),'Object with four position arrows')
    add('toggleobjectrotatemode',r(7,7,10,10,1)+p('M3 12a9 9 0 0 1 16-6m-4 0h4V2M21 12A9 9 0 0 1 5 18m4 0H5v4'),'Object with rotation arrows')
    add('shadowed',p('m3 18 7-15 7 15M6 13h8M13 3l8 17H8'),'A with offset shadow edge')
    add('insertslide',badge(slide()+p('M6 8h12'),plus()),'Slide with plus')
    add('duplicateslide',r(7,8,15,12,1)+p('M4 16H2V3h16v2M10 12h9'),'Two slides')
    add('presentationlayout',slide()+p('M6 8h12M6 12h5v3H6zm8 0h4v3h-4'),'Slide title and two content panes')
    add('presentation',slide()+p('M12 18v4m-5 0h10m-7-15 6 4-6 4z'),'Presentation screen with play')
    from drawing_extension_tab import hst_commands
    hst_commands()


if __name__ == '__main__':
    import sys
    sys.modules['drawing'] = sys.modules[__name__]
    parser=argparse.ArgumentParser()
    parser.add_argument('--stage', type=int, choices=[1,2], required=True)
    args=parser.parse_args()
    stage1()
    if args.stage == 2:
        review = json.loads((ROOT/'metadata/stage-1-review.json').read_text())
        assert review['complete'] and review['source_glyphs'] == 78
        from stage2 import stage2
        stage2()
    from drawing_masters import write
    write(args.stage)
