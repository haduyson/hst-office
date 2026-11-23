# SPDX-License-Identifier: LicenseRef-HST-Proprietary
# Copyright (C) 2026 HASON TECH
""""Multiple" line spacing in lines, as in Word (hst-line-spacing-multiple-like-word.patch): the Paragraph dialog of
Writer, Slides and Draw (and Sheets, text in shapes) shows 130 % as "1,30" and reads "1,3", "1.3" and "130%" as 130 %,
within 0,06-132 lines; DOCX w:line="312" w:lineRule="auto" opens as 1,30 and saves as 312 again. Used by
check-dialogs-writer.py ("line-spacing", "line-spacing-others")."""
import re
import zipfile

from hst_dialog_uitest import click, props, select_entry, state, type_value

PROP = 0  # com.sun.star.style.LineSpacingMode.PROP
MULTIPLE = 4  # position of "Nhiều" (Proportional) in the dialog's list
WRITER_DIALOG = "ParagraphPropertiesDialog"
FIELD = "spinED_LINEDISTPERCENT"


def line_spacing(mode, height):
    import uno
    spacing = uno.createUnoStruct("com.sun.star.style.LineSpacing")
    spacing.Mode, spacing.Height = mode, height
    return spacing


def first_paragraph(doc):
    return doc.getText().createEnumeration().nextElement()


def shown(dlg):
    """(selected mode, text of the Multiple field) on the Indents and Spacing page."""
    return state(dlg.getChild("comboLB_LINEDIST")).get("SelectEntryPos"), state(dlg.getChild(FIELD)).get("Text")


def type_multiple(dlg, text):
    select_entry(dlg, "comboLB_LINEDIST", MULTIPLE)
    type_value(dlg, FIELD, text)
    click(dlg, "ok")


def docx_spacing(path):
    """w:line/w:lineRule of every paragraph spacing in word/document.xml."""
    with zipfile.ZipFile(path) as docx:
        xml = docx.read("word/document.xml").decode("utf-8")
    tags = re.findall(r"<w:spacing [^>]*>", xml)
    return [(re.search(r'w:line="(\d+)"', t).group(1), re.search(r'w:lineRule="(\w+)"', t).group(1))
            for t in tags if 'w:line="' in t and "w:lineRule=" in t]


def check_line_spacing(h, c):
    doc = h.new_document()
    doc.getText().setString("Giãn dòng kiểu Word.")
    h.wait_idle()
    para = first_paragraph(doc)

    para.ParaLineSpacing = line_spacing(PROP, 130)
    dlg = h.open_dialog(".uno:ParagraphDialog", WRITER_DIALOG)
    c.equal("line spacing: 130 % shows Multiple 1,30", shown(dlg), (str(MULTIPLE), "1,30"))
    click(dlg, "cancel")

    para.ParaLineSpacing = line_spacing(PROP, 115)
    dlg = h.open_dialog(".uno:ParagraphDialog", WRITER_DIALOG)
    c.equal("line spacing: 115 % keeps its own entry", shown(dlg)[0], "1")
    click(dlg, "cancel")

    for text, expected in (("1,3", 130), ("1.3", 130), ("130%", 130), ("2,5", 250), ("1,125", 113),
                           ("0,01", 6), ("200", 13200)):
        para.ParaLineSpacing = line_spacing(PROP, 100)
        h.wait_idle(0.5)
        dlg = h.open_dialog(".uno:ParagraphDialog", WRITER_DIALOG)
        type_multiple(dlg, text)
        h.wait_idle()
        got = first_paragraph(doc).ParaLineSpacing
        c.equal(f"line spacing: typed {text!r}", (int(got.Mode), got.Height), (PROP, expected))

    # DOCX: 1,3 lines is w:line="312" auto, opens as 1,30 and saves as 312 again
    first_paragraph(doc).ParaLineSpacing = line_spacing(PROP, 130)
    first_url, second_url = h.temp_url("line-spacing-1.docx"), h.temp_url("line-spacing-2.docx")
    doc.storeToURL(first_url, props(FilterName="MS Word 2007 XML"))
    c.equal("line spacing: DOCX saves w:line 312 auto", docx_spacing(first_url[7:])[:1], [("312", "auto")])
    h.close_document(doc)

    doc = h.office.load(first_url)
    h.wait_idle(2)
    got = first_paragraph(doc).ParaLineSpacing
    c.equal("line spacing: DOCX 312 opens as 130 %", (int(got.Mode), got.Height), (PROP, 130))
    dlg = h.open_dialog(".uno:ParagraphDialog", WRITER_DIALOG)
    c.equal("line spacing: DOCX 312 shows 1,30", shown(dlg), (str(MULTIPLE), "1,30"))
    click(dlg, "ok")
    h.wait_idle()
    doc.storeToURL(second_url, props(FilterName="MS Word 2007 XML"))
    c.equal("line spacing: DOCX saved again keeps 312", docx_spacing(second_url[7:])[:1], [("312", "auto")])
    h.close_document(doc)


def shape_document(h, kind):
    """A document of `kind` with one text shape at 130 % "Multiple", selected."""
    from com.sun.star.awt import Point, Size
    doc = h.new_document(kind)
    page = doc.getDrawPages().getByIndex(0)
    shape = doc.createInstance("com.sun.star.drawing.RectangleShape")
    page.add(shape)
    shape.setPosition(Point(3000, 3000))
    shape.setSize(Size(9000, 4000))
    shape.setString("Giãn dòng kiểu Word.")
    shape.ParaLineSpacing = line_spacing(PROP, 130)
    doc.getCurrentController().select(shape)
    h.wait_idle(1.5)
    return doc, shape


def check_line_spacing_others(h, c):
    # Sheets shares the page but opens it only inside a shape's text, which the svp UITest run cannot enter
    # reliably; it is checked by hand (plans/reports/fullstack-261123-1115-line-spacing-multiple.md).
    for kind in ("simpress", "sdraw"):
        doc, shape = shape_document(h, kind)
        dlg = h.open_dialog(".uno:ParagraphDialog", "DrawParagraphPropertiesDialog")
        c.equal(f"line spacing {kind}: 130 % shows Multiple 1,30", shown(dlg), (str(MULTIPLE), "1,30"))
        type_multiple(dlg, "1.5")
        h.wait_idle()
        got = shape.ParaLineSpacing
        c.equal(f"line spacing {kind}: typed 1.5 applied", (int(got.Mode), got.Height), (PROP, 150))
        h.close_document(doc)
