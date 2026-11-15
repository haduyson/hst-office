# SPDX-License-Identifier: AGPL-3.0-only
"""MLA 9 and ISO 690 (TCVN 10256:2013), numbered and author–year."""
from citation_styles_common import ALIAS, DOT, LINK, g, intl_opts, t, term, v

STYLES = {}


# ---------------------------------------------------------------- MLA 9
MLA_AUTHOR = v("author", substitute=[v("editor", label="editor", labelPos="comma")], suffix=". ")
STYLES["mla-9"] = {
    "id": "mla-9", "name": "MLA 9", "class": "author-date",
    "description": "Trích (Smith 15), (Smith and Doe 15), (Smith et al. 15) — tác giả và trang, không có năm. "
                   "Danh mục “Works Cited”: Smith, John. *Title*. Publisher, 2020.",
    "source": ["MLA Handbook, 9th ed. (2021)"],
    "options": intl_opts(citeYear=False, foreignName="family-comma-given", firstInverted=True,
                    bibAnd={"vi": "và", "other": "and"}, bibAndComma="always", bibEtAl={"min": 3, "use": 1},
                    etAlComma=True, citeAnd={"vi": "và", "other": "and"}, locatorLabel=False, punctInQuote=True,
                    titleCase="title-en", subsequentAuthor="---", citeSort=False, viSort="family",
                    bibTitle={"vi": "TÀI LIỆU TRÍCH DẪN", "other": "Works Cited"}),
    "terms": {"en": {"editor": ["editor", "editors"]}},
    "macros": {},
    "layouts": {
        "book": [MLA_AUTHOR, v("title", italic=True, suffix=". "),
                 v("translator", nameForm="given-family", label="translated-by", labelPos="before", case="capfirst",
                   suffix=", "), v("edition", case="capfirst", suffix=", "), v("publisher", suffix=", "),
                 v("issued", form="year"),
                 t(". "), LINK, DOT],
        "chapter": [MLA_AUTHOR, v("title", quotes=True, suffix=". "), v("container-title", italic=True, suffix=", "),
                    v("editor", nameForm="given-family", label="edited-by", labelPos="before", suffix=", "),
                    v("publisher", suffix=", "), v("issued", form="year", suffix=", "),
                    g(term("page", plural=True), v("page"), delimiter=" "), t(". "), LINK, DOT],
        "article-journal": [MLA_AUTHOR, v("title", quotes=True, suffix=". "), v("container-title", italic=True, suffix=", "),
                            g(term("volume"), v("volume"), delimiter=" ", suffix=", "),
                            g(term("issue"), v("issue"), delimiter=" ", suffix=", "),
                            v("issued", form="year", suffix=", "),
                            g(term("page", plural=True), v("page"), delimiter=" "), t(". "), LINK, DOT],
        "thesis": [MLA_AUTHOR, v("title", italic=True, suffix=". "), v("issued", form="year", suffix=". "),
                   v("publisher", suffix=", "), v("genre", fallbackTerm="phd-thesis"), DOT],
        "webpage": [MLA_AUTHOR, v("title", quotes=True, suffix=". "), v("container-title", italic=True, suffix=", "),
                    v("issued", form="dmy-abbr", suffix=", "), v("URL", suffix=". "),
                    g(term("accessed", case="capfirst"), v("accessed", form="dmy-abbr"), delimiter=" ", suffix=".")],
        "default": [MLA_AUTHOR, v("title", italic=True, suffix=". "), v("publisher", suffix=", "),
                    v("issued", form="year"), t(". "), v("URL"), DOT],
    },
    "alias": dict(ALIAS, **{"paper-conference": "chapter", "report": "default", "legislation": "default",
                            "article-newspaper": "webpage"}),
}

