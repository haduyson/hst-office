# SPDX-License-Identifier: AGPL-3.0-only
"""APA 7 and IEEE."""
from citation_styles_common import ALIAS, DOT, LINK, g, m, intl_opts, t, term, v

STYLES = {}


# ---------------------------------------------------------------- APA 7
APA_AUTHOR = v("author", substitute=[v("editor", label="editor"), v("title", italic=True)], suffix=". ")
APA_DATE = v("issued", form="year", wrap="()", noDate=True, suffix=". ")
APA_DATE_FULL = v("issued", form="y-md", wrap="()", noDate=True, suffix=". ")
APA_IN = g(term("in", case="capfirst"), v("editor", nameForm="initials-family", label="editor", andComma="3+",
                                          suffix=","),
           v("container-title", italic=True), delimiter=" ")
APA_ORIGINAL = g(t({"vi": "Sách gốc xuất bản năm ", "other": "Original work published "}), v("original-date"),
                 wrap="()", prefix=" ")
APA_RETRIEVED = g(term("retrieved"), v("accessed", form="full", suffix=","), term("from"), delimiter=" ",
                  case="capfirst", suffix=" ", **{"if": "!issued"})
STYLES["apa-7"] = {
    "id": "apa-7", "name": "APA 7", "class": "author-date",
    "description": "(Smith & Doe, 2020), (Smith et al., 2020), Smith (2020). Danh mục: Smith, J. A., & Doe, B. (2020). "
                   "Tên tác giả Việt mặc định viết đủ, không đảo; có mẫu đảo tên kiểu ĐH Cần Thơ.",
    "source": ["APA Publication Manual, 7th ed. (2020); apastyle.apa.org",
               "ĐH Tài chính – Marketing, hướng dẫn APA 7 (2022)", "ĐH Cần Thơ, QĐ 06/QĐ.NXB (2023)"],
    "options": intl_opts(viSort="family", disambiguateInitials=True, bibAnd="&", bibAndComma="always", bibEtAl={"min": 21, "use": 19, "last": True},
                    citeAnd="&", collapseYears=True, yearSuffix=True, quotes="none",
                    bibTitle={"vi": "TÀI LIỆU THAM KHẢO", "other": "References"}),
    "presets": [
        {"id": "dao-ten-viet", "name": "Đảo tên Việt: Hoàng, N. T.; trích (Hoàng, 2016), “và ctv.” (ĐH Cần Thơ)",
         "options": {"viName": "given-comma-initials", "citeViName": "given", "viSort": "given",
                     "etAlTerm": {"vi": "và ctv.", "other": "et al."}}},
    ],
    "terms": {"en": {"editor": ["Ed.", "Eds."], "translator": "Trans."}},
    "macros": {},
    "layouts": {
        "book": [APA_AUTHOR, APA_DATE, v("title", italic=True),
                 g(v("edition"), g(term("volume", case="capfirst"), v("volume"), delimiter=" "), delimiter=", ",
                   wrap="()", prefix=" "),
                 v("translator", nameForm="initials-family", label="translator", labelPos="comma", wrap="()",
                   prefix=" "), t(". "), v("publisher", suffix=". "), LINK, APA_ORIGINAL],
        "chapter": [APA_AUTHOR, APA_DATE, v("title", suffix=". "), APA_IN,
                    g(v("edition"), g(term("page", plural=True), v("page"), delimiter=" "), delimiter=", ",
                      wrap="()", prefix=" "), t(". "), v("publisher", suffix=". "), LINK],
        "article-journal": [APA_AUTHOR, APA_DATE, v("title", suffix=". "), v("container-title", italic=True),
                            v("volume", italic=True, prefix=", "), v("issue", wrap="()"), v("page", prefix=", "),
                            g(t({"vi": "Bài ", "other": "Article "}), v("number"), prefix=", ", **{"if": "!page"}),
                            t(". "), LINK],
        "thesis": [APA_AUTHOR, APA_DATE, v("title", italic=True),
                   g(v("genre", fallbackTerm="phd-thesis"), v("publisher"), delimiter=", ", wrap="[]", prefix=" "),
                   t(". "), v("archive", suffix=". "), LINK],
        "report": [APA_AUTHOR, APA_DATE, v("title", italic=True),
                   g(v("genre", fallbackTerm="report"), v("number"), delimiter=" ", wrap="()", prefix=" ",
                     **{"if": "number"}), t(". "), v("publisher", suffix=". "), LINK],
        "webpage": [APA_AUTHOR, APA_DATE_FULL, v("title", italic=True, suffix=". "), v("container-title", suffix=". "),
                    APA_RETRIEVED, v("URL")],
        "article-newspaper": [APA_AUTHOR, APA_DATE_FULL, v("title", suffix=". "), v("container-title", italic=True),
                              v("page", prefix=", "), t(". "), v("URL")],
        "legislation": [APA_AUTHOR, APA_DATE, v("title", italic=True, suffix=". "), v("URL")],
        "default": [APA_AUTHOR, APA_DATE, v("title", italic=True, suffix=". "), v("publisher", suffix=". "), LINK],
    },
    "alias": dict(ALIAS, **{"paper-conference": "chapter"}),
}

