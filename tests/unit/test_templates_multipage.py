# SPDX-License-Identifier: AGPL-3.0-only
"""Fast checks of what keeps a long administrative document right page after page (no office needed).

The runtime check tests/runtime/check-templates-multipage.py measures real exports; these guard the causes it found:
a table carrying space Word cannot keep, a page break carried by a table (lost in .doc), an empty closing paragraph
that spills onto a blank last page, contact details after the signature (Decree 30 puts them on page 1), and a
register print range that stops printing the entries typed below it.
"""
import json
import os
import sys
import tempfile
import unittest
import xml.etree.ElementTree as ET
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "extensions/hst-vietnamese-tools/python"))
sys.path.insert(0, str(ROOT / "scripts"))
from hst_office.nd30 import get_type  # noqa: E402
from hst_office.nd30_layout import build_layout, portable_blocks  # noqa: E402

NS = {"style": "urn:oasis:names:tc:opendocument:xmlns:style:1.0", "fo": "urn:oasis:names:tc:opendocument:xmlns:xsl-fo-compatible:1.0",
      "table": "urn:oasis:names:tc:opendocument:xmlns:table:1.0", "text": "urn:oasis:names:tc:opendocument:xmlns:text:1.0",
      "office": "urn:oasis:names:tc:opendocument:xmlns:office:1.0"}
RULES = json.loads((ROOT / "tests/fixtures/templates/multipage.json").read_text(encoding="utf-8"))
WRITER_TYPES = [t for t in json.loads((ROOT / "templates/catalog.json").read_text(encoding="utf-8"))["templates"] if t["module"] == "writer"]


def q(name):
    prefix, local = name.split(":")
    return "{%s}%s" % (NS[prefix], local)


class PortableBlocks(unittest.TestCase):
    def layouts(self):
        for entry in WRITER_TYPES:
            ident = entry["id"]
            for template in (True, False):
                yield ident, build_layout(ident, template=template)

    def test_no_table_carries_space_or_a_page_break(self):
        for ident, layout in self.layouts():
            blocks, _ = portable_blocks(layout)
            for b in blocks:
                if b["type"] == "grid":
                    self.assertFalse(b.get("spacing_before_pt") or b.get("spacing_after_pt"), "%s: table spacing is lost in DOCX/DOC" % ident)
                    self.assertFalse(b.get("new_section"), "%s: a page break on a table is lost in DOC" % ident)

    def test_closing_table_keeps_with_the_end_paragraph(self):
        for ident, layout in self.layouts():
            blocks, _ = portable_blocks(layout)
            if blocks[-1]["type"] == "grid":
                last = blocks[-1]
                if last.get("name") != "Signature":
                    self.assertFalse(last.get("keep_with_next"), "%s: a register table must stay splittable in DOCX" % ident)
                    continue
                self.assertTrue(last.get("keep_with_next"), ident)
                cells = [p for cell in last["rows"][-1]["cells"] for p in cell]
                self.assertTrue(all(p.get("keep_with_next") for p in cells), "%s: Word keeps a table with the next paragraph only so" % ident)
                if len(last["rows"]) > 1:  # a register must still split: its other rows do not keep with next
                    self.assertFalse(any(p.get("keep_with_next") for cell in last["rows"][0]["cells"] for p in cell), ident)

    def test_minutes_keep_the_recipients_with_the_signatures(self):
        blocks, _ = portable_blocks(build_layout("bien-ban", template=True))
        index = next(i for i, b in enumerate(blocks) if b.get("name") == "Signature")
        self.assertTrue(blocks[index].get("keep_with_next"))
        received = [b for b in blocks[index + 1:] if b.get("role", "").startswith("Recipients")]
        self.assertTrue(all(b.get("keep_with_next") for b in received[:-1]))

    def test_signature_space_survives(self):
        """The 12 pt above the signature goes to a gap paragraph right before it, nothing is dropped. Not into its cells,
        where Writer keeps it at the top of a page, nor onto the body paragraph, which paragraphs typed after it copy."""
        layout = build_layout("quyet-dinh", template=True)
        index = next(i for i, b in enumerate(layout["blocks"]) if b.get("name") == "Signature")
        before, previous = layout["blocks"][index]["spacing_before_pt"], layout["blocks"][index - 1]
        blocks, _ = portable_blocks(layout)
        index = next(i for i, b in enumerate(blocks) if b.get("name") == "Signature")
        gap = blocks[index - 1]
        self.assertEqual((gap["role"], "".join(r["text"] for r in gap["runs"])), ("TableGap", ""))
        self.assertAlmostEqual(gap["line_exact_pt"] + gap["spacing_after_pt"], before)
        self.assertEqual(blocks[index - 2].get("spacing_after_pt"), previous.get("spacing_after_pt"))
        for cell in blocks[index]["rows"][0]["cells"]:
            self.assertFalse(cell[0].get("spacing_before_pt", 0))

    def test_official_letter_contact_goes_to_the_first_page_footer(self):
        """Decree 30, Annex I, Part I, III.4: contact details on the first page of the document."""
        for entry in WRITER_TYPES:
            t = get_type(entry["id"])
            blocks, footer = portable_blocks(build_layout(entry["id"], template=True))
            self.assertFalse(any(b.get("role") == "Contact" for b in blocks), entry["id"])
            if t.get("officialLetter") and t["profile"] in RULES["contactOnFirstPage"]:
                self.assertEqual([b["role"] for b in footer], ["Contact"], entry["id"])


