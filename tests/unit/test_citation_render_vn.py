# SPDX-License-Identifier: AGPL-3.0-only
"""Vietnamese thesis conventions stated explicitly (the golden files hold the full outputs)."""
import unittest

import _paths  # noqa: F401

from hst_office import citation_engine as engine
from hst_office import citation_render_dates as render_dates
from hst_office import citation_render_fields as fields
from hst_office import citation_runs as runs
from hst_office import citation_style as styles

VI = {"hst-vi": True}


def entry(style_id, item, preset=None, **opts):
    found = engine.entry_runs(styles.load_style(style_id, opts, preset), dict({"id": "x"}, **item))
    return runs.to_markup(found)


class VietnameseThesis(unittest.TestCase):
    def test_journal_article_numbered_style(self):
        item = {"type": "article-journal", "language": "vi", "title": "Nhìn lại hai năm phát triển lúa lai",
                "author": [dict(family="Quách", given="Ngọc Ân", **VI)], "issued": {"date-parts": [[1992]]},
                "container-title": "Di truyền học ứng dụng", "volume": "98", "issue": "1", "page": "10-16"}
        self.assertEqual(entry("vn-so", item), "Quách Ngọc Ân (1992), “Nhìn lại hai năm phát triển lúa lai”, "
                                               "*Di truyền học ứng dụng*, 98 (1), tr. 10–16.")
        self.assertEqual(entry("vn-tac-gia-nam", item), "Quách Ngọc Ân (1992), ‘Nhìn lại hai năm phát triển lúa "
                                                        "lai’, *Di truyền học ứng dụng*, 98 (1), 10–16.")

    def test_book_publisher_prefix_is_not_doubled(self):
        item = {"type": "book", "language": "vi", "title": "Giáo trình", "publisher": "NXB Giáo dục",
                "publisher-place": "Hà Nội", "author": [dict(family="Lê", given="Văn An", **VI)]}
        self.assertEqual(entry("vn-so", item), "Lê Văn An (không năm), *Giáo trình*, Nxb Giáo dục, Hà Nội.")
        english = {"type": "book", "language": "en", "title": "Economics", "publisher": "Norton",
                   "author": [{"family": "Krugman", "given": "Paul"}], "issued": {"date-parts": [[2009]]}}
        self.assertEqual(entry("vn-so", english), "Krugman P. (2009), *Economics*, Norton.")

    def test_legislation_and_web_dates(self):
        law = {"type": "legislation", "language": "vi", "title": "Thông tư số 10/2009/TT-BGDĐT",
               "author": [{"literal": "Bộ Giáo dục và Đào tạo"}], "issued": {"date-parts": [[2009, 5, 7]]}}
        self.assertEqual(entry("vn-so", law), "Bộ Giáo dục và Đào tạo (2009), *Thông tư số 10/2009/TT-BGDĐT*, "
                                              "ban hành ngày 07 tháng 5 năm 2009.")
        web = {"type": "webpage", "language": "vi", "title": "Tin tức", "URL": "https://example.vn/a",
               "author": [{"literal": "Cổng thông tin X"}], "accessed": {"date-parts": [[2024, 2, 3]]}}
        self.assertEqual(entry("vn-so", web), "Cổng thông tin X (không năm), *Tin tức*, truy cập ngày 03 tháng 02 "
                                              "năm 2024, từ <https://example.vn/a>.")

    def test_name_variants(self):
        item = {"type": "book", "language": "vi", "title": "Sách", "issued": {"date-parts": [[2016]]},
                "author": [dict(family="Nguyễn", given="Thái Hoàng", **VI), dict(family="Trần", given="Huyền", **VI)]}
        self.assertTrue(entry("apa-7", item).startswith("Nguyễn Thái Hoàng & Trần Huyền. (2016)."))
        self.assertTrue(entry("apa-7", item, "dao-ten-viet").startswith("Hoàng, N. T., & Huyền, T. (2016)."))
        for style_id in ("ieee", "vancouver", "ama-11", "apa-7", "harvard", "chicago-tac-gia-nam", "mla-9"):
            self.assertIn("Nguyễn Thái Hoàng", entry(style_id, item), style_id)  # never abbreviated by default
        self.assertTrue(entry("ieee", item).startswith("Nguyễn Thái Hoàng và Trần Huyền, *Sách*"))
        self.assertTrue(entry("ieee", item, "ten-viet-bo-dau").startswith("T. H. Nguyen và H. Tran,"))
        self.assertTrue(entry("vancouver", item, viName="as-foreign").startswith("Nguyễn TH, Trần H."))
        self.assertTrue(entry("vancouver", item).startswith("Nguyễn Thái Hoàng, Trần Huyền. Sách."))
        self.assertTrue(entry("iso-690-so", item).startswith("NGUYỄN Thái Hoàng và TRẦN Huyền. *Sách*."))

    def test_no_comma_before_va(self):
        people = [dict(family=f, given="Văn A", **VI) for f in ("Lê", "Trần", "Phạm")]
        item = {"type": "book", "language": "vi", "title": "Sách", "author": people, "issued": {"date-parts": [[2020]]}}
        for style_id in ("chicago-tac-gia-nam", "iso-690-so", "ieee"):
            self.assertIn("Trần Văn A và ", entry(style_id, item).replace("TRẦN", "Trần"), style_id)

    def test_many_authors_cut_like_hong_duc(self):
        people = [dict(family=f, given="Văn A", **VI) for f in ("Lê", "Trần", "Phạm", "Vũ", "Đỗ")]
        item = {"type": "book", "language": "vi", "title": "Sách", "author": people, "issued": {"date-parts": [[2020]]}}
        self.assertTrue(entry("vn-so", item, "thu-tu-trich").startswith("Lê Văn A, Trần Văn A, Phạm Văn A "
                                                                        "và cộng sự (2020)"))


