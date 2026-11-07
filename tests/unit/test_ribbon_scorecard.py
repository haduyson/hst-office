# SPDX-License-Identifier: AGPL-3.0-only
"""Ribbon scorecard arithmetic and pixel probes (tests/runtime/ribbon_scorecard.py, ribbon_scorecard_pixels.py).

Fixture observations stand in for the live AT-SPI runs, so this needs no office and no display.
"""
import copy
import os
import sys
import unittest

from _paths import ROOT

sys.path.insert(0, os.path.join(ROOT, "tests", "runtime"))
import ribbon_scorecard as card  # noqa: E402

try:
    from PIL import Image, ImageDraw
    import ribbon_scorecard_pixels as px
except ImportError:  # pragma: no cover - Pillow is part of the test tool set
    Image = None

CONFIG = {"widths": [1485, 1366, 1024], "compact_below": 1280, "banner": {"right_gap": 373, "y": 46, "width": 360},
          "apps": {"writer": {"ribbon_height": 182, "banner_height": 125}},
          "weights": {"D1": 0.35, "D2": 0.15, "D3": 0.20, "D4": 0.10, "D5": 0.15, "D6": 0.05},
          "floors": {"D1": 0.90, "D2": 0.85, "D3": 0.85, "D4": 0.90, "D5": 0.75, "D6": 0.80}}


def group(caption, x, width):
    return {"caption": caption, "box": [x, 50, width, 117]}


def width_obs(groups, banner, chevron=None, height=182, buttons=()):
    return {"groups": groups, "banner": banner, "chevron": chevron, "height": height, "group_buttons": list(buttons)}


