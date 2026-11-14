# SPDX-License-Identifier: AGPL-3.0-only
"""Stage 2 recipes: shape and slide families."""
from drawing import add, p, r, c, transform, arrow, grid, page, slide, plus, cross, check, badge, GLYPHS
from stage2_nouns import lines, pencil, small_pen, lock, bubble, eye, image_frame, book, chart, gear, clock_face, refresh, letter, circle_mark


def shapes_and_slides():
    add('rect',r(3,4,18,16,1),'Rectangle')
    add('ellipse','<ellipse cx="12" cy="12" rx="10" ry="8"/>','Ellipse')
    add('line',p('M3 21 21 3'),'Diagonal line')
    add('linearrowend',p('M3 21 21 3m-8 0h8v8'),'Diagonal line with arrowhead')
    add('lineendstyle',p('M3 5h18m-4-3 4 3-4 3M3 18h18m-18-3 3 3-3 3')+c(21,18,2),'Arrow and circle end styles')
    add('freeline_unfilled',p('M2 19C3 2 10 1 10 12s9 13 12-10'),'Freehand curved stroke')
    add('bezier_unfilled',p('M3 19C3 3 21 21 21 5M3 19 7 3M21 5l-4 16')+r(5,1,4,4)+r(15,19,4,4),'Bezier curve and two handles')
    add('toggleobjectbeziermode',p('M3 21C3 3 21 21 21 3')+r(1,19,4,4)+r(19,1,4,4)+r(10,10,4,4),'Bezier nodes on a curve')
    add('polygon_unfilled',p('M3 21 5 4l9 6 7-7-2 18z'),'Irregular polygon')
    add('starshapes',p('m12 2 3 7 8 1-6 5 2 8-7-4-7 4 2-8-6-5 8-1z'),'Five-point star')
    add('symbolshapes',c(12,12,10)+c(8,9,.7)+c(16,9,.7)+p('M7 15q5 6 10 0'),'Smiling symbol')
    add('symbolshapes.moon',p('M16.5 3A9.5 9.5 0 1 0 21 16.5 9.5 9.5 0 0 1 16.5 3z'),'Crescent theme toggle')
    add('calloutshapes',p('M3 3h18v14H12l-7 5v-5H3z'),'Speech callout shape')
    add('drawcaption',r(7,3,14,11,1)+p('M7 8H3v12h5m-3-3 3 3-3 3'),'Caption with elbow leader')
    add('flowchartshapes.flowchart-document',p('M3 3h18v16c-7-5-11 5-18 0z'),'Flowchart document with waved foot')
    add('connector',r(2,2,6,6)+r(16,16,6,6)+p('M8 5h5v14h3'),'Elbow connector between objects')
    cube=p('m12 2 10 5v10l-10 5-10-5V7zm0 10v10M2 7l10 5 10-5M12 2v10')
    add('cube',cube,'Wireframe cube')
    add('convertinto3d',r(3,8,13,13)+p('M3 8 9 2h13v13l-6 6M16 8l6-6'),'Flat face extruded into depth')
    add('window3d',badge(cube,transform(gear(),'translate(10 10) scale(.55)')),'3D settings')
    add('extrusion3dcolor',cube+circle_mark(),'3D surface colour marker')
    add('extrusiondepthfloater',badge(cube,arrow('right',17,19,10)),'Extrusion depth arrow')
    add('extrusiondirectionfloater',badge(cube,arrow('up',19,18,8)),'Extrusion direction arrow')
    add('extrusionsurfacefloater',cube+p('m14 14 5-3m-5 6 5-3'),'Hatched extrusion surface')
    add('fillshadow',r(3,3,13,13)+p('M8 19h13V8M8 22h14'),'Offset object shadow')
    add('crop',p('M7 2v15h15M2 7h15v15M10 4h10v10'),'Crop corner guides')
    add('contourdialog',image_frame()+p('M5 16Q9 3 19 14'),'Image contour curve')
    add('compressgraphic',image_frame()+p('M1 1l5 5m0-4v4H2M23 23l-5-5m0 4v-4h4'),'Image compression inward corners')
    add('insertgraphic',image_frame(),'Insert image landscape')
    add('graphicdialog',badge(image_frame(),transform(gear(),'translate(10 10) scale(.55)')),'Image properties')
    add('gallery',r(6,2,16,16,1)+p('M2 6v16h16m-9-8 4-5 6 7')+c(10,6,1),'Stacked image gallery')
    add('originalsize',r(6,6,12,12)+p('M2 8V2h6M16 2h6v6M2 16v6h6m8 0h6v-6'),'Restore image bounds')
    add('grafluminance',c(12,12,5)+p('M12 1v3m0 16v3M1 12h3m16 0h3M4 4l2 2m12 12 2 2M4 20l2-2M18 6l2-2'),'Brightness sun')
    add('grafcontrast',c(12,12,9)+p('M12 3v18M15 5v14M18 8v8'),'Half-hatched contrast circle')
    add('grafgamma',p('M3 21h18M3 3v18M5 18C18 18 5 6 21 4'),'Gamma response curve')
    add('graftransparence',r(3,3,13,13)+r(10,10,11,11)+p('M10 13h3v-3'),'Transparent overlapping squares')
    add('outputqualitygrayscale',r(3,3,18,18)+p('M8 3v18M13 3v18M17 3v18'),'Monochrome density swatches')
    add('autopilotmenu',p('m3 18 12-12 5 5L8 23zM5 2v6m-3-3h6M18 2v3m-1.5-1.5h3M20 17v5m-2.5-2.5h5'),'Wizard wand and sparkles')
    # Boolean operations draw the resulting boundaries, not identical stacked boxes.
    for name,body in [
        ('combine',r(3,3,12,12)+r(9,9,12,12)),
        ('merge',p('M3 3h12v6h6v12H9v-6H3z')),
        ('intersect',r(9,9,6,6)+p('M3 12V3h9M12 21h9v-9')),
        ('substract',p('M3 3h12v6H9v6H3zM18 9h3v12H9v-3')),
        ('dismantle',r(2,2,8,8)+r(14,14,8,8)+p('M8 16H3v5m13-13h5V3'))]:
        add(name,body,'Boolean shapes: '+name)
    for name,front in [('bringtofront',True),('sendtoback',False),('objectforwardone',True),('objectbackone',False)]:
        body=r(3,3,12,12)+p('M15 9h6v12H9v-6') if front else r(9,9,12,12)+p('M9 15H3V3h12v6')
        body+=(p('M2 20h5m-2.5-2.5v5') if front else p('M2 20h5')) if name in ('objectforwardone','objectbackone') else p('M2 21h5M2 18h5')
        add(name,body,'Stack order: '+name)
    add('formatgroup',r(2,2,20,20)+r(5,5,7,7)+r(12,12,7,7),'Group two shapes inside one boundary')
    add('formatungroup',p('M2 7V2h5m10 0h5v5M2 17v5h5m10 0h5v-5')+r(5,5,7,7)+r(12,12,7,7),'Ungroup with broken boundary')
    for name,direction in [('entergroup','right'),('leavegroup','left')]:
        add(name,r(8,3,14,18)+r(12,6,7,5)+r(12,14,7,4)+arrow(direction,6,12,10),'Group navigation '+direction)
    add('selectobject',p('M5 2v19l5-6 4 7 4-2-4-7h8z'),'Selection cursor')
    add('mirror',p('M12 2v3m0 3v3m0 3v3m0 3v2M3 19V5l6 14zm18 0V5l-6 14z'),'Horizontal mirror across vertical guide')
    add('mirrorvert',transform(GLYPHS['mirror'][0],'rotate(90 12 12)'),'Vertical mirror across horizontal guide')
    add('rotateright',r(5,10,10,10)+p('M4 6a9 9 0 0 1 16 5m-4-3 4 3 1-5'),'Rotate object clockwise')
    add('shear',p('M8 4h13l-5 16H3zM2 3h18m-3-2 3 2-3 2'),'Shear parallelogram')
    add('crookslant',p('M3 20Q4 3 18 3l3 5Q9 8 8 21z'),'Bent shape strip')
    add('transformdialog',r(5,5,14,14)+r(2,2,5,5)+r(17,17,5,5)+p('M19 4h3v8M4 19v3h8'),'Transform bounding box handles')
    add('objectalignright',p('M21 2v20')+r(4,4,14,6,1)+r(9,14,9,6,1),'Objects against right guide')
    for name,direction in [('aligncenter','vertical'),('alignmiddle','horizontal'),('alignup','top'),('aligndown','bottom')]:
        body=r(5,5,6,8)+r(14,5,5,14)+p('M2 2h20') if direction=='top' else r(5,11,6,8)+r(14,5,5,14)+p('M2 22h20') if direction=='bottom' else r(3,5,8,14)+r(14,8,7,8)+p('M1 12h1m10 0h1m9 0h1') if direction=='horizontal' else r(4,4,16,6)+r(8,14,8,6)+p('M12 1v2m0 8v2m0 8v2')
        add(name,body,'Object alignment '+direction)
    add('distributeselection',p('M2 3v18M22 3v18')+r(5,7,4,10)+r(11,5,4,14)+r(17,7,3,10),'Even object distribution')
    # Text-wrap layouts keep the object square fixed; line placement is semantic.
    wrap_lines={
        'wrapoff':'M2 3h20M2 21h20',
        'wrapon':'M2 3h20M2 9h3m14 0h3M2 15h3m14 0h3M2 21h20',
        'wrapideal':'M2 3h20M2 9h3m14 0h3M19 15h3M2 21h20',
        'wrapleft':'M2 3h20M2 9h3M2 15h3M2 21h20',
        'wrapright':'M2 3h20M19 9h3M19 15h3M2 21h20',
        'wrapthrough':'M2 3h20M2 9h20M2 15h20M2 21h20',
        'textwrap':'M2 3h20M2 9h3m14 0h3M2 15h3m14 0h3M2 21h12',
    }
    for name,lines_ in wrap_lines.items():
        add(name,r(8,7,8,10)+p(lines_)+(small_pen() if name=='textwrap' else ''),'Text wrapping: '+name)
    add('toggleanchortype',c(12,5,3)+p('M12 8v14M5 11h14M3 15q0 7 9 7t9-7m-18 0-1 4m1-4 4 1m14-1 1 4m-1-4-4 1'),'Object anchor')
    add('chainframes',r(2,3,8,18)+r(14,3,8,18)+p('M7 12h10m-3-3 3 3-3 3'),'Linked text frames')
    add('unhainframes',r(2,3,8,18)+r(14,3,8,18)+p('m9 9 6 6m0-6-6 6'),'Unlink text frames')
    add('framedialog',r(3,3,18,18)+p('M1 6h4M1 18h4M19 6h4M19 18h4M8 8h8M8 12h8M8 16h5'),'Frame borders and text')
    add('insertdraw',badge(pencil(),plus()),'Insert drawing')
    add('insertobject',badge(r(3,3,15,15)+r(6,6,9,9),plus()),'Insert embedded object')
    add('inserthyperlink',p('M9 8H6a4 4 0 0 0 0 8h3m6-8h3a4 4 0 0 1 0 8h-3M8 12h8'),'Two chain links')
    # Slides, masters, view layouts and slideshow actions.
    for name,mark in [
        ('insertmasterpage',plus()),('deletemasterpage',cross()),('renamemasterpage',small_pen()),
        ('closemasterview',cross()+p('M2 21h7')),('renameslide',small_pen()),
        ('importslidefromfile',arrow('down',18,18,8)),('showslide',transform(eye(),'translate(10 10) scale(.55)')),
        ('hideslide',p('M3 21 21 3')),('presentationdialog',transform(gear(),'translate(10 10) scale(.55)')),
        ('slidesetup',p('M14 14h8m-8 4h8m-8 4h8M17 12v4M20 16v4')),
        ('presentationminimizer',p('M13 22l4-4m-4 0h4v4M22 13l-4 4m0-4v4h4'))]:
        base=slide()+p('M6 8h12')
        if 'master' in name:base+=p('m9 12 3-2 3 2-1 3h-4z')
        if name=='importslidefromfile':base=page()+p('M8 11h8v6H8z')
        add(name,badge(base,mark),'Slide action: '+name)
    add('slidemasterpage',slide()+p('m7 9 2 6h6l2-6-3 2-2-4-2 4z'),'Master slide crown')
    add('masterlayouts',slide()+p('M6 8h12M6 12h4v3H6zm8 0h4v3h-4M2 21h20'),'Master slide layout and baseline')
    add('assignlayout',slide()+p('M6 8h12M6 12h6v3H6zm9 0h3v3h-3'),'Assign asymmetric slide layout')
    add('displaymasterbackground',slide()+p('m3 16 8-10 10 10M3 21h18'),'Master background mountain and base')
    add('displaymasterobjects',slide()+r(6,8,5,6)+c(16,11,3),'Master objects on slide')
    add('notesmasterpage',slide()+p('M6 9h12M6 13h6M3 21h18'),'Notes master ruled footer')
    add('notesmode',r(5,2,14,20)+r(7,4,10,7)+p('M8 15h8M8 18h6'),'Slide notes page')
    add('handoutmode',r(3,2,18,20)+r(6,5,5,5)+r(14,5,4,5)+r(6,13,5,5)+r(14,13,4,5),'Four slides on handout page')
    add('diamode',r(2,3,8,7)+r(14,3,8,7)+r(2,14,8,7)+r(14,14,8,7),'Slide sorter four tiles')
    add('normalviewmode',slide()+p('M6 8h12M6 12h8'),'Single slide normal view')
    add('normalmultipanegui',r(2,3,20,18)+p('M7 3v18M7 17h15M3 7h2m-2 5h2M10 7h9'),'Normal multi-pane slide workspace')
    add('leftpaneimpress',r(2,3,20,18)+p('M8 3v18')+r(4,6,2,4)+r(4,14,2,4),'Slide navigation pane')
    add('presentationcurrentslide',slide()+p('m9 7 7 4-7 4zM3 21h6'),'Play current slide with position marker')
    add('customshowdialog',badge(slide(),p('M14 14h8M14 18h6M14 22h8')),'Custom slideshow ordered list')
    add('rehearsetimings',badge(slide(),transform(clock_face(),'translate(10 10) scale(.55)')),'Rehearse slide timings stopwatch')
    add('avmediaplayer',r(2,3,20,18,1)+p('M2 7h20M2 17h20M7 3v4M17 3v4M7 17v4M17 17v4m-7-8 5 3-5 3z'),'Film strip with play triangle')
    add('animationeffects',p('m3 16 6-3 4 5 8-14m-5 0h5v5')+c(4,6,2),'Animation motion path')
    add('diaeffect',badge(slide(),p('m14 22 3-7h-4l7-4-2 7h4z')),'Slide object animation lightning')
    add('slidechangewindow',p('M2 4h8v14H2zM14 7h8v14h-8zM8 12h8m-3-3 3 3-3 3'),'Slide transition between two frames')
    add('savebackground',badge(image_frame(),r(14,13,9,9)+p('M16 13v4h5v-4M16 22v-3h5v3')),'Save slide background')
    add('selectbackground',badge(image_frame(),p('m13 13 9 4-4 2-1 4z')),'Select slide background')
    for name,direction in [('upsearch','up'),('downsearch','down')]:
        add(name,badge(slide(),arrow(direction,19,18,8)),'Move slide '+direction)
