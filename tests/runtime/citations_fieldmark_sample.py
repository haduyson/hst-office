# SPDX-License-Identifier: AGPL-3.0-only
"""The sample document of the citation fieldmark checks: citations in body text with a styled
paragraph, in a directly formatted paragraph, in a table and in a footnote, plus a
three-paragraph bibliography under a heading. Each field records what the checks expect."""
import json

from citations_fieldmark_uno import BIBLIOGRAPHY_PREFIX, CITATION_PREFIX, MARKER

BODY_STYLE = "HST Citation Check Body"
BIG_ITEM = {
    "id": "nguyen-van-an-2010", "type": "book",
    "title": 'Nghiên cứu "đặc biệt" về ăâđêôơư, ký tự \\ / <tag> & \' {ngoặc}',
    "author": [{"literal": "Nguyễn Văn An"}], "issued": {"date-parts": [[2010]]},
    "abstract": "Tóm tắt dài có dấu tiếng Việt. " * 300,  # pushes the code past 8 KB
}


def citation_code(cid, item_id, extra=None):
    body = {"v": 1, "citationID": cid, "items": [{"id": item_id, "locator": "314-315", "label": "page"}]}
    if cid == "c1":
        body["items"][0]["itemData"] = BIG_ITEM
    body.update(extra or {})
    return CITATION_PREFIX + json.dumps(body, ensure_ascii=False)


# (citationID, html result, plain result, italic piece, superscript piece, wrapper)
CITATIONS = [
    ("c1", "[1, <i>tr.</i> 314–315]", "[1, tr. 314–315]", "tr.", None, None),
    ("c2", "(Nguyễn Văn An, 2010)", "(Nguyễn Văn An, 2010)", None, None, None),
    ("c3", "[2]", "[2]", None, None, None),
    ("c4", "[3<sup>a</sup>]", "[3a]", None, "a", None),
    ("c5", "Smith, <i>Book</i>, 2020", "Smith, Book, 2020", "Book", None, "Footnote"),
]
READING_ORDER = ["c1", "c2", "c3", "c4", "c5"]
BIB_ENTRIES = [
    ("[1] Nguyễn Văn An (2010), <i>Giáo trình kinh tế</i>, Nxb Giáo dục, Hà Nội.",
     "[1] Nguyễn Văn An (2010), Giáo trình kinh tế, Nxb Giáo dục, Hà Nội."),
    ("[2] Trần Thị Bình (2019), \"Bài báo\", <i>Tạp chí Khoa học</i>, 12(3), tr. 5–9.",
     "[2] Trần Thị Bình (2019), \"Bài báo\", Tạp chí Khoa học, 12(3), tr. 5–9."),
    ("[3] Smith J. (2020), <i>Book</i>, Springer.", "[3] Smith J. (2020), Book, Springer."),
]
BIB_CODE = BIBLIOGRAPHY_PREFIX + ' {"v":1}'
# Word's built-in bibliography style name, kept as is by .docx export and import; the built-in
# "Bibliography 1" is written under its UI name ("Thư tịch 1" in Vietnamese) and comes back as a
# different custom style.
BIB_STYLE = "Bibliography"


def bibliography_html():
    return "".join(f"<p>{html}</p>" for html, _ in BIB_ENTRIES)


def bibliography_text():
    return "\n".join(plain for _, plain in BIB_ENTRIES)


def add_styles(doc):
    family = doc.getStyleFamilies().getByName("ParagraphStyles")
    for name, font in ((BODY_STYLE, "DejaVu Serif"), (BIB_STYLE, None)):
        if family.hasByName(name):
            continue
        style = doc.createInstance("com.sun.star.style.ParagraphStyle")
        family.insertByName(name, style)
        style.ParentStyle = "Standard"
        if font:
            style.CharFontName, style.CharHeight = font, 13.0
        else:  # hanging indent, as a citation style sets it
            style.ParaLeftMargin, style.ParaFirstLineIndent = 1000, -1000


def build(session):
    """Write the sample text with markers, insert every field with the real commands."""
    doc = session.doc
    add_styles(doc)
    text = doc.getText()
    cursor = text.createTextCursor()
    cursor.ParaStyleName = BODY_STYLE
    text.insertString(cursor, f"Theo Nguyễn Văn An {MARKER} thì kết quả {MARKER} đáng chú ý.", False)
    text.insertControlCharacter(cursor, 0, False)
    cursor.ParaStyleName = "Standard"
    cursor.CharFontName, cursor.CharHeight, cursor.CharWeight = "DejaVu Sans", 11.0, 150.0
    text.insertString(cursor, f"Đoạn định dạng trực tiếp {MARKER}.", False)
    text.insertControlCharacter(cursor, 0, False)
    cursor.setPropertyToDefault("CharFontName")
    cursor.setPropertyToDefault("CharHeight")
    cursor.setPropertyToDefault("CharWeight")
    table = doc.createInstance("com.sun.star.text.TextTable")
    table.initialize(1, 1)
    text.insertTextContent(cursor, table, False)
    table.getCellByName("A1").setString(f"Ô bảng {MARKER}")
    end = text.getEnd()
    text.insertString(end, f"Chú thích ở đây{MARKER}.", False)
    text.insertControlCharacter(text.getEnd(), 0, False)
    text.insertString(text.getEnd(), "TÀI LIỆU THAM KHẢO", False)
    heading = text.getEnd()
    text.createTextCursorByRange(heading).ParaStyleName = "Heading 1"
    text.insertControlCharacter(text.getEnd(), 0, False)
    text.createTextCursorByRange(text.getEnd()).ParaStyleName = "Standard"
    markers = session.markers()
    assert len(markers) == len(CITATIONS), len(markers)
    for rng, (cid, html, _plain, _it, _sup, wrapper) in zip(markers, CITATIONS):
        session.insert_field(rng, citation_code(cid, "item-" + cid), html, wrapper)
    session.insert_field(text.getEnd(), BIB_CODE, bibliography_html())
    session.drop_markers()


def citation_id(code):
    try:
        return json.loads(code[len(CITATION_PREFIX):])["citationID"]
    except (ValueError, KeyError):
        return None


def expected_codes():
    return {cid: citation_code(cid, "item-" + cid) for cid, *_ in CITATIONS}
