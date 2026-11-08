# SPDX-License-Identifier: AGPL-3.0-only
"""Public R1 result schema, item selection and completion evidence."""
import json
from pathlib import Path
import sys
import tempfile
import unittest

from _paths import ROOT

sys.path.insert(0, str(Path(ROOT) / "tests/runtime"))
from r1auto import results


class ItemSelectionTests(unittest.TestCase):
    def test_default_and_all_select_the_platform_in_checklist_order(self):
        for platform, prefix, count in (("windows", "W", 15), ("macos", "M", 8)):
            for text in ("", "  ", "all", " ALL "):
                with self.subTest(platform=platform, text=text):
                    self.assertEqual(results.parse_items(text, platform),
                                     [f"{prefix}{i}" for i in range(1, count + 1)])

    def test_ranges_and_duplicates_keep_checklist_order(self):
        self.assertEqual(results.parse_items("w15 W3-5,w1-w3, W10 W5", "windows"),
                         ["W1", "W2", "W3", "W4", "W5", "W10", "W15"])
        self.assertEqual(results.parse_items("M8, m4-6 m1 M4", "macos"),
                         ["M1", "M4", "M5", "M6", "M8"])

    def test_wrong_platform_invalid_ranges_and_malformed_tokens_are_rejected(self):
        cases = {"windows": ("M1", "W1 M2", "W0", "W16", "W2-1", "W1-M3",
                             "W1-16", "W1--3", "W1:3", "1", "W1,*", "all,W1"),
                 "macos": ("W1", "M0", "M9", "M7-9", "M4-2", "M1-W3")}
        for platform, values in cases.items():
            for text in values:
                with self.subTest(platform=platform, text=text), self.assertRaises(ValueError):
                    results.parse_items(text, platform)


class ResultSchemaTests(unittest.TestCase):
    def test_accepts_structured_measurements_and_explicit_failure_without_screenshot(self):
        value = results.row("W13", "PASS", {"message": "Hình mờ", "mean": 230.0}, "shots/W13.png")
        self.assertEqual(set(value), {"item", "status", "detail", "screenshot"})
        self.assertEqual(value["detail"]["mean"], 230.0)
        self.assertIsNone(results.row("W13", "FAIL", "Không kết nối được UNO")["screenshot"])
        self.assertIsNone(results.row("M4", "SKIP", "Chủ sở hữu chưa duyệt")["screenshot"])

    def test_missing_or_extra_fields_are_rejected(self):
        valid = results.row("W1", "FAIL", "Chưa chạy")
        for field in valid:
            invalid = {key: value for key, value in valid.items() if key != field}
            with self.subTest(missing=field), self.assertRaises(ValueError):
                results.validate_row(invalid)
        with self.assertRaises(ValueError):
            results.validate_row(dict(valid, passed=True))

    def test_invalid_item_status_and_empty_or_non_evidence_detail_are_rejected(self):
        invalid = [("item", value) for value in ("W0", "W16", "M9", "X1", None)]
        invalid += [("status", value) for value in ("pass", "PENDING", "", None)]
        invalid += [("detail", value) for value in ("", {}, [], ["text"], None, 0, True)]
        for key, value in invalid:
            candidate = results.row("W1", "FAIL", "Chưa chạy")
            candidate[key] = value
            with self.subTest(key=key, value=value), self.assertRaises(ValueError):
                results.validate_row(candidate)

    def test_pass_requires_a_relative_artifact_screenshot(self):
        for shot in (None, "", 42, "/tmp/screen.png", "../screen.png", "shots/../../screen.png",
                     r"shots\screen.png", r"C:\shots\screen.png", "C:/shots/screen.png"):
            with self.subTest(screenshot=shot), self.assertRaises(ValueError):
                results.row("W1", "PASS", "Đã đo", shot)

    def test_failed_rows_cannot_smuggle_a_screenshot_outside_the_artifact(self):
        with self.assertRaises(ValueError):
            results.row("W1", "FAIL", "Có lỗi", "../outside.png")


class CompletionTests(unittest.TestCase):
    def test_pending_rows_are_persisted_before_any_case_completes(self):
        with tempfile.TemporaryDirectory() as tmp:
            run = results.Results(tmp, "windows", "run-test", ["W1", "W2"])
            stored = json.loads((Path(tmp) / "results.json").read_text(encoding="utf-8"))
            self.assertEqual(stored, run.report)
            self.assertEqual([row["status"] for row in stored["results"]], ["FAIL", "FAIL"])
            self.assertFalse(results.gate(stored["results"]))
            run.put(results.row("W1", "PASS", "Đã đo", "shots/W1.png"))
            stored = json.loads((Path(tmp) / "results.json").read_text(encoding="utf-8"))
            self.assertFalse(results.gate(stored["results"]))
            run.put(results.row("W2", "PASS", "Đã đo", "shots/W2.png"))
            self.assertTrue(results.gate(run.report["results"]))
            self.assertEqual((Path(tmp) / "summary.md").read_text(encoding="utf-8"),
                             results.summary(run.report))

    def test_only_selected_items_can_replace_results_and_order_is_stable(self):
        with tempfile.TemporaryDirectory() as tmp:
            run = results.Results(tmp, "windows", "run-test", ["W1", "W2"])
            run.put(results.row("W2", "PASS", "Đã đo", "shots/W2.png"))
            before = (Path(tmp) / "results.json").read_bytes()
            with self.assertRaises(ValueError):
                run.put(results.row("W3", "FAIL", "Ngoài bộ lọc"))
            self.assertEqual((Path(tmp) / "results.json").read_bytes(), before)
            self.assertEqual([row["item"] for row in run.report["results"]], ["W1", "W2"])

    def test_empty_failures_and_required_skips_never_pass_gate(self):
        self.assertFalse(results.gate([]))
        passed = results.row("W1", "PASS", "Đã đo", "shots/W1.png")
        for status in ("FAIL", "SKIP"):
            for shot in (None, "shots/W2.png"):
                with self.subTest(status=status, shot=shot):
                    self.assertFalse(results.gate([passed, results.row("W2", status, "Chưa xong", shot)]))

    def test_owner_review_exception_requires_its_screenshot_and_never_hides_failures(self):
        passed = results.row("M1", "PASS", "Đã đo", "shots/M1.png")
        review = results.row("M4", "SKIP", "Chủ sở hữu duyệt", "shots/M4.png")
        self.assertTrue(results.gate([passed, review]))
        self.assertFalse(results.gate([passed, results.row("M4", "SKIP", "Thiếu ảnh")]))
        self.assertFalse(results.gate([review, results.row("M2", "FAIL", "Lỗi")]))

    def test_summary_has_one_line_per_result_and_escapes_multiline_details(self):
        report = {"platform": "windows", "run_id": "run-test", "results": [
            results.row("W1", "FAIL", "lỗi | đầu\r\n- dòng giả"),
            results.row("W2", "PASS", {"message": "đã đo\nhình | mờ"}, "shots/W2.png"),
            results.row("W3", "FAIL", {"mean": 230.0})]}
        summary = results.summary(report)
        items = [line for line in summary.splitlines() if line.startswith("- ")]
        self.assertEqual(items, ["- W1: **FAIL** — lỗi \\| đầu  - dòng giả",
                                 "- W2: **PASS** — đã đo hình \\| mờ",
                                 "- W3: **FAIL** — Xem số đo trong results.json"])
        self.assertNotIn("\r", summary)


if __name__ == "__main__":
    unittest.main()
