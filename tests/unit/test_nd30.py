# SPDX-License-Identifier: AGPL-3.0-only
"""ND30 layout/validation tests. Expectations come from docs/VIETNAMESE_OFFICE_SPEC.md via nd30-cases.json."""
import json
import os
import sys
import unittest
from unittest import mock

import _paths  # noqa: F401
from hst_office import nd30, nd30_layout, nd30_metrics

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
        self.assertGreaterEqual(len(data["documentTypes"]), 7)
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
            if t.get("module") == "sheets":
                continue
            text = nd30_layout.layout_to_text(nd30_layout.build_layout(t["id"]))
            self.assertIn("[", text, t["id"])
            if t["typeName"]:
                self.assertIn(t["typeName"], text)

    def header_cells(self, type_id, fields=None):
        rows = nd30_layout.build_layout(type_id, fields)["blocks"][0]["rows"]
        return rows

    def test_rules_follow_real_line_width(self):
        rule = lambda agency: next(p["rule_mm"] for p in self.header_cells("thong-bao", {"agency": agency})[0]["cells"][0] if p.get("rule_mm"))
        short, long = rule("UBND"), rule("ỦY BAN NHÂN DÂN")
        self.assertLess(short, long)
        motto = self.header_cells("thong-bao")[0]["cells"][1][1]
        width = nd30_metrics.text_width_mm(motto["runs"][0]["text"], motto["runs"][0]["size"], True)
        self.assertAlmostEqual(motto["rule_mm"], width, delta=0.01)  # II.1b: as long as the line
        self.assertAlmostEqual(width, 60.46, delta=0.1)  # measured on a rendered PDF
        for name in ("UBND", "ỦY BAN NHÂN DÂN TỈNH VÍ DỤ PHỤC VỤ THỬ NGHIỆM RẤT DÀI ĐỂ XUỐNG DÒNG"):
            line = nd30_metrics.widest_line_mm(name, 13, True, 165 * 0.38)
            self.assertTrue(line / 3 <= rule(name) <= line / 2, name)  # II.2b: 1/3-1/2 of the line

    def test_number_and_date_share_a_row(self):
        number, date = self.header_cells("thong-bao")[1]["cells"]
        self.assertTrue(number[0]["runs"][0]["text"].startswith("Số:"))
        self.assertIn("ngày", date[0]["runs"][0]["text"])
        self.assertEqual(self.header_cells("bien-ban")[1]["cells"][1], [])  # form 1.9 has no date line

    def test_symbol_keeps_official_abbreviations(self):
        self.assertEqual(nd30.format_symbol("ttr-snv", "TTr"), "TTr-SNV")
        self.assertEqual(nd30.format_symbol("snv", "TTr"), "TTr-SNV")
        self.assertEqual(nd30.format_symbol("TTR-SNV", "TTr"), "TTr-SNV")
        self.assertEqual(nd30.format_symbol("qđ-ubnd", "QĐ"), "QĐ-UBND")
        self.assertEqual(nd30.format_symbol("snv-vp"), "SNV-VP")

    def test_typography_matches_spec(self):
        layout = nd30_layout.build_layout("bao-cao", {"body": "a\nb"})
        body = [b for b in layout["blocks"] if b["type"] == "paragraph" and b["align"] == "justify"]
        self.assertEqual(len(body), 2)
        for b in body:
            self.assertEqual((b["runs"][0]["size"], b["indent_first_mm"], b["spacing_after_pt"], b["line_spacing"]), (14, 12.7, 6, 1.15))
        head = layout["blocks"][0]["rows"]
        self.assertTrue(head[0]["cells"][1][0]["runs"][0]["bold"])
        self.assertEqual(head[0]["cells"][1][0]["runs"][0]["size"], 13)  # table footnote: 13 / 14 / 14 go together
        self.assertTrue(head[1]["cells"][1][0]["runs"][0]["italic"])
        sig = layout["blocks"][-1]["rows"][0]["cells"][0][0]["runs"][0]
        self.assertEqual((sig["text"], sig["bold"], sig["italic"], sig["size"]), ("Nơi nhận:", True, True, 12))

    def test_decision_roles(self):
        layout = nd30_layout.build_layout("quyet-dinh")
        blocks = {b.get("role"): b for b in layout["blocks"] if b["type"] == "paragraph"}
        self.assertTrue(blocks["Basis"]["runs"][0]["italic"])
        self.assertTrue(blocks["Authority"]["runs"][0]["bold"])
        self.assertEqual(blocks["Resolve"]["runs"][0]["text"], "QUYẾT ĐỊNH:")
        self.assertTrue(blocks["Resolve"]["runs"][0]["bold"])
        self.assertEqual(blocks["Resolve"]["align"], "center")
        article = blocks["Article"]["runs"]
        self.assertTrue(article[0]["bold"] and not article[1]["bold"])

    def test_minutes_secretary_left_chair_right(self):
        grid = next(b for b in nd30_layout.build_layout("bien-ban", {"secretaryName": "A", "signerName": "B"})["blocks"] if b["type"] == "grid" and b["name"] == "Signature")
        left, right = grid["rows"][0]["cells"]
        self.assertEqual((left[0]["runs"][0]["text"], left[-1]["runs"][0]["text"]), ("THƯ KÝ", "A"))
        self.assertEqual((right[0]["runs"][0]["text"], right[-1]["runs"][0]["text"]), ("CHỦ TỌA", "B"))

    def test_as_above_after_addressee(self):
        text = lines(nd30_layout.build_layout("cong-van", {"kinhGui": "A"}))
        self.assertIn("- Như trên;", text)
        self.assertNotIn("- Như trên;", lines(nd30_layout.build_layout("thong-bao")))

    def test_line_spacing_is_proportional(self):
        import types
        fake = types.SimpleNamespace(createUnoStruct=lambda name: types.SimpleNamespace())
        with mock.patch.dict(sys.modules, {"uno": fake}):
            from hst_office import nd30_text
            spacing = nd30_text.line_spacing({"line_spacing": 1.15})
        self.assertEqual((spacing.Mode, spacing.Height), (0, 115))  # com.sun.star.style.LineSpacingMode.PROP

    def test_text_width_tracks_margins(self):
        self.assertEqual(nd30_layout.build_layout("thong-bao")["textWidthMm"], 165)
        self.assertEqual(nd30_layout.build_layout("thong-bao", margins_mm={"left": 35, "right": 20})["textWidthMm"], 155)

    def test_unknown_type_raises(self):
        with self.assertRaises(ValueError):
            nd30_layout.build_layout("khong-co")


if __name__ == "__main__":
    unittest.main()
