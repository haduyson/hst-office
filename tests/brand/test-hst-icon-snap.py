# SPDX-License-Identifier: AGPL-3.0-only
"""Pixel snapping of the HST glyphs: whole-pixel pens, lattice geometry, outlines, tuned masters."""
import json
from pathlib import Path
import re
import sys
import unittest
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts/brand"))
import hst_icon_outline as outline  # noqa: E402
import hst_icon_snap as snap  # noqa: E402

SOURCE = ROOT / "icon-themes-src/hst"
NS = "{http://www.w3.org/2000/svg}"
EXTENSION_TAB = {"convertencoding", "numbertowords", "formatdate", "formatvnd", "importcsv", "removediacritics",
                 "splitname", "sortbygivenname", "deleteblankrows", "showsolutions"}


def master(body):
    return ('<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24">'
            '<g fill="none" stroke="currentColor" stroke-width="1.65" stroke-linecap="round" '
            f'stroke-linejoin="round">{body}</g></svg>')


def numbers(data):
    return [float(v) for v in re.findall(r"[-+]?(?:\d+\.?\d*|\.\d+)", data)]


class SnapTest(unittest.TestCase):
    def test_pens_are_whole_pixels_proportional_to_the_bold_24_px_pen(self):
        self.assertEqual([snap.target_pen(1.65, size) for size in (16, 24, 32)], [1, 2, 3])
        self.assertEqual(snap.target_pen(2.5, 24), 3)  # colour bars keep their extra weight
        self.assertEqual(snap.target_pen(0.4, 16), 1)  # never below one pixel

    def test_lines_land_on_the_pixel_lattice_of_their_pen(self):
        source = master('<path d="M3 4.4h18M6.2 3v17"/>')
        for size, offset in ((16, 0.5), (24, 0.0), (32, 0.5)):
            draft = ET.fromstring(snap.snap_svg(source, size, outline=False))
            path = draft.find(f"{NS}g/{NS}path")
            self.assertEqual(path.get("stroke-width"), str(snap.TARGET_PEN[size]))
            for value in numbers(path.get("d")):
                self.assertAlmostEqual(value % 1, offset, msg=f"{size}: {path.get('d')}")

    def test_rect_and_circle_edges_fall_on_pixel_edges(self):
        source = master('<rect x="3" y="3" width="11" height="11" rx="1"/><circle cx="17" cy="17" r="3"/>')
        for size in (16, 24, 32):
            pen = snap.TARGET_PEN[size]
            group = ET.fromstring(snap.snap_svg(source, size, outline=False)).find(f"{NS}g")
            rect, circle = group.find(f"{NS}rect"), group.find(f"{NS}circle")
            for edge in (float(rect.get("x")) - pen / 2, float(rect.get("x")) + float(rect.get("width")) + pen / 2):
                self.assertAlmostEqual(edge % 1, 0.0)
            outer = float(circle.get("cx")) - float(circle.get("r")) - pen / 2
            self.assertAlmostEqual(outer % 1, 0.0)

    def test_badge_transforms_are_flattened_with_their_pen(self):
        # The construction desk compensates badge scaling with a heavier pen (1.65 / .75 = 2.2).
        source = master('<g transform="translate(0 0) scale(.75)" stroke-width="2.2"><path d="M4 4h12"/></g>')
        draft = snap.snap_svg(source, 24, outline=False)
        self.assertNotIn("transform", draft)
        self.assertIn('stroke-width="2"', draft)

    def test_shipped_output_is_fill_only_and_deterministic(self):
        source = (SOURCE / "glyphs/stage-1/paste.svg").read_text()
        for size in (16, 24, 32):
            svg = snap.snap_svg(source, size)
            self.assertEqual(svg, snap.snap_svg(source, size))
            root = ET.fromstring(svg)
            self.assertEqual(root.get("viewBox"), f"0 0 {size} {size}")
            for element in root.iter():
                self.assertIsNone(element.get("stroke"), "VCL offsets strokes by half a device pixel")
                self.assertIsNone(element.get("transform"))

    def test_arcs_survive_a_non_uniform_transform(self):
        source = master('<g transform="translate(4 0) scale(.8 1)"><path d="M13 13H9A5 5 0 0 1 9 3h11"/></g>')
        draft = snap.snap_svg(source, 24, outline=False)
        self.assertIn("C", ET.fromstring(draft).find(f"{NS}g/{NS}path").get("d"))

    def test_outline_parts_never_overlap_inside_one_path(self):
        # VCL fills multi-contour paths even-odd: a shaft ending in an arrow head must not put
        # two overlapping contours (or two discs on one point) into the same <path>.
        parts = outline.stroke_path(snap.parse_path("M2 8H14M11 5 14 8 11 11"), 1)
        discs = [p for p in parts if "A" in p]
        self.assertEqual(len(discs), len(set(discs)))
        for part in parts:
            self.assertEqual(part.count("M"), 1)

    def test_tiny_dots_become_solid_squares(self):
        svg = snap.snap_svg(master('<circle cx="3.5" cy="5" r=".9"/>'), 16)
        self.assertNotIn("A", ET.fromstring(svg).find(f"{NS}path").get("d"))

    def test_every_master_snaps_at_every_size(self):
        for path in sorted((SOURCE / "glyphs").glob("stage-*/*.svg")):
            if path.parent.name in ("stage-1-16", "stage-1-24"):
                continue
            for size in (16, 24, 32):
                snap.snap_svg(path.read_text(), size)

    def test_home_and_quick_access_families_have_hand_tuned_16_px_masters(self):
        families = json.loads((SOURCE / "metadata/families.json").read_text())
        home = {f["glyph"] for f in families if f["stage"] == 1 and not f.get("skip") and not f.get("trademark")
                and f["glyph"] not in EXTENSION_TAB}
        tuned = {p.stem for p in (SOURCE / "glyphs/stage-1-16").glob("*.svg")}
        self.assertEqual(len(home), 78)
        self.assertEqual(tuned, home)
        for name in sorted(tuned):
            text = (SOURCE / "glyphs/stage-1-16" / f"{name}.svg").read_text()
            root = ET.fromstring(text)
            self.assertEqual(root.get("viewBox"), "0 0 16 16", name)
            self.assertIn("CC-BY-4.0", text)
            snap.snap_svg(text, 16, native=True)  # whole-pixel pens or SnapError
        with self.assertRaises(snap.SnapError):
            snap.snap_svg(master('<path d="M1 1h4"/>').replace("0 0 24 24", "0 0 16 16"), 16, native=True)


if __name__ == "__main__":
    unittest.main()
