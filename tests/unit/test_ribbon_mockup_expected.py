# SPDX-License-Identifier: LicenseRef-HST-Proprietary
# Copyright (C) 2026 HASON TECH
"""The mockup's expected vectors (tests/runtime/ribbon-mockup-expected.json) and the pure rules of check-ribbon-mockup.py."""
import json
import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(ROOT, "tests", "runtime"))
from ribbon_mockup_rules import LEVEL, banner_limits, banner_ok, compare_states, is_monotonic, width_findings  # noqa: E402

with open(os.path.join(ROOT, "tests", "runtime", "ribbon-mockup-expected.json"), encoding="utf-8") as handle:
    EXPECTED = json.load(handle)
HOME = {"clip", "font", "para", "styles", "edit", "viet"}
INSERT = {"pages", "tables", "illus", "links", "comments", "hf", "text", "symbols"}


class ExpectedVectors(unittest.TestCase):
    def test_states_are_known_ladder_letters(self):
        for tab, keys in (("home", HOME), ("insert", INSERT)):
            for name, value in EXPECTED["states"].items():
                if name.startswith(tab + "-"):
                    self.assertEqual(set(value["states"]), keys, name)
                    self.assertTrue(set(value["states"].values()) <= set(LEVEL), name)

    def test_each_group_only_grows_as_the_window_widens(self):
        for tab, keys in (("home", HOME), ("insert", INSERT)):
            widths = sorted(int(k.split("-")[1]) for k in EXPECTED["states"] if k.startswith(tab + "-"))
            for key in keys:
                series = [EXPECTED["states"][f"{tab}-{w}"]["states"][key] for w in widths]
                self.assertTrue(is_monotonic(series), (tab, key, series))

    def test_banner_limits_are_the_v3_rule(self):
        # the "banner" list of the expected JSON still holds the 1.0.2 sizes (260..360 wide, 104 high): the v3 rule
        # replaces them, so the check is the v3 limits (360..960 wide, 96 high, top 6), not that list
        self.assertEqual(banner_limits(), {"min_w": 360, "max_w": 960, "h": 96, "top": 6})

    def test_banner_ok_accepts_the_v3_range_and_rejects_the_1_0_2_size(self):
        self.assertTrue(banner_ok(360, 96))
        self.assertTrue(banner_ok(960, 96))
        self.assertTrue(banner_ok(361, 97))  # ±1 px for toolkit rounding
        self.assertFalse(banner_ok(358, 96))
        self.assertFalse(banner_ok(962, 96))
        self.assertFalse(banner_ok(360, 104))  # the 1.0.2 height
        self.assertFalse(banner_ok(260, 104))  # the 1.0.2 width at 1280

    def test_width_findings_judges_the_banner_by_the_v3_rule(self):
        got = {"groups": {}, "banner": (0, 0, 260, 104)}
        banner = [f for f in width_findings("home", 1920, {}, got) if "banner" in f[0]]
        self.assertEqual([ok for _name, ok, _detail in banner], [False])
        got["banner"] = (0, 0, 360, 96)
        banner = [f for f in width_findings("home", 1920, {}, got) if "banner" in f[0]]
        self.assertEqual([ok for _name, ok, _detail in banner], [True])

    def test_geometry_adds_up_to_the_147_px_row(self):
        g = EXPECTED["geometry_px"]
        self.assertEqual(g["tab_row"] + g["body_outer"], 147)
        self.assertEqual(g["body_outer"], g["body_panel"] + 2 * g["body_inset_top"])


class Comparator(unittest.TestCase):
    def test_equal_vectors_have_no_difference(self):
        want = {"clip": "L", "font": "L"}
        self.assertEqual(compare_states(want, {"clip": {"state": "L"}, "font": {"state": "L"}}), [])

    def test_a_different_state_is_reported_with_both_values(self):
        want = {"clip": "S", "font": "L"}
        self.assertEqual(compare_states(want, {"clip": {"state": "L"}, "font": {"state": "L"}}), [("clip", "S", "L")])

    def test_a_missing_group_is_a_difference(self):
        self.assertEqual(compare_states({"viet": "M"}, {}), [("viet", "M", None)])

    def test_extra_measured_groups_are_ignored(self):
        self.assertEqual(compare_states({"clip": "L"}, {"clip": {"state": "L"}, "extra": {"state": "S"}}), [])

    def test_monotonic_rule(self):
        self.assertTrue(is_monotonic(["S", "S", "M", "L"]))
        self.assertTrue(is_monotonic(["C"]))
        self.assertFalse(is_monotonic(["L", "S"]))
        self.assertFalse(is_monotonic(["M", "S", "M"]))


if __name__ == "__main__":
    unittest.main()
