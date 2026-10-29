# SPDX-License-Identifier: AGPL-3.0-only
"""Assert actual LibreOffice exports, never source-only claims of recalculation."""
import math
import re
import xml.etree.ElementTree as ET
from zipfile import ZipFile
from .odf import NS, package, q, xml
from .validation import require

W = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
X = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
P = "http://schemas.openxmlformats.org/presentationml/2006/main"
A = "http://schemas.openxmlformats.org/drawingml/2006/main"


def check_docx(path, rules):
    with ZipFile(path) as archive:
        root = ET.fromstring(archive.read("word/document.xml"))
        sections = root.findall(f".//{{{W}}}sectPr")
        require(sections, "DOCX sections missing")
        for section in sections:
            size, margins = section.find(f"{{{W}}}pgSz"), section.find(f"{{{W}}}pgMar")
            for key, mm in {"w": rules["pageSizeMm"]["width"], "h": rules["pageSizeMm"]["height"]}.items():
                require(abs(int(size.get(f"{{{W}}}{key}")) - mm * 1440 / 25.4) < 3, "DOCX A4 mismatch")
            # OOXML w:top/w:bottom measure to the body text (ODF margin + header/footer
            # height), so check the text-area margin against the ND30 range, not one value.
            for side, (low, high) in rules["marginRangesMm"].items():
                value_mm = int(margins.get(f"{{{W}}}{side}")) * 25.4 / 1440
                require(low - 0.1 <= value_mm <= high + 0.1, f"DOCX margin outside ND30 range: {side}={value_mm:.1f}mm")
        require("Độc lập" in "".join(root.itertext()), "DOCX Vietnamese text lost")


def check_xlsx(path, expected, sheet_name):
    with ZipFile(path) as archive:
        book = ET.fromstring(archive.read("xl/workbook.xml"))
        sheet = book.find(f".//{{{X}}}sheet")
        require(sheet.get("name") == sheet_name, "XLSX Vietnamese sheet name lost")
        names = {n.get("name") for n in book.findall(f".//{{{X}}}definedName")}
        require({"_xlnm.Print_Area", "_xlnm.Print_Titles"} <= names, "XLSX print ranges lost")
        root = ET.fromstring(archive.read("xl/worksheets/sheet1.xml"))
        pane = root.find(f".//{{{X}}}pane")
        # Headless --convert-to creates no view shell, and LibreOffice only writes <pane> from
        # live view data, so absence is not evidence of loss. A pane that is written must still
        # be the frozen 4-row heading; the ODF freeze itself is asserted on settings.xml in the
        # unit tests.
        if pane is not None:
            require(pane.get("state") in {"frozen", "frozenSplit"} and float(pane.get("ySplit", 0)) == 4, "XLSX frozen heading wrong")
        cells = {c.get("r"): c for c in root.findall(f".//{{{X}}}c")}
        for address, cell in cells.items():
            require(cell.get("t") != "e", "XLSX formula error at " + address)
        for address, value in expected.items():
            cell = cells[address]
            require(cell.find(f"{{{X}}}f") is not None, "XLSX formula removed at " + address)
            cached = cell.findtext(f"{{{X}}}v")
            require(cached is not None and math.isclose(float(cached), value, rel_tol=1e-9, abs_tol=1e-8),
                    f"Recalculated {address}: expected {value}, got {cached}")


def check_pptx(path, source, ratio=16 / 9):
    with ZipFile(path) as archive:
        root = ET.fromstring(archive.read("ppt/presentation.xml"))
        size = root.find(f"{{{P}}}sldSz")
        require(abs(int(size.get("cx")) / int(size.get("cy")) - ratio) < 0.001, "PPTX aspect ratio")
        names = archive.namelist()
        slides = sorted(n for n in names if re.fullmatch(r"ppt/slides/slide\d+\.xml", n))
        notes = [n for n in names if re.fullmatch(r"ppt/notesSlides/notesSlide\d+\.xml", n)]
        require(len(slides) == len(source["slides"]) and len(notes) == len(slides), "PPTX slide/notes count")
        require(any(n.startswith("ppt/slideMasters/slideMaster") for n in names), "PPTX master missing")
        require(any(n.startswith("ppt/charts/chart") and n.endswith(".xml") for n in names), "PPTX editable chart lost")
        all_notes = "".join("".join(ET.fromstring(archive.read(n)).itertext()) for n in notes)
        for name, slide in zip(slides, source["slides"]):
            text = "".join(ET.fromstring(archive.read(name)).itertext())
            require(slide["title"] in text and slide["notes"] in all_notes, "PPTX Vietnamese content lost")


def fixture_copy(original, target, inputs=None, aspect=None, edit_marker=None):
    """Create explicit QA inputs in a copy; never mutate installed templates."""
    with ZipFile(original) as archive:
        mime = archive.read("mimetype").decode()
        parts = {n: archive.read(n) for n in archive.namelist() if n not in {"mimetype", "META-INF/manifest.xml"}}
    content = ET.fromstring(parts["content.xml"])
    if edit_marker:
        editable = next(p for p in content.iter(q("text:p"))
                        if p.get(q("text:style-name")) == "Body" and p.text and "[" in p.text)
        editable.text = edit_marker
    if inputs is not None:
        content.set("xmlns:of", NS["of"])
        sheet = content.find(".//table:table", NS)
        rows = list(sheet.find("table:table-header-rows", NS)) + sheet.findall("table:table-row", NS)
        for address, value in inputs.items():
            match = re.fullmatch(r"([A-Z])(\d+)", address)
            cell = rows[int(match[2]) - 1].findall("table:table-cell", NS)[ord(match[1]) - 65]
            require(cell.get(q("table:formula")) is None, "fixture cannot overwrite a formula")
            for child in list(cell):
                cell.remove(child)
            if isinstance(value, dict):
                cell.set(q("office:value-type"), "date")
                cell.set(q("office:date-value"), value["date"])
            elif isinstance(value, str):
                cell.set(q("office:value-type"), "string")
                cell.attrib.pop(q("office:value"), None)
                ET.SubElement(cell, q("text:p")).text = value
            else:
                cell.set(q("office:value-type"), "float")
                cell.set(q("office:value"), str(value))
    if aspect:
        styles = ET.fromstring(parts["styles.xml"])
        size = styles.find(".//style:page-layout[@style:name='Wide']/style:page-layout-properties", NS)
        size.set(q("fo:page-height"), "240mm")
        parts["styles.xml"] = xml(styles)
    parts["content.xml"] = xml(content)
    package(target, mime, parts)
