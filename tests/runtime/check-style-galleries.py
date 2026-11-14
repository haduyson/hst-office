# SPDX-License-Identifier: AGPL-3.0-only
"""The picture and table style galleries' handler vnd.hst.styles: in Writer, Sheets and Slides (headless).

Usage: python3 tests/runtime/check-style-galleries.py --soffice PATH/program/soffice [--out DIR] [--port 7471]

For every picture style and every table style in every application: dispatches the style on a selected
picture / the table at the cursor, checks the native properties it must set and that it is one undo action.
Then saves .docx/.xlsx/.pptx, checks the OOXML (a:ln, a:outerShdw, cell fills, the custom Sheets table
style) and reloads the file to check the properties survived. Writes evidence.json; exit 1 on a failure.
"""
import argparse
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from headless_office import Office  # noqa: E402
import style_galleries_uno as sg  # noqa: E402


def check_picture(name, doc, office, obj, writer):
    for style in sg.PICTURE_IDS:
        colour, width, shadow = sg.PICTURES[style]
        before = sg.undo_count(doc)
        sg.dispatch(office, doc, "Picture", style)
        if writer:
            line, fmt = obj.TopBorder, obj.ShadowFormat
            ok = (line.LineWidth > 0) == (width > 0) and (not width or line.Color == colour)
            ok = ok and (fmt.Location.value != "NONE") == (shadow > 0)
            detail = (line.LineWidth, hex(line.Color), fmt.Location.value)
        else:
            ok = (obj.LineStyle.value == "SOLID") == (width > 0) and (not width or (
                obj.LineColor == colour and abs(obj.LineWidth - width) <= 1)) and obj.Shadow == (shadow > 0)
            detail = (obj.LineStyle.value, hex(obj.LineColor), obj.LineWidth, obj.Shadow, obj.ShadowBlur)
        sg.record(f"{name}: picture style {style} sets its properties", ok, detail)
        sg.record(f"{name}: picture style {style} is one undo action", sg.undo_count(doc) == before + 1)


def check_writer(office, work, png):
    doc = office.load("private:factory/swriter")
    picture = sg.writer_picture(office, doc, png)
    table = sg.writer_table(doc)
    controller = doc.getCurrentController()
    controller.select(picture)
    check_picture("Writer", doc, office, picture, True)
    sg.dispatch(office, doc, "Picture", "blue-shadow")
    controller.select(table.getCellByName("B3"))  # the cursor into the table (out of the picture)
    for style in sg.TABLE_IDS:
        header, band = sg.TABLES[style]
        sg.dispatch(office, doc, "Table", style)
        a1, a2 = table.getCellByName("A1"), table.getCellByName("A2")
        ok = table.TableTemplateName == style and (header is None or a1.BackColor == header)
        ok = ok and (band is None or a2.BackColor == band)
        bold = a1.getText().createTextCursor().CharWeight
        sg.record(f"Writer: table style {style} formats the cells", ok and bold >= 150,
                  (table.TableTemplateName, hex(a1.BackColor), hex(a2.BackColor), bold))
    sg.dispatch(office, doc, "Table", "HST Blue")
    path = os.path.join(work, "styles.docx")
    sg.store(office, doc, path, "MS Word 2007 XML")
    doc.close(True)
    xml = sg.part(path, "word/document.xml")
    sg.record("docx: the picture has an outline and an outer shadow", "<a:ln" in xml and "outerShdw" in xml)
    sg.record("docx: the header cells are filled HST blue", 'w:fill="0072BB"' in xml)
    doc = office.load(office.url(path))
    try:
        cell = doc.TextTables.getByIndex(0).getCellByName("A1")
        # a picture with an outline and a shadow comes back as a picture shape (writerfilter), still styled
        if doc.GraphicObjects.Count:
            pic = doc.GraphicObjects.getByIndex(0)
            look = (pic.TopBorder.Color, pic.ShadowFormat.Location.value != "NONE")
        else:
            pic = doc.DrawPage.getByIndex(0)
            look = (pic.LineColor, pic.Shadow)
        sg.record("docx reload: outline, shadow and header fill survive",
                  look == (0x0072BB, True) and cell.BackColor == 0x0072BB, (hex(look[0]), look[1], hex(cell.BackColor)))
        doc.getCurrentController().select(pic)
        before = sg.undo_count(doc)
        sg.dispatch(office, doc, "Picture", "thin")
        colour = pic.TopBorder.Color if doc.GraphicObjects.Count else pic.LineColor
        sg.record("docx reload: the reopened picture takes a style, one undo action",
                  colour == 0x7F8C99 and sg.undo_count(doc) == before + 1, hex(colour))
    finally:
        doc.close(True)


