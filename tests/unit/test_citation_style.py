# SPDX-License-Identifier: AGPL-3.0-only
"""Style files are validated with clear messages; presets, document options and the user's own styles."""
import copy
import json
import os
import tempfile
import unittest

import _paths  # noqa: F401

from hst_office import citation_style as styles
from hst_office import citation_style_check as check
from hst_office import citation_style_options as options


def bundled(style_id):
    with open(os.path.join(styles.builtin_dirs()[1], style_id + ".json"), encoding="utf-8") as handle:
        return json.load(handle)


class Validation(unittest.TestCase):
    def test_every_bundled_style_is_valid_and_complete(self):
        ids = styles.builtin_ids()
        self.assertEqual(len(ids), 12)
        for style_id in ids:
            data = bundled(style_id)
            check.check_style(data, style_id)
            self.assertEqual(data["id"], style_id)
            self.assertTrue(data["source"], style_id)

    def test_errors_name_the_problem(self):
        data = copy.deepcopy(bundled("vn-so"))
        del data["options"]["order"]
        data["layouts"]["book"].append({"v": "nonsense", "colour": "red"})
        data["layouts"]["book"].append({"macro": "missing"})
        data["layouts"]["book"].append({"text": "@noSuchOption"})
        data["layouts"]["book"].append({"v": "title", "if": "type==book"})
        with self.assertRaises(check.StyleError) as caught:
            check.check_style(data, "broken.json")
        message = str(caught.exception)
        for part in ("broken.json", "options: thiếu order", "biến không có: nonsense", "khóa không hiểu: colour",
                     "macro không có: missing", "tùy chọn không có: @noSuchOption", "điều kiện không hiểu"):
            self.assertIn(part, message)

    def test_option_values(self):
        self.assertIsNone(options.check_value("bibEtAl", {"min": 7, "use": 6}))
        self.assertIn("min", options.check_value("bibEtAl", {"min": 3, "use": 6}))
        self.assertIn("một trong", options.check_value("order", "random"))
        self.assertIsNone(options.check_value("etAlTerm", {"vi": "và cs.", "other": "et al."}))
        self.assertEqual(set(options.DEFAULTS), set(options.SCHEMA))


class Loading(unittest.TestCase):
    def test_preset_then_document_options(self):
        style = styles.load_style("vn-so", options={"compress": False, "bogus": 1, "order": "sideways"},
                                  preset="thu-tu-trich")
        self.assertEqual(style.options["order"], "cite")       # preset
        self.assertFalse(style.options["compress"])            # document option
        self.assertEqual(len(style.warnings), 2)               # bad document options are skipped, not fatal
        with self.assertRaises(styles.StyleError):
            styles.load_style("no-such-style")
        with self.assertRaises(styles.StyleError):
            styles.load_style("../etc/passwd")

    def test_preset_terms_layouts_and_notes(self):
        plain, ctu = styles.load_style("apa-7"), styles.load_style("apa-7", preset="dao-ten-viet")
        self.assertEqual(ctu.terms["vi"]["editor"], "Chủ biên")
        self.assertEqual(ctu.terms["en"]["editor"], ["Ed.", "Eds."])  # the style's own terms stay
        self.assertNotEqual(ctu.layout("thesis"), plain.layout("thesis"))
        self.assertEqual(ctu.layout("book"), plain.layout("book"))
        self.assertNotIn("Chủ biên", json.dumps(plain.terms, ensure_ascii=False))
        notes = styles.load_style("chicago-chu-thich", preset="chu-thich-viet-nam")
        self.assertNotEqual(notes.short_note(), styles.load_style("chicago-chu-thich").short_note())

    def test_bad_preset_extras_are_reported(self):
        data = copy.deepcopy(bundled("apa-7"))
        data["presets"][0]["colour"] = "red"
        data["presets"][0]["terms"] = {"vi": {"no-such-term": "x"}}
        data["presets"][0]["layouts"] = {"book": [{"v": "nonsense"}]}
        with self.assertRaises(check.StyleError) as caught:
            check.check_style(data, "broken.json")
        for part in ("khóa không hiểu: colour", "no-such-term", "biến không có: nonsense"):
            self.assertIn(part, str(caught.exception))

    def test_layout_alias_and_listing(self):
        style = styles.load_style("apa-7")
        self.assertIs(style.layout("paper-conference"), style.data["layouts"]["chapter"])
        self.assertIs(style.layout("map"), style.data["layouts"]["default"])
        listed = {s["id"]: s for s in styles.list_styles()}
        self.assertEqual(listed["vn-so"]["class"], "numeric")
        self.assertIn("thu-tu-trich", [p["id"] for p in listed["vn-so"]["presets"]])

    def test_user_style_save_load_list_delete(self):
        with tempfile.TemporaryDirectory() as user_dir:
            style_id = styles.save_user_style(user_dir, "Khoa Kinh tế – mẫu 2026", "vn-so", {"multiCite": "separate"})
            self.assertEqual(style_id, "user-khoa-kinh-te-mau-2026")
            style = styles.load_style(style_id, options={"compress": False}, user_dir=user_dir)
            self.assertEqual((style.name, style.options["multiCite"], style.options["compress"]),
                             ("Khoa Kinh tế – mẫu 2026", "separate", False))
            self.assertIn(style_id, [s["id"] for s in styles.list_styles(user_dir) if s["user"]])
            with self.assertRaises(ValueError):
                styles.save_user_style(user_dir, "x", "vn-so", {"order": "random"})
            with self.assertRaises(styles.StyleError):
                styles.save_user_style(user_dir, "x", "missing-base", {})
            self.assertTrue(styles.delete_user_style(user_dir, style_id))
            self.assertFalse(styles.delete_user_style(user_dir, style_id))


if __name__ == "__main__":
    unittest.main()
