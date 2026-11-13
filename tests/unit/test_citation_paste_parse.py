# SPDX-License-Identifier: AGPL-3.0-only
"""Paste a formatted reference and get its fields back (offline): checked on lines printed by HST's own styles
and on hand-typed Vietnamese thesis lines."""
import unittest

import citation_golden as golden

from hst_office import citation_engine as engine
from hst_office import citation_paste_parse as paste
from hst_office import citation_runs as runs
from hst_office import citation_style as styles


def year(item):
    return ((item.get("issued") or {}).get("date-parts") or [[None]])[0][0]


class FromStyles(unittest.TestCase):
    """Every sample, printed by a style and pasted back, keeps its title (title case aside), its year (when the style
    prints one) and its authors: the same number with the same first family name, or the listed ones before
    "et al."/"và cộng sự"."""

    def same_authors(self, parsed, item, line):
        def family(name):
            return (name.get("family") or name.get("literal") or "").lower()
        want, got = item.get("author", []), parsed.get("author", [])
        truncated = any(word in line for word in ("et al", "cộng sự"))
        count = len(want) == len(got) or (truncated and 0 < len(got) < len(want))
        return count and (not want or bool(got) and family(got[0]) == family(want[0]))

    def check(self, style_id, minimum):
        style, good, failures = styles.load_style(style_id), 0, []
        for item in golden.samples():
            line = runs.plain(engine.entry_runs(style, item))
            parsed, info = paste.parse_reference(line)
            printed_year = year(item) is not None and str(year(item)) in line
            if (parsed.get("title", "").lower() == item["title"].lower() and self.same_authors(parsed, item, line)
                    and (year(parsed) == year(item) or not printed_year and year(parsed) is None)):
                good += 1
            else:
                failures.append(line)
        self.assertGreaterEqual(good, minimum, "\n".join(failures))

    def test_vietnamese_styles(self):
        self.check("vn-so", 24)
        self.check("vn-tac-gia-nam", 24)

    def test_apa_harvard_vancouver(self):
        self.check("apa-7", 24)
        self.check("harvard", 24)
        self.check("vancouver", 24)
        self.check("ama-11", 24)

    def test_ieee_chicago_mla_iso(self):
        self.check("ieee", 24)
        self.check("chicago-tac-gia-nam", 23)
        self.check("chicago-chu-thich", 23)
        self.check("mla-9", 22)
        self.check("iso-690-so", 24)
        self.check("iso-690-tac-gia-nam", 24)


class Typed(unittest.TestCase):
    def test_vietnamese_article_line(self):
        item, info = paste.parse_reference('[15] Quách Ngọc Ân (1992), "Nhìn lại hai năm phát triển lúa lai", '
                                           "Di truyền học ứng dụng, 98 (1), tr.10-16.")
        self.assertEqual(item["type"], "article-journal")
        self.assertEqual(item["author"], [{"family": "Quách", "given": "Ngọc Ân", "hst-vi": True}])
        self.assertEqual((item["title"], item["container-title"]),
                         ("Nhìn lại hai năm phát triển lúa lai", "Di truyền học ứng dụng"))
        self.assertEqual((item["volume"], item["issue"], item["page"]), ("98", "1", "10-16"))
        self.assertEqual((item["language"], info["confidence"]), ("vi", 1.0))

    def test_thesis_book_law_and_web(self):
        thesis, _ = paste.parse_reference("Vũ Đức Minh (2001), Phát triển phương pháp đo, Luận án Tiến sĩ Vật lý, "
                                          "Đại học Quốc gia Hà Nội, Hà Nội.")
        self.assertEqual((thesis["type"], thesis["genre"], thesis["publisher"]),
                         ("thesis", "Luận án Tiến sĩ Vật lý", "Đại học Quốc gia Hà Nội"))
        book, _ = paste.parse_reference("Lê Văn An, Phạm Thị Bình (2015), Cơ sở di truyền, Nxb Nông nghiệp, Hà Nội.")
        self.assertEqual((book["type"], book["publisher"], book["publisher-place"]), ("book", "Nông nghiệp", "Hà Nội"))
        self.assertEqual(len(book["author"]), 2)
        law, _ = paste.parse_reference("Bộ Giáo dục và Đào tạo (2021), Thông tư số 18/2021/TT-BGDĐT, ban hành "
                                       "ngày 28 tháng 6 năm 2021.")
        self.assertEqual((law["type"], law["author"]), ("legislation", [{"literal": "Bộ Giáo dục và Đào tạo"}]))
        web, _ = paste.parse_reference("Tổ chức Y tế Thế giới (2023), Tăng huyết áp, truy cập ngày 20 tháng 3 năm "
                                       "2024, từ <https://example.org/tang-huyet-ap>.")
        self.assertEqual((web["type"], web["URL"]), ("webpage", "https://example.org/tang-huyet-ap"))
        self.assertEqual(web["accessed"], {"date-parts": [[2024, 3, 20]]})

    def test_doi_and_many_lines(self):
        found = paste.parse_many("1. Smith, J. A., & Doe, B. (2020). A title. Journal of Tests, 12(3), 45–67. "
                                 "https://doi.org/10.1000/xyz123\n\n2. short\n"
                                 "3. Fauci AS, Lane HC. Covid-19. N Engl J Med. 2020;382(13):1268-9.")
        self.assertEqual(len(found), 2)
        apa, vancouver = found[0][0], found[1][0]
        self.assertEqual((apa["DOI"], apa["volume"], apa["issue"]), ("10.1000/xyz123", "12", "3"))
        self.assertEqual(apa["author"][0], {"family": "Smith", "given": "J. A."})
        self.assertEqual((vancouver["volume"], vancouver["page"], year(vancouver)), ("382", "1268-9", 2020))
        self.assertEqual(vancouver["author"][1], {"family": "Lane", "given": "H. C."})

    def test_vietnamese_edition_words(self):
        second, _ = paste.parse_reference("Trần Văn Bình (2010), Kinh tế học, xuất bản lần thứ 2, Nxb Giáo dục, Hà Nội.")
        third, _ = paste.parse_reference("Trần Văn Bình (2010), Kinh tế học, tái bản lần thứ 2, Nxb Giáo dục, Hà Nội.")
        self.assertEqual((second["edition"], third["edition"]), ("2", "3"))

    def test_names_before_title_and_repeated_author(self):
        item, _ = paste.parse_reference("WATSON, J. D. và CRICK, F. H. C. Molecular structure of nucleic acids. "
                                        "Nature. 1953, tập 171, tr. 737–738.")
        self.assertEqual([n["family"] for n in item["author"]], ["Watson", "Crick"])
        self.assertEqual(item["title"], "Molecular structure of nucleic acids")
        item, _ = paste.parse_reference("Bộ Giáo dục và Đào tạo. Thông tư số 18/2021/TT-BGDĐT. 2021.")
        self.assertEqual(item["author"], [{"literal": "Bộ Giáo dục và Đào tạo"}])
        many = paste.parse_many("Trần Văn Bình. Kinh tế học vi mô. Giáo dục, 2010.\n"
                                "---. Kinh tế học vĩ mô. Giáo dục, 2010.")
        self.assertEqual(many[1][0]["author"], many[0][0]["author"])


if __name__ == "__main__":
    unittest.main()
