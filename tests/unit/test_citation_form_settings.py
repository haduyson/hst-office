# SPDX-License-Identifier: AGPL-3.0-only
"""Pure parts of the citation commands: the source form, the document settings, list filtering, the strings."""
import json
import os
import unittest

from _paths import ROOT
from hst_office import citation_entry_form as form
from hst_office import citation_lists as lists
from hst_office import citation_settings as settings
from hst_office import citation_texts

LOCALES = os.path.join(ROOT, "extensions", "hst-vietnamese-tools", "locales")


class SourceForm(unittest.TestCase):
    def test_dates(self):
        self.assertEqual(form.parse_date("2010"), {"date-parts": [[2010]]})
        self.assertEqual(form.parse_date("3/2010"), {"date-parts": [[2010, 3]]})
        self.assertEqual(form.parse_date("15/3/2010"), {"date-parts": [[2010, 3, 15]]})
        self.assertEqual(form.parse_date("2010-03-15"), {"date-parts": [[2010, 3, 15]]})
        for bad in ("", "năm 2010", "13/2010", "32/1/2010"):
            self.assertIsNone(form.parse_date(bad), bad)
        self.assertEqual(form.format_date({"date-parts": [[2010, 3, 15]]}), "15/3/2010")
        self.assertEqual(form.format_date({"literal": "không rõ năm"}), "không rõ năm")

    def test_round_trip_of_a_journal_article(self):
        values = form.values_of(None)
        values.update(title="Tăng trưởng tín dụng", authors="Nguyễn Văn An\nSmith, John\n{Ngân hàng Nhà nước}",
                      issued="2019", volume="12", page="10-18", publisher="ignored for articles")
        values["container-title"] = "Tạp chí Kinh tế"
        item, warnings = form.item_of(values, "article-journal")
        self.assertEqual(warnings, [])
        self.assertEqual(item["author"][0], {"family": "Nguyễn", "given": "Văn An", "hst-vi": True})
        self.assertEqual(item["author"][1]["family"], "Smith")
        self.assertEqual(item["author"][2], {"literal": "Ngân hàng Nhà nước"})
        self.assertNotIn("publisher", item)  # not a field of this type
        self.assertTrue(item["custom"]["hst"]["modified"])
        back = form.values_of(item)
        self.assertEqual(back["authors"], "Nguyễn Văn An\nSmith, John\n{Ngân hàng Nhà nước}")
        self.assertEqual((back["issued"], back["container-title"]), ("2019", "Tạp chí Kinh tế"))

    def test_editing_keeps_the_id_and_unshown_fields(self):
        base = {"id": "hst-1", "type": "book", "title": "Cũ", "translator": [{"family": "Lê", "given": "Văn B"}],
                "abstract": "Tóm tắt"}
        values = form.values_of(base)
        values["title"] = "Mới"
        item, _ = form.item_of(values, "book", base)
        self.assertEqual((item["id"], item["title"], item["abstract"]), ("hst-1", "Mới", "Tóm tắt"))
        self.assertEqual(item["translator"][0]["family"], "Lê")

    def test_every_type_shows_known_fields(self):
        for kind, fields in form.TYPE_FIELDS.items():
            self.assertLessEqual(set(fields), set(form.FIELDS), kind)
            self.assertIn("title", fields)


class Settings(unittest.TestCase):
    def test_round_trip_and_defaults(self):
        value = {"style": "vn-so", "preset": "hvtc", "opts": {"compress": False}}
        self.assertEqual(settings.decode(settings.encode(value)), value)
        self.assertEqual(settings.default_settings("vi")["style"], "vn-so")
        self.assertEqual(settings.default_settings("en")["style"], "apa-7")
        for bad in (None, "", "[]", '{"style": ""}', "{"):
            self.assertIsNone(settings.decode(bad), bad)

    def test_too_long_for_other_word_processors(self):
        with self.assertRaises(settings.SettingsError):
            settings.encode({"style": "vn-so", "opts": {"bibTitle": "x" * 300}})

    def test_only_changed_options_are_stored(self):
        self.assertEqual(settings.stored_options({"compress": True, "brackets": "()"}, {"compress": True, "brackets": "[]"}),
                         {"brackets": "()"})
        self.assertEqual(settings.stored_options({}, {}, "en"), {"language": "en"})


class Lists(unittest.TestCase):
    ENTRIES = [{"id": "a", "number": 1, "label": "[1]", "text": "Nguyễn Văn An (2010), Giáo trình"},
               {"id": "b", "number": 12, "label": "", "text": "Smith J. (2020), A study"},
               {"id": "c", "number": 2, "label": "[2]", "text": "Trần Bình (2019), Tín dụng"}]

    def test_filter_by_number_then_prefix_and_by_words_without_accents(self):
        self.assertEqual([e["id"] for e in lists.filter_entries(self.ENTRIES, "1")], ["a", "b"])
        self.assertEqual([e["id"] for e in lists.filter_entries(self.ENTRIES, "[2]")], ["c"])
        self.assertEqual([e["id"] for e in lists.filter_entries(self.ENTRIES, "nguyen giao")], ["a"])
        self.assertEqual(lists.row_text(self.ENTRIES[1]), "[12] Smith J. (2020), A study")

    def test_filter_items_limits_rows(self):
        items = [{"id": str(n), "title": "Sách %d" % n} for n in range(10)]
        shown, hidden = lists.filter_items(items, "sach", lambda i: i["title"], limit=4)
        self.assertEqual((len(shown), hidden), (4, 6))


class Strings(unittest.TestCase):
    def test_both_languages_have_the_same_keys(self):
        def shape(value):
            if isinstance(value, dict):
                return {k: shape(v) for k, v in value.items()}
            return len(value) if isinstance(value, list) else type(value).__name__
        with open(os.path.join(LOCALES, "citations-vi.json"), encoding="utf-8") as handle:
            vi = json.load(handle)
        with open(os.path.join(LOCALES, "citations-en.json"), encoding="utf-8") as handle:
            en = json.load(handle)
        self.assertEqual(shape(vi), shape(en))

    def test_ui_language(self):
        self.assertEqual([citation_texts.language_of(x) for x in ("vi", "vi-VN", "en-US", "", None, "fr")],
                         ["vi", "vi", "en", "en", "en", "en"])
        self.assertEqual(citation_texts.load_language("vi-VN")["common"]["title"], "Trích dẫn")
        self.assertEqual(citation_texts.load_language("en-US")["common"]["title"], "Citations")


if __name__ == "__main__":
    unittest.main()