class ArithmeticTest(unittest.TestCase):
    def test_lcs_and_dedupe(self):
        self.assertEqual(card.lcs(list("ABCD"), list("ACBD")), 3)
        self.assertEqual(card.lcs([], list("AB")), 0)
        self.assertEqual(card.dedupe(["a", "a", "b", "a"]), ["a", "b", "a"])

    def test_structure(self):
        pages = [{"label": "Trang đầu", "groups": [{"caption": "Bảng tạm"}, {"caption": "Phông chữ"}]},
                 {"label": "Chèn", "groups": [{"caption": "Bảng"}]},
                 {"label": "Thiết kế Bảng", "groups": []}]
        spec = {"tabs": [
            {"hst_tab": "Trang đầu", "contextual": False, "groups": [{"hst_group": "Bảng tạm"}, {"hst_group": "Phông chữ"},
                                                                    {"hst_group": "Phông chữ"}, {"hst_group": None}]},
            {"hst_tab": "Chèn", "contextual": False, "groups": [{"hst_group": "Trang"}, {"hst_group": "Bảng"}]},
            {"hst_tab": "Trợ giúp", "contextual": False, "groups": [{"hst_group": "Trợ giúp"}]},
            {"hst_tab": "Thiết kế Bảng", "contextual": True, "groups": []},
            {"hst_tab": "Đầu trang & Chân trang", "contextual": True, "groups": []}]}
        score, detail = card.score_structure(spec, pages, ["Tệp tin", "Chèn", "Trang đầu"])
        # tabs: lcs([Trang đầu, Chèn, Trợ giúp], live) = 1; contextual 1/2; groups 2/2 + 1/2 + 0/1
        self.assertEqual(detail["tabs"], [1, 3])
        self.assertEqual(detail["contextual"], [1, 2])
        self.assertEqual(detail["groups"], [3, 5])
        self.assertEqual(score, round(5 / 10, 4))
        self.assertIn("Trợ giúp", detail["missing_tabs"])
        self.assertIn("Chèn / Trang", detail["missing_groups"])

    def test_scaling_checks(self):
        page = {
            "1485": width_obs([group("A", 10, 300), group("B", 320, 200)], [1112, 46, 360, 125]),
            "1366": width_obs([group("A", 10, 300), group("B", 320, 220)], [993, 46, 360, 125], chevron=[900, 90, 15, 36]),
            "1024": width_obs([group("A", 10, 300)], None, height=170)}
        rows = {(w, c): ok for w, c, ok, _d in card.scaling_checks(page, ["A", "B", "C"], CONFIG, "writer")}
        self.assertTrue(rows[(1485, "a")])
        self.assertTrue(rows[(1485, "b")])
        self.assertFalse(rows[(1485, "c")])  # C shows nowhere and there is no chevron
        self.assertTrue(rows[(1485, "d")])
        self.assertFalse(rows[(1366, "a")])  # chevron while groups still show their captions
        self.assertFalse(rows[(1366, "b")])  # B grew while the window narrowed
        self.assertTrue(rows[(1366, "c")])  # the chevron holds the rest
        self.assertTrue(rows[(1366, "d")])
        self.assertTrue(rows[(1024, "a")])
        self.assertTrue(rows[(1024, "b")])
        self.assertFalse(rows[(1024, "c")])  # B and C gone without a chevron
        self.assertFalse(rows[(1024, "d")])  # no compact banner, and the height changed

    def test_scaling_reachable_through_group_buttons_and_clipping(self):
        page = {"1485": width_obs([group("A", 10, 1200)], [1112, 46, 360, 125]),
                "1366": width_obs([], [993, 46, 360, 125], buttons=["A"]),
                "1024": width_obs([], [600, 46, 360, 107])}
        rows = {(w, c): ok for w, c, ok, _d in card.scaling_checks(page, ["A"], CONFIG, "writer")}
        self.assertFalse(rows[(1485, "c")])  # A runs under the banner
        self.assertTrue(rows[(1366, "c")])
        self.assertTrue(rows[(1024, "d")])  # compact banner inside the window, right of the groups

    def test_missing_widths_fail(self):
        rows = card.scaling_checks({}, ["A"], CONFIG, "writer")
        self.assertEqual(len(rows), 12)
        self.assertFalse(any(ok for _w, _c, ok, _d in rows))

    def probes(self, passing):
        return {name: {"pass": name in passing, "detail": ""} for name in card.PROBES}

    def test_total_is_the_weighted_mean_over_apps(self):
        pages = {"writer": [{"label": "Trang đầu", "groups": [{"caption": "A"}]}]}
        spec = {"apps": {"writer": {"tabs": [{"hst_tab": "Trang đầu", "contextual": False, "groups": [{"hst_group": "A"}]}]}}}
        light = {"tabs": ["Trang đầu"], "pages": {"Trang đầu": {
            "1485": width_obs([group("A", 10, 100)], [1112, 46, 360, 125]),
            "1366": width_obs([group("A", 10, 100)], [993, 46, 360, 125]),
            "1024": width_obs([group("A", 10, 100)], [600, 46, 360, 107])}},
            "probes": self.probes({"hover_fill", "paste_32"}),
            "gallery": {"rendered_previews": {"pass": True}, "four_columns": {"pass": False}}}
        dark = {"probes": self.probes({"hover_fill", "tab_underline", "pressed"})}
        per_app = {"writer": {"light": light, "dark": dark}}
        parity_report = {"writer": {"d1": 0.8, "d4": 0.5, "counts": {"present": 8, "elsewhere": 1, "missing": 1, "infeasible": 0},
                                    "raw_coverage": 0.8, "launchers_present": 1, "launchers_feasible": 2}}
        result = card.score(per_app, parity_report, pages, spec, CONFIG, apps=("writer",))
        dims = result["dimensions"]
        self.assertEqual(dims["D1"], 0.8)
        self.assertEqual(dims["D2"], 1.0)
        self.assertEqual(dims["D3"], 1.0)
        self.assertEqual(dims["D4"], 0.5)
        self.assertEqual(dims["D5"], round(5 / 20, 4))
        self.assertEqual(dims["D6"], round(2 / 8, 4))  # previews + Writer's Paste; Sheets and Slides not measured
        expected = 0.35 * 0.8 + 0.15 + 0.20 + 0.10 * 0.5 + 0.15 * 0.25 + 0.05 * 0.25
        self.assertAlmostEqual(result["total"], round(expected, 4))
        self.assertEqual(result["below_floor"], ["D1", "D4", "D5", "D6"])
        again = card.score(copy.deepcopy(per_app), parity_report, pages, spec, CONFIG, apps=("writer",))
        self.assertEqual(again["total"], result["total"])  # same observations, same score
        self.assertIn("Total", card.markdown(result, {"label": "fixture"}))

    def test_crashed_run_scores_zero_not_error(self):
        per_app = {"writer": {"light": {"errors": ["boom"]}}}
        pages = {"writer": []}
        spec = {"apps": {"writer": {"tabs": []}}}
        report = {"writer": {"d1": 0.0, "d4": 0.0, "counts": {"present": 0, "elsewhere": 0, "missing": 0, "infeasible": 0},
                             "raw_coverage": 0.0, "launchers_present": 0, "launchers_feasible": 0}}
        result = card.score(per_app, report, pages, spec, CONFIG, apps=("writer",))
        self.assertEqual(result["dimensions"]["D5"], 0.0)
        self.assertEqual(result["details"]["writer"]["errors"], ["boom"])


