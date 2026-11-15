# SPDX-License-Identifier: AGPL-3.0-only
"""Vancouver (ICMJE/NLM), AMA 11 and Harvard (Cite Them Right)."""
from citation_styles_common import ALIAS, DOT, LINK, g, intl_opts, t, term, v

STYLES = {}


# ---------------------------------------------------------------- Vancouver / AMA
def nlm_layouts(ama):
    italic = {"italic": True} if ama else {}
    author = v("author", substitute=[v("editor", label="editor", labelPos="comma")], suffix=". ")
    place_pub = (v("publisher", suffix="; ") if ama else
                 g(v("publisher-place", suffix=": "), v("publisher"), suffix="; "))
    pages = (v("page", prefix=":") if ama else g(t({"vi": "tr. ", "other": "p. "}), v("page"), prefix=". "))
    doi = v("DOI", prefix=" ")
    return {
        "article-journal": [author, v("title", suffix=". "), v("container-title", form="short", suffix=". ", **italic),
                            v("issued", form="year"), v("volume", prefix=";"), v("issue", wrap="()"),
                            v("page", prefix=":"), DOT, doi],
        "book": [author, v("title", suffix=". ", **italic), v("edition", case="capfirst", suffix=". "), place_pub,
                 v("issued", form="year"), DOT, doi],
        "chapter": [author, v("title", suffix=". "),
                    g(t({"vi": "Trong: ", "other": "In: "}),
                      v("editor", label="editor", labelPos="comma", suffix=". "), v("container-title", **italic),
                      suffix=". "),
                    v("edition", case="capfirst", suffix=". "), place_pub, v("issued", form="year"), pages, DOT, doi],
        "thesis": [author, v("title", **italic),
                   v("genre", fallbackTerm="phd-thesis", **({"prefix": ". ", "suffix": ". "} if ama else
                                                           {"wrap": "[]", "prefix": " ", "suffix": ". "})),
                   t(". "), place_pub, v("issued", form="year"), DOT],
        "report": [author, v("title", suffix=". ", **italic), place_pub, v("issued", form="year"), DOT,
                   g(t({"vi": "Báo cáo số: ", "other": "Report No.: "}), v("number"), prefix=" ", suffix=".")],
        "webpage": ([author, v("title", suffix=". "), v("container-title", suffix=". "),
                     g(t({"vi": "Xuất bản ", "other": "Published "}), v("issued", form="full"), suffix=". "),
                     g(t({"vi": "Truy cập ", "other": "Accessed "}), v("accessed", form="full"), suffix=". "),
                     v("URL")] if ama else
                    [author, v("title"), t({"vi": " [Internet]", "other": " [Internet]"}), t(". "), place_pub,
                     v("issued", form="year"),
                     g(t({"vi": "trích dẫn ngày ", "other": "cited "}), v("accessed", form="ymd"), wrap="[]",
                       prefix=" "), t(". "),
                     g(t({"vi": "Truy cập tại: ", "other": "Available from: "}), v("URL"))]),
        "article-newspaper": [author, v("title", suffix=". "), v("container-title", suffix=". ", **italic),
                              v("issued", form="ymd"), v("page", prefix=":"), DOT],
        "default": [author, v("title", suffix=". ", **italic), place_pub, v("issued", form="year"), DOT,
                    g(t({"vi": "Truy cập tại: ", "other": "Available from: "}), v("URL"), prefix=" ")],
    }


STYLES["vancouver"] = {
    "id": "vancouver", "name": "Vancouver (ICMJE/NLM)", "class": "numeric",
    "description": "[1], [1, 3–5]; số theo thứ tự trích. Fauci AS, Lane HC. Tên bài. Tên tạp chí. 2020;382(13):1268-9. "
                   "Tối đa 6 tác giả rồi “et al.”; tên Việt viết đủ. Dùng cho y dược (Tạp chí Y Dược Huế).",
    "source": ["ICMJE Recommendations; NLM Citing Medicine, 2nd ed.",
               "Tạp chí Y Dược Huế, hướng dẫn trích dẫn tài liệu tham khảo"],
    "options": intl_opts(order="cite", viSort="family", foreignName="family-compact", bibEtAl={"min": 7, "use": 6},
                    etAlComma=True, quotes="none", pageRange="minimal", pageDash="-", doiPrefix="doi:",
                    bibLabel="%s.", hangingIndent=False),
    "terms": {"en": {"editor": ["editor", "editors"], "translator": "translator"}},
    "macros": {}, "layouts": nlm_layouts(False), "alias": dict(ALIAS, **{"paper-conference": "chapter"}),
}
STYLES["ama-11"] = {
    "id": "ama-11", "name": "AMA 11 (số mũ)", "class": "numeric",
    "description": "Trích bằng số mũ ¹, ¹⁻³. Tối đa 6 tác giả; từ 7 tác giả: 3 người đầu + “et al.”. "
                   "Tạp chí Nghiên cứu Y học (ĐH Y Hà Nội) dùng AMA.",
    "source": ["AMA Manual of Style, 11th ed. (2020)", "Tạp chí Nghiên cứu Y học, hướng dẫn gửi bài"],
    "options": intl_opts(order="cite", viSort="family", foreignName="family-compact", bibEtAl={"min": 7, "use": 3},
                    etAlComma=True, quotes="none", brackets="sup", pageDash="-", doiPrefix="doi:",
                    bibLabel="%s.", hangingIndent=False),
    "terms": {"en": {"editor": ["ed", "eds"], "page": ["p", "pp"]}},
    "macros": {}, "layouts": nlm_layouts(True), "alias": dict(ALIAS, **{"paper-conference": "chapter"}),
}