class Helpers(unittest.TestCase):
    def test_dates(self):
        date = {"date-parts": [[2009, 5, 7]]}
        self.assertEqual(render_dates.format_date(date, "full", "vi"), "07 tháng 5 năm 2009")
        self.assertEqual(render_dates.format_date({"date-parts": [[2024, 2, 13]]}, "full", "vi"),
                         "13 tháng 02 năm 2024")
        self.assertEqual(render_dates.format_date(date, "full", "en"), "May 7, 2009")
        self.assertEqual(render_dates.format_date(date, "ymd", "en"), "2009 May 7")
        self.assertEqual(render_dates.format_date(date, "dmy-abbr", "en"), "7 May 2009")
        self.assertEqual(render_dates.format_date({"date-parts": [[2024, 3, 20]]}, "mdy-abbr", "en"), "Mar. 20, 2024")
        self.assertEqual(render_dates.format_date(date, "year", "vi", "a"), "2009a")
        self.assertEqual(render_dates.format_date({"date-parts": [[2009], [2010]]}, "full", "en"), "2009–2010")
        self.assertEqual(render_dates.format_date({"literal": "đang in"}, "year", "vi"), "đang in")

    def test_fields(self):
        self.assertEqual(fields.page_range("123-9"), "123–129")
        self.assertEqual(fields.page_range("123--129", "minimal", "-"), "123-9")
        self.assertEqual(fields.page_range("1234-1240", "minimal", "-"), "1234-40")
        self.assertEqual(fields.page_range("e101-e105, S3"), "e101–e105, S3")
        self.assertEqual(fields.edition("2", "vi"), "xuất bản lần thứ 2")  # edition 2 is the second printing
        self.assertEqual(fields.edition("22nd", "en"), "22nd ed.")
        self.assertEqual(fields.edition("Revised", "en"), "Revised")
        self.assertEqual(fields.doi("https://doi.org/10.1/x", "doi:"), "doi:10.1/x")
        self.assertEqual(fields.publisher("Nhà xuất bản Trẻ", "Nxb "), "Trẻ")
        self.assertEqual(fields.title_case("the return of NASA: a study of x-ray data"),
                         "The Return of NASA: A Study of X-Ray Data")
        self.assertEqual(fields.sentence_case("NHÌN LẠI. HAI NĂM"), "Nhìn lại. Hai năm")
        self.assertFalse(fields.is_all_caps("Short TXT"))


if __name__ == "__main__":
    unittest.main()