class GeneratedTemplates(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        os.environ.setdefault("SOURCE_DATE_EPOCH", "1767225600")
        import subprocess
        subprocess.run([sys.executable, str(ROOT / "scripts/generate-templates.py"), "--out", cls.tmp.name], check=True, stdout=subprocess.DEVNULL)
        cls.out = Path(cls.tmp.name)
        cls.manifest = json.loads((cls.out / "manifest.json").read_text(encoding="utf-8"))

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def parts(self, entry):
        z = zipfile.ZipFile(self.out / entry["output"])
        return ET.fromstring(z.read("content.xml")), ET.fromstring(z.read("styles.xml"))

    def test_end_paragraph_after_a_closing_table_is_tiny(self):
        for entry in self.manifest["templates"]:
            if entry["module"] != "writer":
                continue
            content, styles = self.parts(entry)
            body = content.find("office:body/office:text", NS)
            last = list(body)[-1]
            if last.tag == q("table:table"):
                self.fail("%s ends in a table: Writer adds a full-size paragraph that can spill onto a blank page" % entry["id"])
            if len(list(body)) > 1 and list(body)[-2].tag == q("table:table") and not "".join(last.itertext()):
                self.assertEqual(last.get(q("text:style-name")), "DocumentEnd", entry["id"])
                style = styles.find(".//style:style[@style:name='DocumentEnd']/style:text-properties", NS)
                self.assertEqual(style.get(q("fo:font-size")), "1pt")

    def test_body_area_is_the_same_on_every_page(self):
        """One page layout; the bottom of the body stays at the bottom margin even with a first-page footer."""
        for entry in self.manifest["templates"]:
            if entry["module"] != "writer" or entry["id"] in RULES["singleSheet"]:
                continue
            _, styles = self.parts(entry)
            t = get_type(entry["id"])
            margins = RULES["profiles"][t["profile"]]["marginsMm"]
            layouts = styles.findall(".//style:page-layout", NS)
            self.assertEqual(len(layouts), 1, entry["id"])
            props = layouts[0].find("style:page-layout-properties", NS)
            footer = layouts[0].find("style:footer-style/style:header-footer-properties", NS)
            bottom = float(props.get(q("fo:margin-bottom"))[:-2]) + (float(footer.get(q("fo:min-height"))[:-2]) if footer is not None else 0)
            self.assertTrue(margins["bottom"][0] <= bottom <= margins["bottom"][1], entry["id"])
            if footer is not None:
                for master in styles.iter(q("style:master-page")):
                    self.assertIsNotNone(master.find("style:footer", NS), "%s: every page keeps the footer band" % entry["id"])

    def test_registers_print_every_entry(self):
        for entry in self.manifest["templates"]:
            if entry["module"] == "sheets" and entry["output"].startswith("van-thu/"):
                content, _ = self.parts(entry)
                book = [t for t in content.iter(q("table:table")) if t.get(q("table:name")) == "Sổ"][0]
                self.assertIsNone(book.get(q("table:print-ranges")), entry["id"])
                self.assertIsNotNone(book.find("table:table-header-rows", NS), entry["id"])


if __name__ == "__main__":
    unittest.main()
