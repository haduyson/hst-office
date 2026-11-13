# SPDX-License-Identifier: AGPL-3.0-only
"""Paragraph styles of the bibliography (UNO).

The bibliography result is pasted as HTML, which makes every paragraph "Text body"; after each write the
paragraphs get these document styles, created on first use. "Bibliography" is the name of Word's built-in
bibliography style and is kept as is by .docx export and import; the built-in "Bibliography 1" is not used, since
.docx export writes it under its translated UI name and it comes back as another style (phase 01 of the plan).
"""
ENTRY, TITLE, GROUP = "Bibliography", "Bibliography Title", "Bibliography Group"
ROLE_STYLES = {"entry": ENTRY, "title": TITLE, "heading": GROUP}
HANGING = 1000  # 1/100 mm: the usual 1 cm hanging indent of a reference list


def ensure_styles(doc, hanging):
    family = doc.getStyleFamilies().getByName("ParagraphStyles")
    for name in (ENTRY, TITLE, GROUP):
        if family.hasByName(name):
            continue
        style = doc.createInstance("com.sun.star.style.ParagraphStyle")
        family.insertByName(name, style)
        style.ParentStyle = "Standard"
        if name == TITLE:
            style.ParentStyle = "Heading 1" if family.hasByName("Heading 1") else "Standard"
            style.ParaAdjust = 3  # CENTER
            continue
        if name == GROUP:
            style.CharWeight = 150.0  # BOLD
            style.ParaTopMargin = 200
        style.ParaBottomMargin = 100
    entry = family.getByName(ENTRY)
    entry.ParaLeftMargin = HANGING if hanging else 0
    entry.ParaFirstLineIndent = -HANGING if hanging else 0


def style_bibliography(doc, mark, roles, hanging):
    """Give the paragraphs of the bibliography field the style of their role (title, group heading, entry)."""
    ensure_styles(doc, hanging)
    anchor = mark.getAnchor()
    cursor = anchor.getText().createTextCursorByRange(anchor)
    enum = cursor.createEnumeration()
    index = 0
    while enum.hasMoreElements() and index < len(roles):  # never past the planned paragraphs
        para = enum.nextElement()
        if not para.supportsService("com.sun.star.text.Paragraph"):
            continue
        para.ParaStyleName = ROLE_STYLES[roles[index]]
        index += 1