def check_sheets(office, work, png):
    doc = office.load("private:factory/scalc")
    sheet, table = sg.sheets_table(doc)
    picture = sg.shape_picture(office, doc, sheet.DrawPage, png)
    controller = doc.getCurrentController()
    controller.select(picture)
    check_picture("Sheets", doc, office, picture, False)
    sg.dispatch(office, doc, "Picture", "blue-shadow")
    controller.select(sheet.getCellRangeByName("B3"))
    for style in sg.TABLE_IDS:
        before = sg.undo_count(doc)
        sg.dispatch(office, doc, "Table", style)
        sg.record(f"Sheets: table style {style} is set, banded rows kept, one undo action",
                  table.TableStyleName == style and table.UseRowStripes and sg.undo_count(doc) == before + 1,
                  (table.TableStyleName, table.UseRowStripes))
    sg.dispatch(office, doc, "Table", "HST Blue")
    path = os.path.join(work, "styles.xlsx")
    sg.store(office, doc, path, "Calc Office Open XML")
    doc.close(True)
    styles, tables = sg.part(path, "xl/styles.xml"), sg.part(path, "xl/tables/")
    sg.record("xlsx: the custom table style HST Blue is written with its formats",
              re.search(r'<tableStyle [^>]*name="HST Blue"', styles) and "headerRow" in styles
              and "firstRowStripe" in styles and 'rgb="FF0072BB"' in styles)
    sg.record("xlsx: the table uses it", 'tableStyleInfo name="HST Blue"' in tables)
    drawing = sg.part(path, "xl/drawings/")
    sg.record("xlsx: the picture has an outline and an outer shadow", "<a:ln" in drawing and "outerShdw" in drawing)
    doc = office.load(office.url(path))
    names = doc.DatabaseRanges.getElementNames()
    style = doc.DatabaseRanges.getByName(names[0]).TableStyleName if names else None
    sg.record("xlsx reload: the table keeps HST Blue", style == "HST Blue", names)
    doc.close(True)


def check_slides(office, work, png):
    doc = office.load("private:factory/simpress")
    page = doc.DrawPages.getByIndex(0)
    while page.Count:
        page.remove(page.getByIndex(0))
    picture = sg.shape_picture(office, doc, page, png)
    table = sg.slides_table(doc, page)
    controller = doc.getCurrentController()
    controller.select(picture)
    check_picture("Slides", doc, office, picture, False)
    sg.dispatch(office, doc, "Picture", "blue-shadow")
    controller.select(table)
    for style in sg.TABLE_IDS:
        header, band = sg.TABLES[style]
        sg.dispatch(office, doc, "Table", style)
        model = table.Model
        h, b = model.getCellByPosition(0, 0), model.getCellByPosition(0, 1)
        ok = table.TableTemplate.Name == style and h.FillColor == (header if header is not None else 0xFFFFFF)
        sg.record(f"Slides: table style {style} formats the cells, header option kept",
                  ok and b.FillColor == (band if band is not None else 0xFFFFFF) and table.UseFirstRowStyle,
                  (table.TableTemplate.Name, hex(h.FillColor), hex(b.FillColor)))
    sg.dispatch(office, doc, "Table", "HST Blue")
    path = os.path.join(work, "styles.pptx")
    sg.store(office, doc, path, "Impress Office Open XML")
    doc.close(True)
    xml = sg.part(path, "ppt/slides/slide1.xml")
    pic = xml[xml.find("<p:pic>"):xml.find("</p:pic>")]
    sg.record("pptx: picture outline in plain HST blue and shadow, header cells HST blue",
              re.search(r'<a:ln [^>]*><a:solidFill><a:srgbClr val="0072BB"', pic) and "outerShdw" in pic
              and xml.count('srgbClr val="0072BB"') >= 2, pic[:400])
    doc = office.load(office.url(path))
    shapes = [doc.DrawPages.getByIndex(0).getByIndex(i) for i in range(doc.DrawPages.getByIndex(0).Count)]
    pics = [s for s in shapes if s.supportsService("com.sun.star.drawing.GraphicObjectShape")]
    tabs = [s for s in shapes if s.supportsService("com.sun.star.drawing.TableShape")]
    ok = pics and pics[0].LineColor == 0x0072BB and pics[0].Shadow and tabs and \
        tabs[0].Model.getCellByPosition(0, 0).FillColor == 0x0072BB
    sg.record("pptx reload: outline, shadow and header fill survive", ok,
              [(hex(p.LineColor), p.Shadow) for p in pics])
    doc.close(True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--soffice", required=True)
    parser.add_argument("--out", default="style-galleries-out")
    parser.add_argument("--port", type=int, default=7471)
    args = parser.parse_args()
    work = os.path.abspath(args.out)
    os.makedirs(work, exist_ok=True)
    png = os.path.join(work, "picture.png")
    sg.write_png(png)
    office = Office(args.soffice, work, args.port)
    try:
        for check in (check_writer, check_sheets, check_slides):
            try:
                check(office, work, png)
            except Exception as error:  # noqa: BLE001 - record and go on with the next application
                sg.record(f"{check.__name__} ran to the end", False, repr(error))
    finally:
        office.stop()
    with open(os.path.join(work, "evidence.json"), "w", encoding="utf-8") as handle:
        json.dump(sg.RESULTS, handle, ensure_ascii=False, indent=1)
    failed = [r for r in sg.RESULTS if not r["ok"]]
    print(f"{len(sg.RESULTS) - len(failed)}/{len(sg.RESULTS)} checks passed")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
