# SPDX-License-Identifier: AGPL-3.0-only
"""Word-style .docx fixtures written by hand (no python-docx), for scripts/perf/large_file_fixtures_sized.py.

write_docx_kind(path, kind, units): kind is one of
- images   a report with one photo or screenshot per page (distinct pictures, as pasted from a phone or a screen)
- text     long text in sections, with a 8x5 table in every other section
- review   the same text under review: insertions and deletions by several authors, a comment on every third paragraph
- notes    long text with a footnote on every `comment_every`-th paragraph
- styles   a few hundred paragraph and character styles, every run with its own direct formatting
`units` scales the content (pictures for images, sections otherwise); the parts look like the common word processor's
(docProps/app.xml names it, compatibility mode 15). All text is generated, the pictures are noise.
"""
import random
import zipfile
from xml.sax.saxutils import escape

from large_file_fixture_words import sentence
from large_file_fixtures_media import noise_png, photo_jpeg

NS = ('xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main" '
      'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships" '
      'xmlns:wp="http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing" '
      'xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main" '
      'xmlns:pic="http://schemas.openxmlformats.org/drawingml/2006/picture"')
REL = "http://schemas.openxmlformats.org/officeDocument/2006/relationships/"
AUTHORS = ("Nguyễn Văn An", "Trần Thị Bình", "Lê Hoàng Cường", "Phạm Thu Dung")
FONTS = ("Times New Roman", "Arial", "Calibri", "Cambria", "Tahoma")


def run(text, rpr=""):
    return '<w:r>%s<w:t xml:space="preserve">%s</w:t></w:r>' % (rpr and "<w:rPr>%s</w:rPr>" % rpr, escape(text))


def para(body, style="", ppr=""):
    props = ('<w:pStyle w:val="%s"/>' % style if style else "") + ppr
    return "<w:p>%s%s</w:p>" % (props and "<w:pPr>%s</w:pPr>" % props, body)


def table(rnd, rows, cols):
    grid = "".join('<w:gridCol w:w="1800"/>' for _ in range(cols))
    cells = "".join("<w:tr>%s</w:tr>" % "".join('<w:tc><w:tcPr><w:tcW w:w="1800" w:type="dxa"/></w:tcPr>%s</w:tc>'
                                                 % para(run(sentence(rnd, 3))) for _ in range(cols)) for _ in range(rows))
    return ('<w:tbl><w:tblPr><w:tblStyle w:val="TableGrid"/><w:tblW w:w="0" w:type="auto"/></w:tblPr>'
            "<w:tblGrid>%s</w:tblGrid>%s</w:tbl>" % (grid, cells))


def picture(n, rid, cx, cy):
    return ('<w:r><w:drawing><wp:inline distT="0" distB="0" distL="0" distR="0"><wp:extent cx="%d" cy="%d"/>'
            '<wp:docPr id="%d" name="Picture %d"/><a:graphic><a:graphicData uri="http://schemas.openxmlformats.org/'
            'drawingml/2006/picture"><pic:pic><pic:nvPicPr><pic:cNvPr id="%d" name="image%d"/><pic:cNvPicPr/>'
            '</pic:nvPicPr><pic:blipFill><a:blip r:embed="%s"/><a:stretch><a:fillRect/></a:stretch></pic:blipFill>'
            '<pic:spPr><a:xfrm><a:off x="0" y="0"/><a:ext cx="%d" cy="%d"/></a:xfrm><a:prstGeom prst="rect">'
            '<a:avLst/></a:prstGeom></pic:spPr></pic:pic></a:graphicData></a:graphic></wp:inline></w:drawing></w:r>'
            % (cx, cy, n, n, n, n, rid, cx, cy))


class Review:
    """Insertions, deletions and comments with distinct ids, authors and dates."""

    def __init__(self, rnd, comment_every=3):
        self.rnd, self.n, self.comments, self.every, self.notes = rnd, 0, [], comment_every, []

    def noted(self, i):
        """A paragraph with a footnote on every `every`-th one (theses and legal texts)."""
        body = run(sentence(self.rnd, 50))
        if i % self.every == 0:
            n = len(self.notes) + 1
            self.notes.append('<w:footnote w:id="%d"><w:p><w:r><w:footnoteRef/></w:r>%s</w:p></w:footnote>'
                              % (n, run(" " + sentence(self.rnd, 25))))
            body += ('<w:r><w:rPr><w:vertAlign w:val="superscript"/></w:rPr><w:footnoteReference w:id="%d"/></w:r>' % n)
        return para(body)

    def mark(self, tag, text):
        self.n += 1
        attrs = 'w:id="%d" w:author="%s" w:date="2026-0%d-1%dT0%d:15:00Z"' % (
            self.n, self.rnd.choice(AUTHORS), 1 + self.n % 9, self.n % 10, self.n % 10)
        if tag == "del":
            return '<w:del %s><w:r><w:delText xml:space="preserve">%s</w:delText></w:r></w:del>' % (attrs, escape(text))
        return "<w:ins %s>%s</w:ins>" % (attrs, run(text))

    def paragraph(self, i):
        rnd = self.rnd
        body = "".join(run(sentence(rnd, 8)) if k % 3 == 0 else self.mark(("ins", "del")[k % 3 - 1], sentence(rnd, 5))
                       for k in range(6))
        if i % self.every == 0:
            c = len(self.comments)
            self.comments.append('<w:comment w:id="%d" w:author="%s" w:date="2026-03-02T09:00:00Z" w:initials="X">%s'
                                 "</w:comment>" % (c, rnd.choice(AUTHORS), para(run(sentence(rnd, 14)))))
            body = ('<w:commentRangeStart w:id="%d"/>%s<w:commentRangeEnd w:id="%d"/><w:r><w:commentReference w:id="%d"/>'
                    "</w:r>" % (c, body, c, c))
        return para(body)


