# SPDX-License-Identifier: AGPL-3.0-only
"""Stage 2 recipes: document and text families."""
from drawing import add, p, r, c, transform, arrow, grid, page, slide, plus, cross, check, badge, GLYPHS
from stage2_nouns import lines, pencil, small_pen, lock, bubble, eye, image_frame, book, chart, gear, clock_face, refresh, letter, circle_mark


def documents():
    # Review actions retain the document outline and distinguish accept/reject,
    # all changes (stack), and advance (right arrow) without relying on colour.
    for name,mark,stack in [
        ('accepttrackedchange',check(),False),('acceptalltrackedchanges',check(),True),
        ('rejecttrackedchange',cross(),False),('rejectalltrackedchanges',cross(),True),
        ('accepttrackedchangetonext',check(10,18)+arrow('right',19,19,6),False),
        ('rejecttrackedchangetonext',cross(10,18)+arrow('right',19,19,6),False),
        ('accepttrackedchanges',check()+p('M4 18h4M4 22h8'),False)]:
        body=page()+p('M8 8h8M8 12h6')
        if stack:body=p('M2 6v17h12')+body
        add(name,badge(body,mark),'Review document: '+name)
    for name,mark in [
        ('nexttrackedchange',arrow('right',17,19,8)),('previoustrackedchange',arrow('left',17,19,8)),
        ('trackchanges',small_pen()),('showtrackedchanges',transform(eye(),'translate(11 12) scale(.5)')),
        ('protecttracechangemode',transform(lock(),'translate(10 10) scale(.55)'))]:
        add(name,badge(page()+p('M8 8h8M8 12h8M3 7v7'),mark),'Tracked changes: '+name)
    for name,mark in [
        ('editannotation',small_pen()),('deleteannotation',cross()),('deleteallannotation',cross()+p('M2 6v17h9')),
        ('nextannotation',arrow('right',17,19,8)),('previousannotation',arrow('left',17,19,8)),
        ('replycomment',p('M21 21v-5h-8m3-3-3 3 3 3')),
        ('hideallnotes',p('M3 21 21 3')),('showannotations',plus())]:
        add(name,badge(bubble(),mark),'Comment: '+name)
    add('shownote',bubble(),'Insert comment speech bubble')
    for name,mark in [
        ('closedoc',cross()),('editdoc',small_pen()),('newdoc',plus()),
        ('openreadonly',transform(lock(),'translate(10 10) scale(.55)')),
        ('setdocumentproperties',transform(gear(),'translate(10 10) scale(.55)')),
        ('toolprotectiondocument',transform(lock(),'translate(10 10) scale(.55)')),
        ('sharedocument',c(17,16,2)+p('M12 22q0-5 5-4 5-1 5 4')),
        ('saveastemplate',p('m17 12 2 3 4 1-3 3v4l-3-2-3 2v-4l-3-3 4-1z'))]:
        noun=GLYPHS['save'][0] if name=='saveastemplate' else page()+lines()
        if name=='openreadonly':noun=GLYPHS['open'][0]
        add(name,badge(noun,mark),'Document action: '+name)
    add('edit',pencil(),'Edit pencil')
    add('signature',p('M3 18c8-17 10-17 5-7-5 9-5 12-1 8l5-5-2 5 5-3-1 3h7M3 22h18'),'Handwritten signature stroke')
    add('signpdf',badge(page()+p('M8 8h7'),small_pen())+p('M3 22h7'),'Signed document')
    add('redactdoc',page()+p('M8 8h8M8 12h8m-8 1.5h8M8 17h6'),'Document with redaction block')
    add('exportdirecttopdf',page()+p('M8 10h8m-8 4h5')+arrow('right',17,19,8),'Fixed document export arrow')
    add('exportdirecttoepub',badge(book(),arrow('right',17,19,8)),'Electronic book export')
    add('exportto',badge(page(),arrow('right',17,18,10)),'Document export')
    add('sendmail',r(2,5,20,14,1)+p('m3 6 9 7 9-7'),'Envelope')
    add('insertenvelope',badge(r(2,5,20,14,1)+p('m3 6 9 7 9-7'),plus()),'Insert envelope')
    add('mailmergewizard',badge(r(2,5,20,14,1)+p('m3 6 9 7 9-7'),p('M14 14h8M14 18h8M14 22h8')),'Envelope with recipient list')
    add('addressbooksource',book()+c(7,8,2)+p('M4 15q3-6 6 0M16 8h3m-3 4h3'),'Address book with contact')
    add('comparedocuments',r(2,3,8,18,1)+r(14,3,8,18,1)+p('M5 8h2m10 0h2M5 13h2m10 3h2'),'Two documents with different line positions')
    add('mergedocuments',p('M2 3h7v10H2zM15 3h7v10h-7zM5 16l7 5 7-5M12 21v-8'),'Documents converging to one')
    add('mergedialog',badge(page()+lines(),p('M12 14l5 5 5-5m-5 5v3')),'Merge document dialog')
    add('reload',refresh(),'Refresh circular arrows')
    add('editglossary',book()+p('M15 9h5m-5 4h5M5 8v7m-2-3h4'),'AutoText book')
    add('bibliographycomponent',book()+p('M5 7h4M5 11h4M15 7h4M15 11h4'),'Bibliography book')
    add('insertauthoritiesentry',badge(book(),plus()),'Add bibliographic citation')
    add('insertbookmark',p('M6 3h12v19l-6-5-6 5z'),'Bookmark ribbon')
    add('insertindexesentry',badge(page()+p('M8 7h8M8 11h8'),plus()),'Index entry plus')
    add('insertmultiindex',page()+p('M8 7h5m2 0h1M8 12h5m2 0h1M8 17h5m2 0h1'),'Index entries and page numbers')
    add('updatecurindex',badge(page()+p('M8 7h7M8 11h7'),transform(refresh(),'translate(10 10) scale(.55)')),'Refresh index')
    add('insertreferencefield',badge(page(),p('M13 21v-7h8m-3-3 3 3-3 3')),'Cross reference to another field')
    add('charmapcontrol',p('M3 21h6v-4C0 11 5 3 12 3s12 8 3 14v4h6'),'Omega special character')
    add('insertmath',p('M2 13h4l3 8 5-18h8M15 11h7m-7 5h7'),'Root and equality equation')
    add('dbviewfunctions',letter('f',3,3,1.2)+letter('x',13,8,.9),'Function fx')
    add('hyphenate',p('M3 6h7m5 0h6M11 6h2M3 12h11M3 18h7m5 0h6M11 18h2'),'Text split at hyphens')
    add('spelling',letter('A',3,3,1.1)+check(16,18),'Letter A with spelling check')
    add('spellonline',letter('A',3,3,1.1)+p('m2 20 3-2 3 2 3-2 3 2 3-2 3 2'),'Letter with live spelling wave')
    add('thesaurus',book()+p('M5 8h4m-4 5h4M15 10h4m-4 5h4'),'Thesaurus facing word lists')
    add('wordcountdialog',letter('1',2,4,1)+letter('2',12,4,1)+p('M3 21h18'),'Word count 12')
    add('titlepagedialog',page()+letter('T',8,7,.9)+p('M8 19h8'),'Title page with T')
    add('watermark',page()+transform(letter('A',5,6,1.1),'rotate(-25 12 12)'),'Diagonal watermark on page')
    # Explicit field symbols sit inside a document outline.
    for name,body in [
        ('insertfieldctrl',letter('#',8,10,.7)),('insertpagenumberfield',letter('1',9,10,.7)),
        ('insertpagecountfield',letter('#',8,10,.7)+p('M2 6v17h12')),
        ('inserttitlefield',letter('T',8,10,.7))]:
        add(name,page()+body,'Document field: '+name)
    for name,y in [('insertheader',5),('insertfooter',18)]:
        add(name,r(4,2,16,20,1)+p(f'M7 {y}h10m-10 3h10')+p('M8 11h8'),'Page '+name)
    add('editheaderandfooter',r(4,2,16,20,1)+p('M7 6h10M7 18h10M7 9h10M7 15h10'),'Header and footer bands')
    for name, at_top in [('insertfootnote',False),('insertendnote',True)]:
        add(name,page()+p('M8 8h8M8 12h5M8 17h8')+p('M3 3v4m-1-2h2' if at_top else 'M20 17v5m-2-2h4'),'Endnote' if at_top else 'Footnote')
    # Caption text sits under the picture, outside its frame: an image alone reads as Chèn ảnh.
    add('insertcaptiondialog',r(4,2.5,16,12,1.5)+c(8.5,6.5,1.3)+p('m4 13 4.5-4 3 2.5 3-3.5 5.5 5M3 18.5h18M6 22h12'),
        'Small picture above two caption text lines')
    add('insertsection',page()+r(7,10,10,7)+p('M8 6h5'),'Document section rectangle')
    add('insertbreak',p('M3 3h18v6H3zM3 15h18v6H3zM3 12h4m3 0h4m3 0h4'),'Manual break between blocks')
    add('insertpagebreak',p('M5 2h14v7H5zM5 15h14v7H5zM2 12h20m-3-2 3 2-3 2'),'Page break arrow between pages')
    add('text',p('M3 4h18v4M12 4v17M7 21h10'),'Text T')
    add('verticaltext',p('M4 3v13m-2-3 2 3 2-3')+transform(letter('T',9,3,1),'rotate(90 15 10)'),'Vertical text direction')
    add('fontwork',p('M3 20 7 6l5-3 5 3 4 14M5 14h14M7 6l5 14 5-14'),'Bent decorative letter construction')
    add('fontworkgalleryfloater',badge(GLYPHS['fontwork'][0],plus()),'Decorative text gallery')
    add('fontworksameletterheights',p('M2 3h20M2 21h20')+letter('A',3,6,.9)+letter('A',14,6,.9),'Two letters aligned to equal height')
