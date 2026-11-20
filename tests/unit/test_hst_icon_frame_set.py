# SPDX-License-Identifier: AGPL-3.0-only
"""The HST frame glyphs (stage-frame) and the frame inventory they are drawn for.

* metadata/frame-inventory.json lists frame elements only (never menu items, which keep the
  LibreOffice icons), each with a known owner phase and a `needs` verdict consistent with what
  Colibre and the HST themes draw;
* every stage-frame master and hand-tuned 16 px master passes the hst-modern spec, and every glyph
  used at 16 px has a hand-tuned master;
* every glyph ships at 16/24/32 px and as @150/@250 variants, in the light and dark theme, crisp
  (fringe), unclipped and as heavy as the pen of its scale (check-hst-icon-weight.measure);
* no two glyphs ship the same 16 px raster;
* beside the Colibre icons of the same surface (hst_icon_frame_compare.NEIGHBOURS) no glyph is
  smaller, thinner, lighter, heavier or softer than its neighbours at any size and display scale
  (needs rsvg-convert and the pristine LibreOffice tree in HST_LO_TREE);
* every glyph has a provenance record (meaning, method, masters) and the provenance names no other
  product's icons.
"""
import importlib.util
import json
from pathlib import Path
import os
import re
import shutil
import sys
import unittest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts/brand"))
import hst_modern_icons as modern  # noqa: E402
import hst_icon_frame_sheet as sheet  # noqa: E402
from hst_icon_frame_glyphs import NATIVE, NEIGHBOURS, SNAPPED_AT_16, native_masters, sizes_of  # noqa: E402
from hst_icon_lattice import BASE_PEN, target_pen  # noqa: E402

INVENTORY = modern.MODERN / "metadata/frame-inventory.json"
PROVENANCE = modern.MODERN / "metadata/frame-provenance.json"
STAGE = sheet.STAGE
FOREIGN = re.compile(r"\b(microsoft|office ?365|fluent|material|google|apple|sf symbols|colibre|breeze|"
                     r"font ?awesome|icons8|feather|lucide|tabler)\b", re.I)


def masters():
    return sorted(p.stem for p in STAGE.glob("*.svg"))