def styles_xml(many):
    base = ('<w:docDefaults><w:rPrDefault><w:rPr><w:rFonts w:ascii="Times New Roman" w:hAnsi="Times New Roman" '
            'w:eastAsia="Times New Roman" w:cs="Times New Roman"/><w:sz w:val="26"/><w:lang w:val="vi-VN"/></w:rPr>'
            '</w:rPrDefault><w:pPrDefault><w:pPr><w:spacing w:after="120" w:line="276" w:lineRule="auto"/></w:pPr>'
            '</w:pPrDefault></w:docDefaults><w:style w:type="paragraph" w:default="1" w:styleId="Normal"><w:name '
            'w:val="Normal"/></w:style><w:style w:type="table" w:styleId="TableGrid"><w:name w:val="Table Grid"/>'
            '<w:tblPr><w:tblBorders><w:top w:val="single" w:sz="4"/><w:bottom w:val="single" w:sz="4"/><w:insideH '
            'w:val="single" w:sz="4"/><w:insideV w:val="single" w:sz="4"/></w:tblBorders></w:tblPr></w:style>')
    for lvl in (1, 2):
        base += ('<w:style w:type="paragraph" w:styleId="Heading%d"><w:name w:val="heading %d"/><w:basedOn w:val="Normal"/>'
                 '<w:pPr><w:keepNext/><w:outlineLvl w:val="%d"/></w:pPr><w:rPr><w:b/><w:sz w:val="%d"/></w:rPr></w:style>'
                 % (lvl, lvl, lvl - 1, 36 - 4 * lvl))
    for i in range(many):  # chains of based-on paragraph styles and character styles, as in long-lived templates
        parent = "Normal" if i % 10 == 0 else "P%d" % (i - 1)
        base += ('<w:style w:type="paragraph" w:customStyle="1" w:styleId="P%d"><w:name w:val="Đoạn %d"/><w:basedOn '
                 'w:val="%s"/><w:pPr><w:spacing w:before="%d"/><w:ind w:left="%d"/></w:pPr><w:rPr><w:rFonts w:ascii="%s" '
                 'w:hAnsi="%s"/><w:sz w:val="%d"/></w:rPr></w:style><w:style w:type="character" w:customStyle="1" '
                 'w:styleId="C%d"><w:name w:val="Ký tự %d"/><w:rPr><w:color w:val="%06X"/><w:i/></w:rPr></w:style>'
                 % (i, i, parent, i % 7 * 20, i % 5 * 100, FONTS[i % 5], FONTS[i % 5], 20 + i % 8, i, i, i * 7919 % 0xFFFFFF))
    return '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n<w:styles %s>%s</w:styles>' % (NS, base)


def styled_paragraph(rnd, i, many):
    runs = "".join(run(sentence(rnd, 4), '<w:rStyle w:val="C%d"/><w:rFonts w:ascii="%s" w:hAnsi="%s"/>%s<w:sz w:val="%d"/>'
                       '<w:color w:val="%06X"/>' % (rnd.randrange(many), FONTS[k % 5], FONTS[k % 5],
                                                    "<w:b/>" if k % 2 else "", 22 + k % 6, rnd.randrange(0xFFFFFF)))
                   for k in range(8))
    return para(runs, "P%d" % (i % many), '<w:jc w:val="both"/><w:ind w:firstLine="567"/>')


