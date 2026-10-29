# SPDX-License-Identifier: AGPL-3.0-only
"""Independent checks of generated archive structure, links and document contracts."""
import hashlib
import re
import unicodedata
from pathlib import PurePosixPath
from zipfile import ZIP_STORED, ZipFile
import xml.etree.ElementTree as ET
from .catalog import safe_formula
from .odf import MIME, NS, q


def require(condition, message):
    if not condition:
        raise ValueError(message)


def check_archive(path, entry, source, rules):
    with ZipFile(path) as archive:
        names = archive.namelist()
        require(names[0] == "mimetype", "mimetype must be first")
        require(archive.getinfo("mimetype").compress_type == ZIP_STORED, "mimetype must be stored")
        require(not archive.getinfo("mimetype").extra, "mimetype must not have ZIP extra fields")
        require(names[1:] == sorted(names[1:]) and len(names) == len(set(names)), "ZIP order or duplicate entry")
        require(len({i.date_time for i in archive.infolist()}) == 1, "variable ZIP timestamps")
        require(archive.testzip() is None, "CRC mismatch")
        require(archive.read("mimetype").decode() == MIME[entry["module"]], "wrong ODF type")
        required = {"mimetype", "META-INF/manifest.xml", "content.xml", "styles.xml", "meta.xml"}
        allowed = required | ({"settings.xml"} if entry["module"] == "sheets" else set())
        if entry["module"] == "slides":
            allowed.add("Chart1/content.xml")
        require(set(names) == allowed, "unexpected or missing archive members (macros/fonts forbidden)")
        trees = {}
        for name in names[1:]:
            raw = archive.read(name).decode("utf-8")
            require(unicodedata.normalize("NFC", raw) == raw and "\ufffd" not in raw, "damaged Unicode")
            require("<!DOCTYPE" not in raw and "<!ENTITY" not in raw, "DTD/entities forbidden")
            root = trees[name] = ET.fromstring(raw)
            for item in root.iter():
                local = item.tag.rsplit("}", 1)[-1].lower()
                require(local not in {"script", "scripts", "event-listener", "event-listeners", "font-face-uri"}, "active content or embedded font")
                for key, value in item.attrib.items():
                    if key == q("table:formula"):
                        require(value.startswith("of:="), "formula namespace missing")
                        safe_formula(value[4:])
                    if key == q("xlink:href"):
                        target = value.removeprefix("./")
                        require(not re.match(r"^[a-zA-Z][a-zA-Z0-9+.-]*:", value), "external link")
                        require(not PurePosixPath(target).is_absolute() and ".." not in PurePosixPath(target).parts, "unsafe link")
                        require(target in names or target + "/content.xml" in names, "broken embedded reference")
        manifest = {n.get(q("manifest:full-path")): n.get(q("manifest:media-type"))
                    for n in trees["META-INF/manifest.xml"]}
        require(manifest.get("/") == MIME[entry["module"]], "manifest MIME mismatch")
        require(set(names) - {"mimetype", "META-INF/manifest.xml"} <= manifest.keys(), "missing manifest member")
        meta = trees["meta.xml"]
        require(meta.findtext(".//meta:generator", namespaces=NS) == "HST Office template generator", "generator mismatch")
        require(meta.findtext(".//dc:title", namespaces=NS) == entry["title"]["vi"], "Vietnamese title mismatch")
        content, styles = trees["content.xml"], trees["styles.xml"]
        require("[" in "".join(content.itertext()), "editable placeholders missing")
        if entry["module"] == "writer":
            check_writer(content, styles, source, rules)
        elif entry["module"] == "sheets":
            check_sheet(content, trees["settings.xml"], source)
        else:
            check_slides(content, styles, source)
    return hashlib.sha256(path.read_bytes()).hexdigest()


def check_writer(content, styles, source, rules):
    for layout in styles.findall(".//style:page-layout-properties", NS):
        size = rules["pageSizeMm"]
        require(layout.get(q("fo:page-width")) == f'{size["width"]}mm', "Writer page width")
        require(layout.get(q("fo:page-height")) == f'{size["height"]}mm', "Writer page height")
        for side, value in rules["defaultMarginsMm"].items():
            require(layout.get(q("fo:margin-" + side)) == f"{value}mm", "Writer margin " + side)
    table = content.find(".//table:table", NS)
    require(len(table.findall("table:table-column", NS)) == 2, "Writer header columns")
    require(styles.find(".//style:font-face[@style:name='Times New Roman']", NS) is not None, "Writer font declaration")
    first = styles.find(".//style:master-page[@style:name='FirstPage']", NS)
    require(first is not None and first.find("style:header", NS) is None, "first-page number must be hidden")
    require(styles.find(".//text:page-number", NS) is not None, "subsequent page number missing")
    title = content.find(".//text:p[@text:style-name='TypeName']", NS)
    official = source["id"] == "cong-van"
    require((title is None) == official, "official-letter title layout")
    require(len(content.findall(".//draw:line", NS)) == (2 if official else 3), "ND30 rules missing")
    require(all(line in "".join(content.itertext()) for line in source["paragraphs"]), "Writer body missing")


def check_sheet(content, settings, source):
    sheet = content.find(".//table:table", NS)
    require(sheet.get(q("table:name")) == source["sheetName"], "sheet name")
    require(sheet.get(q("table:print-ranges")), "print area missing")
    headers = sheet.find("table:table-header-rows", NS)
    require(headers is not None and len(headers) == 4, "repeated headings missing")
    formulas = content.findall(".//table:table-cell[@table:formula]", NS)
    expected = source["rows"] * sum("formula" in c for c in source["columns"]) + len(source["totals"])
    require(len(formulas) == expected, "formula count mismatch")
    values = {e.get(q("config:name")): e.text for e in settings.iter(q("config:config-item"))}
    require(values.get("VerticalSplitMode") == "2" and values.get("VerticalSplitPosition") == "4", "frozen header missing")


def check_slides(content, styles, source):
    pages = content.findall(".//office:presentation/draw:page", NS)
    require(len(pages) == len(source["slides"]), "slide count")
    layouts = styles.findall(".//style:presentation-page-layout", NS)
    require(len(layouts) == 5, "five reusable layouts required")
    require(len(styles.findall(".//style:master-page", NS)) == 2, "slide masters missing")
    size = styles.find(".//style:page-layout[@style:name='Wide']/style:page-layout-properties", NS)
    require(size.get(q("fo:page-width")) == "320mm" and size.get(q("fo:page-height")) == "180mm", "16:9 required")
    for page, authored in zip(pages, source["slides"]):
        require(authored["notes"] in "".join(page.find("presentation:notes", NS).itertext()), "speaker notes lost")
        require(authored["title"] in "".join(page.itertext()), "Vietnamese slide title lost")
