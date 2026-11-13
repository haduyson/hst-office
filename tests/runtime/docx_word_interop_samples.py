# SPDX-License-Identifier: AGPL-3.0-only
"""Sample documents and checks for check-docx-word-interop.py (split runs, East Asian font export)."""
import os
import re
import zipfile

SPLIT_RUNS_XML = (
    '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
    '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"><w:body>'
    '<w:p><w:r><w:t>Nguy</w:t></w:r><w:r><w:t>ễ</w:t></w:r><w:r><w:t xml:space="preserve">n </w:t></w:r>'
    '<w:r><w:rPr><w:b/></w:rPr><w:t>Vă</w:t></w:r><w:r><w:rPr><w:b/></w:rPr><w:t>n</w:t></w:r>'
    '<w:r><w:t xml:space="preserve"> </w:t></w:r><w:bookmarkStart w:id="0" w:name="dau"/><w:r><w:t>A</w:t></w:r>'
    '<w:bookmarkEnd w:id="0"/><w:r><w:t>n, k</w:t></w:r><w:r><w:t>ế</w:t></w:r><w:r><w:t>t qu</w:t></w:r>'
    '<w:r><w:t>ả</w:t></w:r><w:r><w:tab/></w:r><w:r><w:t>cu</w:t></w:r><w:r><w:t>ố</w:t></w:r><w:r><w:t>i.</w:t></w:r></w:p>'
    '<w:p><w:r><w:t>Dòng hai</w:t></w:r><w:r><w:t>.</w:t></w:r></w:p>'
    '<w:sectPr/></w:body></w:document>')


def split_runs_docx(path):
    """A .docx whose runs are split the way Word splits Vietnamese text."""
    with zipfile.ZipFile(path, "w") as package:
        package.writestr("[Content_Types].xml",
                         '<?xml version="1.0" encoding="UTF-8"?><Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
                         '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
                         '<Default Extension="xml" ContentType="application/xml"/><Override PartName="/word/document.xml" '
                         'ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/></Types>')
        package.writestr("_rels/.rels",
                         '<?xml version="1.0" encoding="UTF-8"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
                         '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" '
                         'Target="word/document.xml"/></Relationships>')
        package.writestr("word/document.xml", SPLIT_RUNS_XML)


def check_split_runs(desktop, out, expect, prop):
    """Runs split the way Word splits Vietnamese text keep their text, bold run and bookmark."""
    import uno
    hidden = (prop("Hidden", True),)
    path = os.path.join(out, "split-runs.docx")
    split_runs_docx(path)
    doc = desktop.loadComponentFromURL(uno.systemPathToFileUrl(path), "_blank", 0, hidden)
    paragraphs = doc.getText().createEnumeration()
    first = paragraphs.nextElement()
    expect("split runs: paragraph text", first.getString(), "Nguy\u1ec5n V\u0103n An, k\u1ebft qu\u1ea3\tcu\u1ed1i.")
    expect("split runs: second paragraph", paragraphs.nextElement().getString(), "D\u00f2ng hai.")
    portions = [(p.getString(), p.CharWeight > 100) for p in first.createEnumeration() if p.TextPortionType == "Text"]
    expect("split runs: only V\u0103n is bold", [text for text, bold in portions if bold], ["V\u0103n"])
    expect("split runs: bookmark covers A", doc.getBookmarks().getByName("dau").getAnchor().getString(), "A")
    doc.close(True)


def east_asian_fonts(path):
    """(Latin, East Asian) pairs of every w:rFonts that names an East Asian font."""
    pairs = []
    with zipfile.ZipFile(path) as package:
        for name in ("word/styles.xml", "word/document.xml"):
            for fonts in re.findall(r"<w:rFonts [^>]*>", package.read(name).decode("utf-8")):
                attrs = dict(re.findall(r'w:(ascii|eastAsia)="([^"]*)"', fonts))
                if "eastAsia" in attrs:
                    pairs.append((attrs.get("ascii"), attrs["eastAsia"]))
    return pairs


def check_east_asian_export(desktop, out, expect, prop):
    """A stored CJK East Asian font is exported as the Latin font unless the text has CJK."""
    import uno
    for name, sample, keeps in (("vietnamese-cjk-font", "Nguy\u1ec5n V\u0103n An, k\u1ebft qu\u1ea3.", False),
                              ("chinese-cjk-font", "Nguy\u1ec5n V\u0103n An \u7814\u7a76\u7ed3\u679c.", True)):
        doc = desktop.loadComponentFromURL("private:factory/swriter", "_blank", 0, (prop("Hidden", True),))
        doc.getStyleFamilies().getByName("ParagraphStyles").getByName("Standard").CharFontNameAsian = "Noto Serif CJK SC"
        text = doc.getText()
        text.setString(sample)
        cursor = text.createTextCursor()
        cursor.gotoEnd(False)
        text.insertString(cursor, " B\u00e0i vi\u1ebft.", False)
        cursor.gotoStartOfParagraph(True)
        cursor.CharFontNameAsian = "SimSun"  # direct formatting on the run as well
        path = os.path.join(out, name + ".docx")
        doc.storeToURL(uno.systemPathToFileUrl(path), (prop("FilterName", "MS Word 2007 XML"),))
        doc.close(True)
        pairs = east_asian_fonts(path)
        cjk = sorted({east for _, east in pairs if east in ("Noto Serif CJK SC", "SimSun")})
        expect(f"{name}: East Asian fonts kept", cjk, ["Noto Serif CJK SC", "SimSun"] if keeps else [])
        if not keeps:
            expect(f"{name}: East Asian font equals the Latin font", [p for p in pairs if p[0] and p[0] != p[1]], [])
