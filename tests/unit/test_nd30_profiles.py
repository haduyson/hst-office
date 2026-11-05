# SPDX-License-Identifier: AGPL-3.0-only
"""Rules profiles and the new document types: each profile keeps its own rules; expectations come from the source annexes."""
import unittest

import _paths  # noqa: F401
from hst_office import nd30, nd30_layout, nd30_page
from hst_office.nd30_blocks import classify

ARTICLE7 = ("nghi-quyet quyet-dinh chi-thi quy-che quy-dinh thong-cao thong-bao huong-dan chuong-trinh ke-hoach phuong-an de-an du-an bao-cao bien-ban to-trinh "
            "hop-dong cong-van cong-dien ban-ghi-nho ban-thoa-thuan giay-uy-quyen giay-moi giay-gioi-thieu giay-nghi-phep phieu-gui phieu-chuyen phieu-bao thu-cong").split()
ABBREVIATIONS = {"nghi-quyet": "NQ", "quyet-dinh": "QĐ", "chi-thi": "CT", "quy-che": "QC", "quy-dinh": "QyĐ", "thong-cao": "TC", "thong-bao": "TB", "huong-dan": "HD",
                 "chuong-trinh": "CTr", "ke-hoach": "KH", "phuong-an": "PA", "de-an": "ĐA", "du-an": "DA", "bao-cao": "BC", "bien-ban": "BB", "to-trinh": "TTr", "hop-dong": "HĐ",
                 "cong-dien": "CĐ", "ban-ghi-nho": "BGN", "ban-thoa-thuan": "BTT", "giay-uy-quyen": "GUQ", "giay-moi": "GM", "giay-gioi-thieu": "GGT", "giay-nghi-phep": "GNP",
                 "phieu-gui": "PG", "phieu-chuyen": "PC", "phieu-bao": "PB"}


def text(type_id, fields=None, template=True):
    return nd30_layout.layout_to_text(nd30_layout.build_layout(type_id, fields, template=template))


class Catalog(unittest.TestCase):
    def test_all_29_types_of_article_7(self):
        self.assertEqual(len(ARTICLE7), 29)
        for type_id in ARTICLE7:
            self.assertEqual(nd30.get_type(type_id)["profile"], "nd30", type_id)

    def test_abbreviations(self):
        for type_id, abbr in ABBREVIATIONS.items():
            self.assertEqual(nd30.get_type(type_id)["abbr"], abbr)

    def test_no_invented_form_number(self):
        for type_id in ("hop-dong", "ban-ghi-nho", "ban-thoa-thuan", "thu-cong"):
            kind = nd30.get_type(type_id)
            self.assertEqual(kind["form"], "", type_id)
            self.assertTrue(kind["noForm"])