def content(rnd, kind, units, review, many, rels, media):
    for u in range(units):
        yield para(run("Mục %d. %s" % (u + 1, sentence(rnd, 5))), "Heading%d" % (1 + u % 2))
        if kind == "images":
            rid, png = "rIdImg%d" % u, u % 3 == 2
            media.append(("image%d.%s" % (u, "png" if png else "jpeg"),
                          noise_png(rnd, 1600, 1000) if png else photo_jpeg(rnd, *((4000, 3000) if u % 5 == 0
                                                                                       else (1600, 1067)))))
            rels.append('<Relationship Id="%s" Type="%simage" Target="media/%s"/>' % (rid, REL, media[-1][0]))
            yield para(picture(u + 1, rid, 5760000, 3600000 if png else 3840000), "", '<w:jc w:val="center"/>')
            yield para(run(sentence(rnd, 40))) + '<w:p><w:r><w:br w:type="page"/></w:r></w:p>'
            continue
        for p in range(5):
            if kind == "review":
                yield review.paragraph(u * 5 + p)
            elif kind == "notes":
                yield review.noted(u * 5 + p)
            elif kind == "styles":
                yield styled_paragraph(rnd, u * 5 + p, many)
            else:
                yield para(run(sentence(rnd, 60)))
        if kind == "text" and u % 2 == 0:
            yield table(rnd, 8, 5) + para("")
    yield ('<w:sectPr><w:pgSz w:w="11906" w:h="16838"/><w:pgMar w:top="1134" w:right="1134" w:bottom="1134" '
           'w:left="1701" w:header="720" w:footer="720" w:gutter="0"/></w:sectPr>')


def write_docx_kind(path, kind, units, seed=11, comment_every=3):
    rnd = random.Random(seed)
    rels, media, review, many = [], [], Review(rnd, comment_every), 300 if kind == "styles" else 0
    head = '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
    relx = '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">%s</Relationships>'
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED, compresslevel=6) as z:
        with z.open("word/document.xml", "w", force_zip64=True) as fh:  # streamed: text fixtures reach 300 MB of XML
            fh.write((head + "<w:document %s><w:body>" % NS).encode("utf-8"))
            for chunk in content(rnd, kind, units, review, many, rels, media):
                fh.write(chunk.encode("utf-8"))
            fh.write(b"</w:body></w:document>")
        for name, data in media:
            z.writestr("word/media/" + name, data, compress_type=zipfile.ZIP_STORED)
        comments = review.comments
        ct = ['<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>',
              '<Default Extension="xml" ContentType="application/xml"/>',
              '<Default Extension="jpeg" ContentType="image/jpeg"/>', '<Default Extension="png" ContentType="image/png"/>']
        wml = "application/vnd.openxmlformats-officedocument.wordprocessingml."
        parts = (("document", "document.main"), ("styles", "styles"), ("settings", "settings"))
        parts += (("comments", "comments"),) if comments else ()
        parts += (("footnotes", "footnotes"),) if review.notes else ()
        ct += ['<Override PartName="/word/%s.xml" ContentType="%s%s+xml"/>' % (n, wml, t) for n, t in parts]
        ct += ['<Override PartName="/docProps/app.xml" ContentType="application/vnd.openxmlformats-officedocument.'
               'extended-properties+xml"/>']
        rels += ['<Relationship Id="rIdS" Type="%sstyles" Target="styles.xml"/>' % REL,
                 '<Relationship Id="rIdT" Type="%ssettings" Target="settings.xml"/>' % REL]
        if review.notes:
            rels.append('<Relationship Id="rIdF" Type="%sfootnotes" Target="footnotes.xml"/>' % REL)
            z.writestr("word/footnotes.xml", head + '<w:footnotes %s><w:footnote w:type="separator" w:id="-1"><w:p><w:r>'
                       '<w:separator/></w:r></w:p></w:footnote><w:footnote w:type="continuationSeparator" w:id="0"><w:p>'
                       '<w:r><w:continuationSeparator/></w:r></w:p></w:footnote>%s</w:footnotes>' % (NS, "".join(review.notes)))
        if comments:
            rels.append('<Relationship Id="rIdC" Type="%scomments" Target="comments.xml"/>' % REL)
            z.writestr("word/comments.xml", head + "<w:comments %s>%s</w:comments>" % (NS, "".join(comments)))
        z.writestr("[Content_Types].xml", head + '<Types xmlns="http://schemas.openxmlformats.org/package/2006/'
                   'content-types">%s</Types>' % "".join(ct))
        z.writestr("_rels/.rels", head + relx % ('<Relationship Id="rId1" Type="%sofficeDocument" Target="word/'
                                                 'document.xml"/><Relationship Id="rId2" Type="%sextended-properties" '
                                                 'Target="docProps/app.xml"/>' % (REL, REL)))
        z.writestr("docProps/app.xml", head + '<Properties xmlns="http://schemas.openxmlformats.org/officeDocument/'
                   '2006/extended-properties"><Application>Microsoft Office Word</Application><AppVersion>16.0000'
                   '</AppVersion></Properties>')
        z.writestr("word/_rels/document.xml.rels", head + relx % "".join(rels))
        z.writestr("word/styles.xml", styles_xml(many))
        z.writestr("word/settings.xml", head + '<w:settings %s><w:compat><w:compatSetting w:name="compatibilityMode" '
                   'w:uri="http://schemas.microsoft.com/office/word" w:val="15"/></w:compat></w:settings>' % NS)