@unittest.skipIf(Image is None, "Pillow is not installed")
class PixelTest(unittest.TestCase):
    def blank(self, size=(120, 80), colour=(245, 245, 245)):
        return Image.new("RGB", size, colour)

    def test_flat_fill_and_ring(self):
        before = self.blank()
        after = before.copy()
        ImageDraw.Draw(after).rectangle([10, 10, 39, 39], fill=(200, 220, 240))
        ok, detail = px.flat_fill(before, after, (10, 10, 30, 30))
        self.assertTrue(ok, detail)
        self.assertFalse(px.flat_fill(before, before, (10, 10, 30, 30))[0])
        ringed = before.copy()
        ImageDraw.Draw(ringed).rectangle([10, 10, 39, 39], outline=(0, 90, 200), width=2)
        self.assertTrue(px.ring(before, ringed, (10, 10, 30, 30))[0])
        self.assertFalse(px.ring(before, after, (10, 10, 30, 30))[0])  # a fill is not a ring

    def test_thin_separator_rejects_thick_borders(self):
        image = self.blank()
        ImageDraw.Draw(image).line([(50, 0), (50, 79)], fill=(200, 200, 200))
        self.assertTrue(px.thin_separator(image, (40, 10, 20, 60))[0])
        thick = self.blank()
        ImageDraw.Draw(thick).rectangle([48, 0, 52, 79], fill=(120, 120, 120))
        self.assertFalse(px.thin_separator(thick, (40, 10, 20, 60))[0])
        self.assertFalse(px.thin_separator(self.blank(), (40, 10, 20, 60))[0])

    def test_centred_caption_and_underline(self):
        image = self.blank((200, 60))
        draw = ImageDraw.Draw(image)
        draw.rectangle([80, 40, 119, 48], fill=(30, 30, 30))  # caption ink centred at x = 100
        self.assertTrue(px.centred(image, (0, 38, 200, 14), (0, 0, 200, 60))[0])
        self.assertFalse(px.centred(image, (0, 38, 200, 14), (0, 0, 160, 60))[0])
        draw.rectangle([0, 30, 199, 31], fill=(30, 100, 220))
        self.assertTrue(px.underline(image, (0, 0, 200, 30))[0])

    def test_large_icon_with_label_and_tiles(self):
        image = self.blank((60, 70))
        draw = ImageDraw.Draw(image)
        draw.rectangle([14, 4, 45, 35], fill=(40, 90, 160))  # 32 px icon
        draw.rectangle([18, 50, 41, 57], fill=(20, 20, 20))  # label
        ok, detail = px.large_icon_with_label(image, (0, 0, 60, 70))
        self.assertTrue(ok, detail)
        small = self.blank((60, 70))
        ImageDraw.Draw(small).rectangle([18, 8, 41, 31], fill=(40, 90, 160))  # 24 px icon, no label
        self.assertFalse(px.large_icon_with_label(small, (0, 0, 60, 70))[0])
        tiles = self.blank((300, 60))
        draw = ImageDraw.Draw(tiles)
        for left in (10, 90, 170):
            draw.rectangle([left, 20, left + 50, 30], fill=(20, 20, 20))
        draw.rectangle([5, 5, 75, 55], outline=(53, 132, 228))  # coloured selection frame is not text
        self.assertEqual(px.gallery_tiles(tiles, (0, 0, 300, 60)), 3)


if __name__ == "__main__":
    unittest.main()