class Profiles(unittest.TestCase):
    def test_margins_per_profile(self):
        margins = {"top": 25, "bottom": 25, "left": 30, "right": 15}
        self.assertTrue(nd30.validate_margins(margins, nd30.profile_rules("nd30"))["ok"])
        self.assertFalse(nd30.validate_margins(margins, nd30.profile_rules("qppl"))["ok"])  # Decree 187: 15-20
        low = {"top": 15, "bottom": 15, "left": 30, "right": 15}
        self.assertTrue(nd30.validate_margins(low, nd30.profile_rules("qppl"))["ok"])
        self.assertFalse(nd30.validate_margins(low, nd30.profile_rules("nd30"))["ok"])
        self.assertFalse(nd30.validate_margins(margins, nd30.profile_rules("dang"))["ok"])  # Guide 05: fixed values
        for profile in ("nd30", "qppl", "dang"):
            data = nd30.profile_rules(profile)
            self.assertTrue(nd30.validate_margins(data["defaultMarginsMm"], data)["ok"], profile)

    def test_page_band_reaches_the_margin_in_every_profile(self):
        for profile, top in (("nd30", 25), ("qppl", 15), ("dang", 20)):
            data = nd30.profile_rules(profile)
            margins = {**data["defaultMarginsMm"], "top": top}
            wanted = nd30_page.plan_properties(margins, True, profile=profile)
            self.assertEqual(wanted["TopMargin"] + wanted["HeaderHeight"] + wanted["HeaderBodyDistance"], top * 100)

    def test_circular_rules(self):
        T = nd30.profile_rules("qppl")["typography"]
        self.assertEqual((T["signerAuthority"], T["pageNumber"]), (13, 13))
        result = text("thong-tu", {"number": "5", "date": "05/02/2026", "symbol": "bnv"}, template=False)
        self.assertIn("Số: 05/2026/TT-BNV", result)
        self.assertIn("Bộ trưởng", text("thong-tu"))
        self.assertNotIn("Về việc", text("thong-tu"))

    def test_circular_15_has_its_attached_document(self):
        blocks = nd30_layout.build_layout("thong-tu-ban-hanh", template=True)["blocks"]
        self.assertTrue(any(b.get("new_section") for b in blocks))
        self.assertIn("(Kèm theo Thông tư số", text("thong-tu-ban-hanh"))

    def test_party_profile(self):
        result = text("dang-quyet-dinh", {"number": "5", "symbol": "tu", "date": "05/02/2026"}, template=False)
        for wanted in ("ĐẢNG CỘNG SẢN VIỆT NAM", "Số 05-QĐ/TU", "*", "-----", "Nơi nhận:"):
            self.assertIn(wanted, result)
        self.assertNotIn("Độc lập", result)
        self.assertNotIn("CỘNG HÒA", result)
        self.assertTrue(nd30.validate_fields("dang-quyet-dinh", {"symbol": "QĐ/TU"})["ok"])
        self.assertFalse(nd30.validate_fields("thong-bao", {"symbol": "QĐ/TU"})["ok"])

    def test_party_minutes_person_responsible_on_the_right(self):
        grid = next(b for b in nd30_layout.build_layout("dang-bien-ban")["blocks"] if b.get("name") == "Signature")
        self.assertEqual(grid["rows"][0]["cells"][0][0]["runs"][0]["text"], "NGƯỜI GHI BIÊN BẢN")
        self.assertEqual(grid["rows"][0]["cells"][1][0]["runs"][0]["text"], "CHỦ TRÌ HỘI NGHỊ")


class Forms(unittest.TestCase):
    def test_copies(self):
        for type_id, form, abbr in (("sao-y", "SAO Y", "SY"), ("sao-luc", "SAO LỤC", "SL"), ("trich-sao", "TRÍCH SAO", "TrS")):
            layout = nd30_layout.build_layout(type_id, template=True)
            self.assertEqual(layout["flow"], "append")
            result = nd30_layout.layout_to_text(layout)
            self.assertIn(form, result)
            self.assertIn("/%s-" % abbr, result)
            self.assertTrue(any(b.get("top_rule") for b in layout["blocks"]), "full-width rule above the copy block")
        self.assertEqual(nd30_layout.build_layout("ban-sao-dien-tu")["flow"], "prepend")

    def test_register_opens_as_a_workbook(self):
        with self.assertRaises(ValueError):
            nd30_layout.build_layout("so-van-ban-di")

    def test_received_stamp_is_50_wide(self):
        grid = nd30_layout.build_layout("dau-den")["blocks"][0]
        self.assertEqual(grid["widthMm"], 50)
        self.assertEqual(sum(row["heightMm"] for row in grid["rows"]), 35)

    def test_classify(self):
        self.assertEqual(classify("Căn cứ Luật;")[0], "basis")
        self.assertEqual(classify("QUYẾT NGHỊ:")[0], "resolve")
        self.assertEqual(classify("Chương II")[0], "chapter")
        self.assertEqual(classify("Điều 3. Hiệu lực")[0], "article")
        self.assertEqual(classify("Một đoạn thường.")[0], "body")


if __name__ == "__main__":
    unittest.main()
