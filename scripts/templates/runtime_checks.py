# SPDX-License-Identifier: AGPL-3.0-only
"""Assert actual LibreOffice exports, never source-only claims of recalculation."""
import math
import re
import xml.etree.ElementTree as ET
from zipfile import ZipFile
from .odf import NS, package, q, xml
from .runtime_requirements import check_paragraphs, role
from .validation import require

W = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
X = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
P = "http://schemas.openxmlformats.org/presentationml/2006/main"
A = "http://schemas.openxmlformats.org/drawingml/2006/main"


def docx_paragraphs(root):
    """(style id, text) of every paragraph, table cells included; LibreOffice keeps the ODF style name as the id."""
    out = []
    for p in root.iter(f"{{{W}}}p"):
        style = p.find(f"{{{W}}}pPr/{{{W}}}pStyle")
        out.append((style.get(f"{{{W}}}val") if style is not None else "", "".join(t.text or "" for t in p.iter(f"{{{W}}}t"))))
    return out


def check_docx(path, spec):
    """Page and margins of the type (A4, or the envelope), then the blocks the type requires."""
    with ZipFile(path) as archive:
        root = ET.fromstring(archive.read("word/document.xml"))
        sections = root.findall(f".//{{{W}}}sectPr")
        require(sections, "DOCX sections missing")
        page = spec["page"]
        for section in sections:
            size, margins = section.find(f"{{{W}}}pgSz"), section.find(f"{{{W}}}pgMar")
            for key, mm in {"w": page["widthMm"], "h": page["heightMm"]}.items():
                require(abs(int(size.get(f"{{{W}}}{key}")) - mm * 1440 / 25.4) < 3, f"DOCX page size is not {page['widthMm']}x{page['heightMm']} mm")
            # OOXML w:top/w:bottom measure to the body text (ODF margin + header/footer
            # height), so check the text-area margin against the type's range, not one value.
            for side, (low, high) in spec["margins"].items():
                value_mm = int(margins.get(f"{{{W}}}{side}")) * 25.4 / 1440
                require(low - 0.1 <= value_mm <= high + 0.1, f"DOCX margin outside the type's range: {side}={value_mm:.1f}mm")
        check_paragraphs(docx_paragraphs(root), spec, "DOCX")


def _workbook(archive, name, frozen, *, fixed_print_area=True):
    """Sheet names, the worksheet named `name` and its cells, after the checks every exported sheet shares."""
    book = ET.fromstring(archive.read("xl/workbook.xml"))
    names = [sheet.get("name") for sheet in book.findall(f".//{{{X}}}sheet")]
    require(name in names, "XLSX Vietnamese sheet name lost: " + name)
    index = names.index(name)
    defined = {(n.get("name"), n.get("localSheetId")) for n in book.findall(f".//{{{X}}}definedName")}
    require(("_xlnm.Print_Titles", str(index)) in defined, "XLSX repeating print titles lost")
    has_print_area = ("_xlnm.Print_Area", str(index)) in defined
    require(has_print_area == fixed_print_area,
            "XLSX print area lost" if fixed_print_area else "XLSX register has a fixed print area that would truncate new entries")
    root = ET.fromstring(archive.read(f"xl/worksheets/sheet{index + 1}.xml"))  # LibreOffice writes the parts in sheet order
    pane = root.find(f".//{{{X}}}pane")
    # Headless --convert-to creates no view shell, and LibreOffice only writes <pane> from
    # live view data, so absence is not evidence of loss. A pane that is written must still
    # be the frozen heading; the ODF freeze itself is asserted on settings.xml in the unit tests.
    if pane is not None:
        require(pane.get("state") in {"frozen", "frozenSplit"} and float(pane.get("ySplit", 0)) == frozen, "XLSX frozen heading wrong")
    cells = {c.get("r"): c for c in root.findall(f".//{{{X}}}c")}
    for address, cell in cells.items():
        require(cell.get("t") != "e", "XLSX formula error at " + address)
    return names, root, cells


def check_xlsx(path, expected, sheet_name, frozen=4):
    with ZipFile(path) as archive:
        names, _root, cells = _workbook(archive, sheet_name, frozen)
        require(names[0] == sheet_name, "XLSX Vietnamese sheet name lost")
        for address, value in expected.items():
            cell = cells[address]
            require(cell.find(f"{{{X}}}f") is not None, "XLSX formula removed at " + address)
            cached = cell.findtext(f"{{{X}}}v")
            require(cached is not None and math.isclose(float(cached), value, rel_tol=1e-9, abs_tol=1e-8),
                    f"Recalculated {address}: expected {value}, got {cached}")


def check_register_xlsx(path, spec, source):
    """Annex IV register: cover and register sheets, the annex's column titles over their numbers (1), (2)..., landscape."""
    with ZipFile(path) as archive:
        names, root, cells = _workbook(archive, spec["sheet"], spec["frozenRows"], fixed_print_area=False)
        require(names == spec["sheets"], "XLSX register sheets: " + ", ".join(names))
        shared = ["".join(si.itertext()) for si in ET.fromstring(archive.read("xl/sharedStrings.xml"))]
        text = lambda address: shared[int(cells[address].findtext(f"{{{X}}}v"))] if address in cells and cells[address].get("t") == "s" else ""
        for index, column in enumerate(source["columns"]):
            letter = chr(65 + index)
            require(text(letter + "1") == column["title"] and text(letter + "2") == "(%d)" % (index + 1), "XLSX register heading lost at " + letter)
        require(source["coverTitle"] in shared, "XLSX register cover title lost")
        setup = root.find(f"{{{X}}}pageSetup")
        require(setup is not None and setup.get("orientation") == spec["orientation"] and setup.get("paperSize", "9") == "9", "XLSX register is not A4 " + spec["orientation"])


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


def fixture_copy(original, target, inputs=None, aspect=None, edit=None, marker=None, sheet=None):
    """Create explicit QA inputs in a copy; never mutate installed templates. `edit` is the paragraph role whose first
    placeholder becomes `marker`; `sheet` names the table `inputs` go to (the first one by default)."""
    with ZipFile(original) as archive:
        mime = archive.read("mimetype").decode()
        parts = {n: archive.read(n) for n in archive.namelist() if n not in {"mimetype", "META-INF/manifest.xml"}}
    content = ET.fromstring(parts["content.xml"])
    if edit:
        editable = next((p for p in content.iter(q("text:p")) if role(p.get(q("text:style-name"))) == edit and "[" in "".join(p.itertext())), None)
        require(editable is not None, f"No {edit} paragraph with a placeholder to edit")
        for child in list(editable):
            editable.remove(child)
        editable.text = marker
    if inputs is not None:
        content.set("xmlns:of", NS["of"])
        table = content.find(".//table:table" + (f"[@table:name='{sheet}']" if sheet else ""), NS)
        rows = list(table.find("table:table-header-rows", NS)) + table.findall("table:table-row", NS)
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