def load_weight_check():
    spec = importlib.util.spec_from_file_location("hst_weight_check", ROOT / "scripts/brand/check-hst-icon-weight.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class InventoryTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.data = json.loads(INVENTORY.read_text(encoding="utf-8"))
        cls.elements = cls.data["elements"]

    def test_ids_are_unique_and_groups_have_their_owner_phase(self):
        ids = [e["id"] for e in self.elements]
        self.assertEqual(len(ids), len(set(ids)))
        owners = {"backstage": "03", "sidebar": "04", "statusbar": "05", "doctabs": "07"}
        for element in self.elements:
            self.assertEqual(owners[element["group"]], element["owner_phase"], element["id"])

    def test_menu_items_are_not_frame_elements(self):
        for element in self.elements:
            self.assertNotRegex(element["source"], r"/(popupmenu|menubar)/", element["id"])

    def test_needs_follows_from_what_colibre_and_hst_draw(self):
        for element in self.elements:
            images, drawn = element["images"], element["drawn_by"]
            if drawn == "vector":
                expected = "draw"
            elif drawn == "none":
                expected = "none"
            elif any(not i["colibre_svg"] for i in images):
                expected = "draw"
            else:
                expected = "none" if all(i["hst_glyph"] for i in images) else "modern-only"
            self.assertEqual(expected, element["needs"], element["id"])
            self.assertTrue(all(not i["classic_shows_hst"] or i["hst_glyph"] for i in images), element["id"])

    def test_counts_match_the_elements(self):
        counts = {}
        for element in self.elements:
            counts[element["needs"]] = counts.get(element["needs"], 0) + 1
        self.assertEqual(counts, self.data["counts"])


@unittest.skipUnless(masters(), "no stage-frame glyphs yet")
class GlyphTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.names = masters()
        cls.files = {theme: {name: sheet.shipped(name, theme) for name in cls.names} for theme in sheet.THEMES}

    def test_masters_pass_the_spec(self):
        for name in self.names:
            self.assertEqual({}, sheet.violations(name), name)

    def test_glyphs_shown_at_16_px_have_a_hand_tuned_master(self):
        for name in self.names:
            if 16 in sizes_of(name) and name not in SNAPPED_AT_16:
                self.assertTrue((STAGE / "16" / f"{name}.svg").is_file(), name)
        orphans = {p.stem for p in (STAGE / "16").glob("*.svg")} - set(self.names)
        self.assertEqual(set(), orphans)

    def test_native_glyphs_pass_the_spec_at_their_image_size(self):
        inventory = {i["request"][:-4]: i["colibre_size"] for e in json.loads(INVENTORY.read_text())["elements"]
                     for i in e["images"]}
        for name in native_masters(STAGE):
            self.assertIn(name, NATIVE)
            self.assertEqual({}, sheet.native_violations(name), name)
            size = list(sheet.native_size((STAGE / "native" / f"{name}.svg").read_text(encoding="utf-8")))
            self.assertEqual(inventory[NATIVE[name]], size, name)

    def test_every_size_and_scale_variant_ships(self):
        expected = {f"{prefix}{{}}{suffix}.svg" for prefix in sheet.PREFIX.values() for suffix in ("", "@150", "@250")}
        for theme in sheet.THEMES:
            for name in self.names:
                self.assertEqual({e.format(name) for e in expected}, set(self.files[theme][name]), (theme, name))

    def test_shipped_files_are_crisp_unclipped_and_of_the_pen_weight(self):
        weight = load_weight_check()
        for theme in sheet.THEMES:
            ink = modern.ink()["dark" if sheet.THEMES[theme] else "light"]
            flat = {k: v.encode("utf-8") for name in self.names for k, v in self.files[theme][name].items()}
            for key, icon in weight.measure_theme(flat, ink).items():
                with self.subTest(theme=theme, icon=key):
                    self.assertLessEqual(icon["overflow"], 0.01)
                    self.assertLessEqual(icon["fringe"], weight.MAX_FRINGE)
                    pen = target_pen(BASE_PEN, icon["size"], icon["scale"] / 100)
                    self.assertLessEqual(icon["stroke"], 1.5 * pen)

    def test_no_two_glyphs_ship_the_same_16_px_icon(self):
        shipped = {}
        for name in self.names:
            text = self.files["hst"][name][f"cmd/sc_{name}.svg"]
            body = re.sub(r"<title>.*?</title>|<desc>.*?</desc>", "", text, flags=re.S)
            self.assertNotIn(body, shipped, f"{name} duplicates {shipped.get(body)}")
            shipped[body] = name

    def test_every_glyph_has_provenance(self):
        provenance = json.loads(PROVENANCE.read_text(encoding="utf-8"))
        self.assertEqual(set(self.names) | set(native_masters(STAGE)), set(provenance["glyphs"]))
        self.assertIsNone(FOREIGN.search(json.dumps(provenance, ensure_ascii=False)))
        for name, record in provenance["glyphs"].items():
            for field in ("meaning", "method", "masters"):
                self.assertTrue(record.get(field), (name, field))
            for master in record["masters"]:
                self.assertTrue((modern.MODERN / "glyphs" / master).is_file(), (name, master))


LO_TREE = Path(os.environ.get("HST_LO_TREE", "/data/hst-upstream/libreoffice-26.8.3.1-pristine"))


@unittest.skipUnless(masters() and shutil.which("rsvg-convert") and (LO_TREE / "icon-themes/colibre_svg").is_dir(),
                     "needs stage-frame glyphs, rsvg-convert and the pristine tree (HST_LO_TREE)")
class CalibrationTest(unittest.TestCase):
    def test_glyphs_match_their_colibre_neighbours(self):
        import hst_icon_frame_compare as compare
        names = masters() + native_masters(STAGE)
        self.assertEqual([], sorted(set(names) - set(NEIGHBOURS)))
        report = compare.compare(names, compare.Colibre(LO_TREE / "icon-themes"))
        self.assertEqual({}, compare.outliers(report))


if __name__ == "__main__":
    unittest.main()