# ---------------------------------------------------------------- Harvard (Cite Them Right)
HV_HEAD = [v("author", substitute=[v("editor", label="editor"), v("title", italic=True)]),
           v("issued", form="year", wrap="()", prefix=" ", noDate=True, suffix=" ")]
HV_AVAIL = g(t({"vi": "Truy cập tại: ", "other": "Available at: "}), LINK)
HV_ACCESSED = g(t({"vi": "Truy cập ngày: ", "other": "Accessed: "}), v("accessed", form="dmy"), wrap="()",
                prefix=" ", **{"if": "!DOI"})
HV_PLACE_PUB = g(v("publisher-place", suffix=": "), v("publisher"), suffix=". ")
STYLES["harvard"] = {
    "id": "harvard", "name": "Harvard (Cite Them Right)", "class": "author-date",
    "description": "(Smith, 2020), (Smith and Doe, 2020), (Smith et al., 2020) từ 4 tác giả. Danh mục: Smith, J. (2020) "
                   "*Title*. 2nd edn. London: Penguin. Kiểu NEU/UEL thực chất là Harvard bản Việt (xem “Luận văn Việt Nam – tác giả, năm”).",
    "source": ["Pears & Shields, Cite Them Right, 12th ed. (2022)"],
    "options": intl_opts(bibAnd={"vi": "và", "other": "and"}, citeAnd={"vi": "và", "other": "and"}, viSort="family",
                         disambiguateInitials=True,
                    citeEtAl={"min": 4, "use": 1}, yearSuffix=True, collapseYears=True, citeSort=False,
                    quotes="single", initialsSpace=False),
    "terms": {"en": {"editor": ["ed.", "eds."], "edition": "%s edn", "no-date": "no date"}},
    "macros": {},
    "layouts": {
        "book": HV_HEAD + [v("title", italic=True, suffix=". "), v("edition", case="capfirst", suffix=". "), HV_PLACE_PUB,
                           HV_AVAIL, HV_ACCESSED, DOT],
        "chapter": HV_HEAD + [v("title", quotes=True, suffix=", "),
                              g(term("in"), v("editor", label="editor"), v("container-title", italic=True),
                                delimiter=" ", suffix=". "),
                              g(v("publisher-place", suffix=": "), v("publisher")),
                              g(term("page", plural=True), v("page"), delimiter=" ", prefix=", "), t(". "), HV_AVAIL,
                              DOT],
        "article-journal": HV_HEAD + [v("title", quotes=True, suffix=", "), v("container-title", italic=True),
                                      v("volume", prefix=", "), v("issue", wrap="()"),
                                      g(term("page", plural=True), v("page"), delimiter=" ", prefix=", "), t(". "),
                                      HV_AVAIL, HV_ACCESSED, DOT],
        "thesis": HV_HEAD + [v("title", italic=True, suffix=". "), v("genre", fallbackTerm="phd-thesis", suffix=". "),
                             v("publisher", suffix=". "), HV_AVAIL, HV_ACCESSED, DOT],
        "webpage": HV_HEAD + [v("title", italic=True, suffix=". "), HV_AVAIL, HV_ACCESSED, DOT],
        "default": HV_HEAD + [v("title", italic=True, suffix=". "), HV_PLACE_PUB, HV_AVAIL, HV_ACCESSED, DOT],
    },
    "alias": dict(ALIAS, **{"paper-conference": "chapter", "report": "default", "legislation": "default",
                            "article-newspaper": "article-journal"}),
}