# ---------------------------------------------------------------- IEEE
IEEE_PLACE_PUB = g(v("publisher-place", suffix=": "), v("publisher"), suffix=", ")
IEEE_PAGES = g(term("page", plural=True), v("page"), delimiter=" ", prefix=", ")
STYLES["ieee"] = {
    "id": "ieee", "name": "IEEE", "class": "numeric",
    "description": "[1], [1]–[3], [1, p. 5]; số theo thứ tự trích. J. K. Author, “Title,” *Journal*, vol. 1, no. 2, "
                   "pp. 3–4, May 2020. Dùng nhiều ở ngành kỹ thuật (HUIT, HCMUTE, ĐH KHTN, ĐH Vinh).",
    "source": ["IEEE Reference Guide (IEEE Author Center)", "ĐH KHTN (ĐHQG-HCM), hướng dẫn trình bày TLTK đồ án thạc sĩ"],
    "options": intl_opts(order="cite", foreignName="initials-family", viSort="family",
                    bibAnd={"vi": "và", "other": "and"}, bibAndComma="3+", bibEtAl={"min": 7, "use": 1},
                    multiCite="separate", punctInQuote=True, bibLabel="[%s]", doiPrefix="doi: ",
                    bibTitle={"vi": "TÀI LIỆU THAM KHẢO", "other": "References"}),
    "presets": [{"id": "ten-viet-bo-dau", "name": "Tên Việt viết tắt, bỏ dấu: P. Huynh, Y. N. Lam (ĐH KHTN)",
                 "options": {"viName": "as-foreign", "viAscii": True}}],
    "terms": {"en": {"editor": ["Ed.", "Eds."], "translator": "Trans."}},
    "macros": {"author": [v("author", substitute=[v("editor", nameForm="initials-family", label="editor",
                                                    labelPos="comma")], suffix=", ")]},
    "layouts": {
        "article-journal": [m("author"), v("title", quotes=True, suffix=", "), v("container-title", italic=True, suffix=", "),
                            g(term("volume"), v("volume"), delimiter=" ", suffix=", "),
                            g(term("issue"), v("issue"), delimiter=" ", suffix=", "),
                            g(term("page", plural=True), v("page"), delimiter=" ", suffix=", "),
                            v("issued", form="my-abbr", suffix=", "), v("DOI", suffix=", "), DOT],
        "book": [m("author"), v("title", italic=True),
                 v("translator", nameForm="initials-family", label="translator", labelPos="comma", prefix=", "),
                 v("edition", prefix=", "), t(". "), IEEE_PLACE_PUB,
                 v("issued", form="year"), DOT],
        "chapter": [m("author"), v("title", quotes=True, suffix=", "),
                    g(term("in"), v("container-title", italic=True), delimiter=" "), v("edition", prefix=", "),
                    v("editor", nameForm="initials-family", label="editor", labelPos="comma", prefix=", "), t(". "),
                    IEEE_PLACE_PUB, v("issued", form="year"), IEEE_PAGES, DOT],
        "paper-conference": [m("author"), v("title", quotes=True, suffix=", "),
                             g(term("in"), v("container-title", italic=True), delimiter=" "),
                             v("event-place", prefix=", ", **{"if": "event-place", "else": [v("publisher-place", prefix=", ")]}),
                             v("issued", form="year", prefix=", "), IEEE_PAGES, v("DOI", prefix=", "), DOT],
        "thesis": [m("author"), v("title", quotes=True, suffix=", "), v("genre", fallbackTerm="phd-thesis", suffix=", "),
                   v("publisher", suffix=", "), v("publisher-place", suffix=", "), v("issued", form="year"), DOT],
        "report": [m("author"), v("title", quotes=True, suffix=", "), v("publisher", suffix=", "),
                   v("publisher-place", suffix=", "), g(t("Rep."), v("number"), delimiter=" ", suffix=", "),
                   v("issued", form="year"), DOT],
        "webpage": [v("author", suffix=". "), v("title", quotes=True, suffix=". "), v("container-title", suffix=". "),
                    g(t({"vi": "Truy cập: ", "other": "Accessed: "}), v("accessed", form="mdy-abbr"), suffix=". "),
                    g(t({"vi": "[Trực tuyến]. Địa chỉ: ", "other": "[Online]. Available: "}), v("URL"))],
        "default": [m("author"), v("title", italic=True, suffix=", "), v("publisher", suffix=", "),
                    v("issued", form="year"), t(". "),
                    g(t({"vi": "[Trực tuyến]. Địa chỉ: ", "other": "[Online]. Available: "}), v("URL"))],
    },
    "alias": dict(ALIAS, legislation="default"),
}
