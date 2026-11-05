# SPDX-License-Identifier: AGPL-3.0-only
"""Compare the values Excel stored with a hard recalculation by HST.

For .xlsm/.xlsb the stored value is read from the file itself where it can be (sheet XML), so the comparison does not depend on what HST
kept at load; for .xls it is the value at load, which HST takes from the file. Cells whose formula calls a macro function (UDF) are counted apart.
"""
import re
import xml.etree.ElementTree as ET
import zipfile

MAIN = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"
REL = "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}"
PKG = "{http://schemas.openxmlformats.org/package/2006/relationships}"
CELL = re.compile(r"^([A-Z]+)(\d+)$")


def stored_values(path):
    """{(sheet name, column, row): (type, value)} of the formula cells in an OOXML workbook; {} when not one."""
    try:
        package = zipfile.ZipFile(path)
        rels = {r.get("Id"): r.get("Target") for r in ET.fromstring(package.read("xl/_rels/workbook.xml.rels")).iter(PKG + "Relationship")}
        book = ET.fromstring(package.read("xl/workbook.xml"))
    except (zipfile.BadZipFile, KeyError, ET.ParseError):
        return {}
    out = {}
    for sheet in book.iter(MAIN + "sheet"):
        target = rels.get(sheet.get(REL + "id"), "")
        name = target.lstrip("/") if target.startswith("/") else "xl/" + target
        try:
            root = ET.fromstring(package.read(name))
        except (KeyError, ET.ParseError):
            continue
        for cell in root.iter(MAIN + "c"):
            formula, value = cell.find(MAIN + "f"), cell.find(MAIN + "v")
            match = CELL.match(cell.get("r", ""))
            if formula is None or value is None or not match:
                continue
            column = 0
            for char in match.group(1):
                column = column * 26 + ord(char) - 64
            out[(sheet.get("name"), column - 1, int(match.group(2)) - 1)] = (cell.get("t", "n"), value.text or "")
    return out


def same_stored(stored, cell):
    kind, value = stored
    if kind == "n":
        try:
            number = float(value)
        except ValueError:
            return False
        return abs(cell.getValue() - number) <= 1e-9 * max(1.0, abs(number))
    if kind == "b":
        return cell.getValue() == float(value)
    if kind == "e":
        return cell.getError() != 0
    return cell.getString() == value


def compare_recalc(doc, path, udf_names):
    udf = re.compile(r"\b(" + "|".join(re.escape(n) for n in udf_names) + r")\s*\(", re.I) if udf_names else None
    stored = stored_values(path)
    cells = []
    sheets = doc.Sheets
    for index in range(sheets.Count):
        sheet = sheets.getByIndex(index)
        enum = sheet.queryContentCells(16).getCells().createEnumeration()  # CellFlags.FORMULA
        count = 0
        while enum.hasMoreElements() and count < 5000:
            cells.append((sheet.Name, enum.nextElement()))
            count += 1
    before = [(c.getString(), c.getValue(), c.getError()) for _s, c in cells]
    doc.calculateAll()
    result = dict(formula_cells=len(cells), udf_cells=0, from_file=0, differ=0, udf_differ=0, diffs=[])
    for (sheet, cell), old in zip(cells, before):
        address = cell.getCellAddress()
        is_udf = bool(udf and udf.search(cell.getFormula()))
        result["udf_cells"] += is_udf
        key = (sheet, address.Column, address.Row)
        if key in stored:
            result["from_file"] += 1
            same = same_stored(stored[key], cell)
            shown = stored[key][1]
        else:
            same = old[2] == cell.getError() and (old[0] == cell.getString() or abs(old[1] - cell.getValue()) <= 1e-9 * max(1.0, abs(old[1])) and old[1] != 0)
            shown = old[0]
        if not same:
            result["differ"] += 1
            result["udf_differ"] += is_udf
            if len(result["diffs"]) < 12:
                result["diffs"].append(dict(sheet=sheet, col=address.Column, row=address.Row, formula=cell.getFormula()[:100], stored=str(shown)[:50], now=cell.getString()[:50], err=cell.getError(), udf=is_udf))
    return result