# ---------------------------------------------------------------- ISO 690
def iso_layouts(author_date):
    if author_date:
        head = [v("author", substitute=[v("title", italic=True)]),
                v("issued", form="year", prefix=", ", noDate=True, suffix=". ")]
        year = []
    else:
        head = [v("author", substitute=[v("editor", label="editor", labelPos="comma")], suffix=". ")]
        year = [v("issued", form="year")]
    place_pub = g(v("publisher-place", suffix=": "), v("publisher"))
    doi = g(t("DOI "), v("DOI"), prefix=" ", suffix=".", **{"if": "DOI", "else": [g(t({"vi": "Truy cập tại: ", "other": "Available from: "}), v("URL"), prefix=" ")]})
    return {
        "book": head + [v("title", italic=True, suffix=". "), v("edition", case="capfirst", suffix=". "),
                        g(place_pub, *year, delimiter=", ", suffix=". "),
                        g(t("ISBN"), v("ISBN"), delimiter=" ", suffix=". "), doi],
        "chapter": head + [v("title", suffix=". "),
                           g(t({"vi": "Trong: ", "other": "In: "}), v("editor", label="editor", suffix=". "),
                             v("container-title", italic=True), suffix=". "),
                           g(place_pub, *year, delimiter=", ", suffix=", "),
                           g(term("page", plural=True), v("page"), delimiter=" "), t(". "), doi],
        "article-journal": head + [v("title", suffix=". "), v("container-title", italic=True, suffix=". "),
                                   g(*year, g(term("volume"), v("volume"), delimiter=" "),
                                     g(term("issue"), v("issue"), delimiter=" "),
                                     g(term("page", plural=True), v("page"), delimiter=" "), delimiter=", ",
                                     case="capfirst", suffix=". "), doi],
        "thesis": head + [v("title", italic=True, suffix=". "), g(place_pub, *year, delimiter=", ", suffix=". "),
                          v("genre", fallbackTerm="phd-thesis", suffix=". "), doi],
        "webpage": head + [v("title", italic=True), t({"vi": " [trực tuyến]. ", "other": " [online]. "}),
                           v("container-title", suffix=". "), g(*year, suffix=" "),
                           g(term("viewed"), v("accessed", form="dmy"), delimiter=" ", wrap="[]", suffix=". "),
                           g(t({"vi": "Truy cập tại: ", "other": "Available from: "}), v("URL"))],
        "default": head + [v("title", italic=True, suffix=". "), g(place_pub, *year, delimiter=", ", suffix=". "), doi],
    }


ISO_OPTS = dict(familyUpper=True, foreignName="family-comma-given", viSort="family",
                bibAnd={"vi": "và", "other": "and"}, bibEtAl={"min": 4, "use": 3},
                citeAnd={"vi": "và", "other": "and"}, doiPrefix="")
STYLES["iso-690-so"] = {
    "id": "iso-690-so", "name": "ISO 690 – số thứ tự (TCVN 10256:2013)", "class": "numeric",
    "description": "[1], [2]; số theo thứ tự trích. SMITH, John. *Title*. 2nd ed. London: Penguin, 2020. "
                   "TCVN 10256:2013 tương đương ISO 690:2010 và không bắt buộc một kiểu dấu câu cố định.",
    "source": ["ISO 690:2010 / TCVN 10256:2013"],
    "options": intl_opts(order="cite", bibLabel="[%s]", **ISO_OPTS),
    "macros": {}, "layouts": iso_layouts(False), "alias": dict(ALIAS, **{"paper-conference": "chapter",
                                                                          "report": "default", "legislation": "default",
                                                                          "article-newspaper": "article-journal"}),
}
STYLES["iso-690-tac-gia-nam"] = {
    "id": "iso-690-tac-gia-nam", "name": "ISO 690 – tác giả, năm (TCVN 10256:2013)", "class": "author-date",
    "description": "(Smith 2020, p. 15). SMITH, John, 2020. *Title*. London: Penguin.",
    "source": ["ISO 690:2010 / TCVN 10256:2013"],
    "options": intl_opts(citeYearSep=" ", yearSuffix=True, collapseYears=True, citeSort=False, **ISO_OPTS),
    "macros": {}, "layouts": iso_layouts(True), "alias": STYLES["iso-690-so"]["alias"],
}
