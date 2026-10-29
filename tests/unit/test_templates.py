# SPDX-License-Identifier: AGPL-3.0-only
"""Test source contracts, actual archives and rejection of unsafe/tampered output."""
import copy
import importlib.util
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
from zipfile import ZipFile
import xml.etree.ElementTree as ET

BASE = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(BASE / "scripts"))
from templates.catalog import load, safe_formula, validate
from templates.odf import NS, package, q, read_json, xml
from templates.runtime_checks import fixture_copy
from templates.validation import check_archive


def script(name):
    spec = importlib.util.spec_from_file_location(name, BASE / "scripts" / (name + ".py"))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class TemplatesTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory(prefix="hst-template-unit-")
        cls.directory = Path(cls.temp.name)
        cls.catalog_path = BASE / "templates/catalog.json"
        cls.generator, cls.checker = script("generate-templates"), script("check-templates")
        cls.catalog, cls.sources = load(cls.catalog_path)
        cls.rules = read_json(BASE / "data/vietnamese/nd30.json")
        with patch.dict(os.environ, SOURCE_DATE_EPOCH="1767225600"):
            cls.generator.generate(cls.directory / "first", cls.catalog_path)

    @classmethod
    def tearDownClass(cls):
        cls.temp.cleanup()

    def test_all_eighteen_archives_and_catalog(self):
        manifest = self.checker.check(self.directory / "first", self.catalog_path)
        self.assertEqual(len(manifest["templates"]), 18)

    def test_rebuilds_are_byte_identical_and_epoch_controls_metadata(self):
        with patch.dict(os.environ, SOURCE_DATE_EPOCH="1767225600"):
            self.generator.generate(self.directory / "second", self.catalog_path)
        files = [p for p in (self.directory / "first").rglob("*") if p.is_file()]
        self.assertEqual(len(files), 37)
        for path in files:
            self.assertEqual(path.read_bytes(), (self.directory / "second" / path.relative_to(self.directory / "first")).read_bytes())
        with patch.dict(os.environ, SOURCE_DATE_EPOCH="1767312000"):
            self.generator.generate(self.directory / "later", self.catalog_path)
        with ZipFile(self.directory / "later/writer/cong-van.ott") as archive:
            self.assertIn(b"2026-01-02T00:00:00Z", archive.read("meta.xml"))
            self.assertEqual(archive.getinfo("mimetype").date_time, (2026, 1, 2, 0, 0, 0))

    def test_schema_rejects_unknown_fields_missing_layouts_and_decomposed_text(self):
        schema = read_json(BASE / "templates/schema.json")
        for mutate in [lambda d: d.update(unknown=True), lambda d: d.pop("paragraphs"),
                       lambda d: d.update(paragraphs=["Tie\u0302\u0301ng Vie\u0323\u0302t"])]:
            bad = copy.deepcopy(self.sources["cong-van"])
            mutate(bad)
            with self.assertRaises(ValueError):
                validate(bad, schema, schema)

    def test_external_formulas_rejected(self):
        for value in ['WEBSERVICE("https://example.invalid")', 'DDE("x";"y";"z")',
                      'HYPERLINK("file:///etc/passwd")', "['other.ods'#Sheet.A1]", "[.Z999]"]:
            with self.assertRaises(ValueError):
                safe_formula(value)
        safe_formula('IF([.B5]>0;SUM([.C5:.F5]);0)')

    def test_tampered_archives_rejected(self):
        entry = self.catalog["templates"][0]
        original = self.directory / "first" / entry["output"]
        with ZipFile(original) as archive:
            mime = archive.read("mimetype").decode()
            parts = {n: archive.read(n) for n in archive.namelist() if n not in {"mimetype", "META-INF/manifest.xml"}}
        for tag, attrs in [("office:scripts", {}), ("text:a", {q("xlink:href"): "https://example.invalid"})]:
            root = ET.fromstring(parts["content.xml"])
            ET.SubElement(root, q(tag), attrs)
            changed = {**parts, "content.xml": xml(root)}
            target = self.directory / "tampered.ott"
            package(target, mime, changed)
            with self.assertRaises(ValueError):
                check_archive(target, entry, self.sources[entry["id"]], self.rules)
        target = self.directory / "macro.ott"
        package(target, mime, {**parts, "Basic/script.xml": b"<macro/>"})
        with self.assertRaises(ValueError):
            check_archive(target, entry, self.sources[entry["id"]], self.rules)

    def test_fixture_edits_preserve_formulas_and_original_template(self):
        original = self.directory / "first/sheets/thu-chi.ots"
        before = original.read_bytes()
        changed = self.directory / "fixture.ots"
        fixture_copy(original, changed, inputs={"A5": {"date": "2026-01-01"}, "C5": 1000000})
        self.assertEqual(before, original.read_bytes())
        with ZipFile(changed) as archive:
            content = archive.read("content.xml")
            root = ET.fromstring(content)
            self.assertIn(b'xmlns:of=', content)
            self.assertIsNotNone(root.find(".//table:table-cell[@office:date-value='2026-01-01']", NS))
            self.assertEqual(len(root.findall(".//table:table-cell[@table:formula]", NS)), 8)
        with self.assertRaises(ValueError):
            fixture_copy(original, changed, inputs={"E5": 1})

    def test_sheet_fit_width_layout_keeps_header_footer_geometry(self):
        # Regression: fit-to-width plus the empty header/footer styles LibreOffice writes on
        # save printed a blank page after template -> ods -> pdf.
        for path in sorted((self.directory / "first/sheets").glob("*.ots")):
            with ZipFile(path) as archive:
                styles = ET.fromstring(archive.read("styles.xml"))
            layout = styles.find(".//style:page-layout[@style:name='SheetPage']", NS)
            props = layout.find("style:page-layout-properties", NS)
            self.assertEqual(props.get(q("style:scale-to-X")), "1", path.name)
            with ZipFile(path) as archive:
                settings = ET.fromstring(archive.read("settings.xml"))
                body = ET.fromstring(archive.read("content.xml"))
            for cell in body.iterfind(".//table:table-cell[@table:formula]", NS):
                self.assertIsNone(cell.get(q("office:value")), path.name + ": stored result blocks recalculation")
            items = {i.get(q("config:name")): i.text for i in settings.iter(q("config:config-item"))}
            self.assertEqual((items["VerticalSplitMode"], items["VerticalSplitPosition"]), ("2", "4"), path.name)
            for part in ("header", "footer"):
                box = layout.find(f"style:{part}-style/style:header-footer-properties", NS)
                self.assertIsNotNone(box, f"{path.name}: {part} geometry missing")
                self.assertTrue(box.get(q("fo:min-height")), path.name)

    def test_number_formats_follow_frozen_contract(self):
        with ZipFile(self.directory / "first/sheets/du-toan.ots") as archive:
            styles = ET.fromstring(archive.read("styles.xml"))
        money = styles.find(".//number:currency-style", NS)
        self.assertEqual(money.get(q("number:language")), "vi")
        self.assertEqual(money.findtext("number:currency-symbol", namespaces=NS), "₫")
        self.assertEqual(money.find("number:number", NS).get(q("number:decimal-places")), "0")
        percent = styles.find(".//number:percentage-style/number:number", NS)
        self.assertEqual(percent.get(q("number:decimal-places")), "2")


if __name__ == "__main__":
    unittest.main()
