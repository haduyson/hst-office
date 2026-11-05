# SPDX-License-Identifier: AGPL-3.0-only
"""New-document part of check-defaults.py: real documents, not only the configuration."""
import os
import re
import zipfile


def check_new_documents(ctx, out):
    """Sheets 11 pt in new workbooks only, Writer stays Times New Roman 12; saved Office files name Calibri, not Carlito."""
    import uno
    from com.sun.star.beans import PropertyValue

    def prop(name, value):
        item = PropertyValue()
        item.Name, item.Value = name, value
        return item

    desktop = ctx.ServiceManager.createInstanceWithContext("com.sun.star.frame.Desktop", ctx)
    hidden = (prop("Hidden", True),)
    rows, failed = [], 0

    def expect(name, actual, wanted):
        nonlocal failed
        ok = actual == wanted
        failed += not ok
        rows.append((name, actual, ok))
        print(f"{'PASS' if ok else 'FAIL'}  {name}: {actual!r}")

    sheets = desktop.loadComponentFromURL("private:factory/scalc", "_blank", 0, hidden)
    style = sheets.getStyleFamilies().getByName("CellStyles").getByName("Default")
    expect("Sheets new workbook: default style 11 pt", style.CharHeight, 11.0)
    first = sheets.getSheets().getByIndex(0)
    height = first.getRows().getByIndex(0).Height
    expect("Sheets: empty rows follow the size", height > 452 and first.getRows().getByIndex(5000).Height == height, True)
    sheets.getSheets().insertNewByName("Hai", 1)
    expect("Sheets: a new sheet has the same rows", sheets.getSheets().getByName("Hai").getRows().getByIndex(0).Height, height)
    first.getCellByPosition(0, 0).setString("Xin chào")
    path = os.path.join(out, "new.xlsx")
    sheets.storeToURL(uno.systemPathToFileUrl(path), (prop("FilterName", "Calc MS Excel 2007 XML"),))
    sheets.close(True)
    with zipfile.ZipFile(path) as package:
        styles = package.read("xl/styles.xml").decode("utf-8")
    first_font = re.search(r"<font>.*?</font>", styles).group(0)
    expect("Sheets .xlsx: first font 11 pt", '<sz val="11"/>' in first_font, True)
    expect("Sheets .xlsx: names Calibri, not Carlito", "Calibri" in first_font and "Carlito" not in styles, True)
    # An older file that states 10 pt, and one saved as ODS at 10 pt, keep it.
    reopened = desktop.loadComponentFromURL(uno.systemPathToFileUrl(path), "_blank", 0, hidden)
    expect("Sheets: saved .xlsx reopens at 11 pt", reopened.getSheets().getByIndex(0).getCellByPosition(0, 0).CharHeight, 11.0)
    reopened.close(True)
    # The same .xlsx as a file made elsewhere at 10 pt: it keeps its size.
    ten = os.path.join(out, "ten.xlsx")
    with zipfile.ZipFile(path) as source, zipfile.ZipFile(ten, "w") as target:
        for name in source.namelist():
            data = source.read(name)
            target.writestr(name, data.replace(b'<sz val="11"/>', b'<sz val="10"/>') if name == "xl/styles.xml" else data)
    reopened = desktop.loadComponentFromURL(uno.systemPathToFileUrl(ten), "_blank", 0, hidden)
    expect("Sheets: a 10 pt .xlsx stays 10 pt", reopened.getSheets().getByIndex(0).getCellByPosition(0, 0).CharHeight, 10.0)
    reopened.close(True)
    older = desktop.loadComponentFromURL("private:factory/scalc", "_blank", 0, hidden)
    older.getStyleFamilies().getByName("CellStyles").getByName("Default").CharHeight = 10.0
    path = os.path.join(out, "older.ods")
    older.storeToURL(uno.systemPathToFileUrl(path), (prop("FilterName", "calc8"),))
    older.close(True)
    older = desktop.loadComponentFromURL(uno.systemPathToFileUrl(path), "_blank", 0, hidden)
    expect("Sheets: an existing 10 pt file stays 10 pt", older.getStyleFamilies().getByName("CellStyles").getByName("Default").CharHeight, 10.0)
    older.close(True)

    writer = desktop.loadComponentFromURL("private:factory/swriter", "_blank", 0, hidden)
    standard = writer.getStyleFamilies().getByName("ParagraphStyles").getByName("Standard")
    expect("Writer: Times New Roman 12", (standard.CharFontName, standard.CharHeight), ("Times New Roman", 12.0))
    writer.close(True)

    slides = desktop.loadComponentFromURL("private:factory/simpress", "_blank", 0, hidden)
    path = os.path.join(out, "new.pptx")
    slides.storeToURL(uno.systemPathToFileUrl(path), (prop("FilterName", "Impress MS PowerPoint 2007 XML"),))
    slides.close(True)
    with zipfile.ZipFile(path) as package:
        faces = {face for name in package.namelist() if name.endswith(".xml")
                 for face in re.findall(r'typeface="([^"]+)"', package.read(name).decode("utf-8", "replace"))}
    expect("Slides .pptx: names Calibri, not Carlito", "Calibri" in faces and "Carlito" not in faces, True)
    return failed, rows
