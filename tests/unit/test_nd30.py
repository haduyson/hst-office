# SPDX-License-Identifier: AGPL-3.0-only
"""ND30 layout/validation tests. Expectations come from docs/VIETNAMESE_OFFICE_SPEC.md via nd30-cases.json."""
import json
import os
import unittest

import _paths  # noqa: F401
from hst_office import nd30, nd30_layout

with open(os.path.join(_paths.FIXTURES, "nd30-cases.json"), encoding="utf-8") as _f:
    CASES = json.load(_f)


def lines(layout):
    return nd30_layout.layout_to_text(layout).split("\n")


class Formatting(unittest.TestCase):
    def test_number_padding(self):
        for raw, want in CASES["numbers"]:
            self.assertEqual(nd30.format_number(raw), want)

    def test_dates(self):
        for raw, want in CASES["dates"]:
            self.assertEqual(nd30.format_issue_date(raw), want, raw)


class Validation(unittest.TestCase):
    def test_types(self):
        data = nd30.rules()
        self.assertEqual(len(data["documentTypes"]), 7)
        self.assertEqual(nd30.validate_fields("nope", {})["errors"][0]["code"], "unknown-type")
        for t in data["documentTypes"]:
            self.assertTrue(nd30.validate_fields(t["id"], {})["ok"])

    def test_field_errors(self):
        codes = lambda f: {e["code"] for e in nd30.validate_fields("thong-bao", f)["errors"]}
        self.assertIn("number-digits-only", codes({"number": "12a"}))
        self.assertIn("symbol-no-space-or-slash", codes({"symbol": "A/B"}))
        self.assertIn("invalid-date", codes({"date": "2026-02-30"}))
        self.assertIn("control-character", codes({"body": "a\x00b"}))
        self.assertIn("too-long", codes({"agency": "x" * 2001}))
        self.assertIn("not-text", codes({"agency": 5}))
        self.assertEqual(codes({"body": "ok\nline", "date": "05/02/2026"}), set())

    def test_margins(self):
        self.assertTrue(nd30.validate_margins({"top": 20, "bottom": 25, "left": 35, "right": 15})["ok"])
        self.assertTrue(nd30.validate_margins(nd30.rules()["defaultMarginsMm"])["ok"])
        bad = nd30.validate_margins({"top": 19.9, "bottom": 25.1, "left": 29, "right": "x"})
        self.assertEqual({e["field"]: e["code"] for e in bad["errors"]}, {
            "top": "margin-out-of-range", "bottom": "margin-out-of-range", "left": "margin-out-of-range", "right": "margin-not-number"})
        self.assertFalse(nd30.validate_margins({"top": 20})["ok"])
        self.assertFalse(nd30.validate_margins({"top": float("nan"), "bottom": 20, "left": 30, "right": 15})["ok"])


class Layout(unittest.TestCase):
    def test_cases(self):
        for case in CASES["layouts"]:
            with self.subTest(case["typeId"]):
                got = lines(nd30_layout.build_layout(case["typeId"], case["fields"]))
                for want in case["expectLines"]:
                    self.assertIn(want, got)
                for bad in case["forbidLines"]:
                    self.assertFalse(any(g.startswith(bad) for g in got), bad)

    def test_all_types_build_with_placeholders_only(self):
        for t in nd30.rules()["documentTypes"]:
            text = nd30_layout.layout_to_text(nd30_layout.build_layout(t["id"]))
            for token in ("[TÊN CƠ QUAN BAN HÀNH]", "[Họ và tên]", "[Nội dung văn bản]"):
                self.assertIn(token, text)
            if t["typeName"]:
                self.assertIn(t["typeName"], text)

    def test_rules_follow_text_width(self):
        short = nd30_layout.build_layout("thong-bao", {"agency": "UBND"})["blocks"][0]["left"][0]["rule_mm"]
        long = nd30_layout.build_layout("thong-bao", {"agency": "ỦY BAN NHÂN DÂN THÀNH PHỐ"})["blocks"][0]["left"][0]["rule_mm"]
        self.assertLess(short, long)
        motto = nd30_layout.build_layout("thong-bao")["blocks"][0]["right"][1]
        width = nd30_layout.estimate_text_width_mm(motto["runs"][0]["text"], motto["runs"][0]["size"], True)
        self.assertAlmostEqual(motto["rule_mm"], width, delta=0.1)  # II.1b: as long as the line
        self.assertLessEqual(long, 0.5 * nd30_layout.estimate_text_width_mm("ỦY BAN NHÂN DÂN THÀNH PHỐ", 13, True) + 0.1)

    def test_typography_matches_spec(self):
        layout = nd30_layout.build_layout("bao-cao", {"body": "a\nb"})
        body = [b for b in layout["blocks"] if b["type"] == "paragraph" and b["align"] == "justify"]
        self.assertEqual(len(body), 2)
        for b in body:
            self.assertEqual((b["runs"][0]["size"], b["indent_first_mm"], b["spacing_after_pt"], b["line_spacing"]), (14, 12.7, 6, 1.15))
        head = layout["blocks"][0]
        self.assertTrue(head["right"][0]["runs"][0]["bold"])
        self.assertTrue(head["right"][2]["runs"][0]["italic"])
        sig = layout["blocks"][-1]["left"][0]["runs"][0]
        self.assertEqual((sig["text"], sig["bold"], sig["italic"], sig["size"]), ("Nơi nhận:", True, True, 12))

    def test_text_width_tracks_margins(self):
        self.assertEqual(nd30_layout.build_layout("thong-bao")["textWidthMm"], 165)
        self.assertEqual(nd30_layout.build_layout("thong-bao", margins_mm={"left": 35, "right": 20})["textWidthMm"], 155)

    def test_unknown_type_raises(self):
        with self.assertRaises(ValueError):
            nd30_layout.build_layout("khong-co")


if __name__ == "__main__":
    unittest.main()
