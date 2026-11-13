# SPDX-License-Identifier: AGPL-3.0-only
"""Chicago Manual of Style 18: author–date and notes–bibliography."""
from citation_styles_common import ALIAS, DOT, LINK, g, intl_opts, t, term, v

STYLES = {}


# ---------------------------------------------------------------- Chicago 18 (author-date and notes)
CH_PLACE_PUB = g(v("publisher-place", suffix=": "), v("publisher"))
CH_TRANS = v("translator", nameForm="given-family", label="translated-by", labelPos="before", case="capfirst",
             suffix=". ")
CH_ACCESSED = g(term("accessed", case="capfirst"), v("accessed", form="full"), delimiter=" ", suffix=". ",
                **{"if": "!issued"})


def chicago_bib(author_date):
    if author_date:
        head = [v("author", substitute=[v("editor", label="editor", labelPos="comma")], suffix=". "),
                v("issued", form="year", noDate=True, suffix=". ")]
        tail_book = [CH_PLACE_PUB, t(". ")]
        journal_date = []
    else:
        head = [v("author", substitute=[v("editor", label="editor", labelPos="comma")], suffix=". ")]
        tail_book = [g(CH_PLACE_PUB, v("issued", form="year"), delimiter=", "), t(". ")]
        journal_date = [v("issued", form="year", wrap="()", prefix=" ")]
    return {
        "book": head + [v("title", italic=True, suffix=". "), CH_TRANS, v("edition", case="capfirst", suffix=". ")] +
                tail_book +
                [LINK, DOT],
        "chapter": head + [v("title", quotes=True, suffix=". "),
                           g(term("in", case="capfirst"), v("container-title", italic=True), delimiter=" "),
                           v("editor", nameForm="given-family", label="edited-by", labelPos="before", prefix=", "),
                           v("page", prefix=", "), t(". ")] + tail_book + [LINK, DOT],
        "article-journal": head + [v("title", quotes=True, suffix=". "), v("container-title", italic=True),
                                   v("volume", prefix=" "), g(t("no."), v("issue"), delimiter=" ", prefix=", ")] +
                           journal_date + [v("page", prefix=": "), t(". "), LINK, DOT],
        "thesis": head + [v("title", quotes=True, suffix=". "),
                          g(v("genre", fallbackTerm="phd-thesis"), v("publisher"),
                            *([] if author_date else [v("issued", form="year")]), delimiter=", ", suffix=". "),
                          LINK, DOT],
        "webpage": head + [v("title", quotes=True, suffix=". "), v("container-title", suffix=". "),
                           v("issued", form="full", suffix=". ", **({"if": "day=issued"} if author_date else {})),
                           CH_ACCESSED, v("URL"), DOT],
        "default": head + [v("title", italic=True, suffix=". ")] + tail_book + [LINK, DOT],
    }


def chicago_ad_bib():
    layouts = chicago_bib(True)
    # author-date journals: "Journal 12 (3): 45–67."
    layouts["article-journal"] = [
        v("author", substitute=[v("editor", label="editor", labelPos="comma")], suffix=". "),
        v("issued", form="year", noDate=True, suffix=". "), v("title", quotes=True, suffix=". "),
        v("container-title", italic=True), v("volume", prefix=" "), v("issue", wrap="()", prefix=" "),
        v("page", prefix=": "), t(". "), LINK, DOT]
    return layouts


CH_OPTS = dict(foreignName="family-comma-given", firstInverted=True, bibAnd={"vi": "và", "other": "and"},
               bibAndComma="always", bibEtAl={"min": 7, "use": 3}, etAlComma=True,
               citeAnd={"vi": "và", "other": "and"}, citeAndComma="3+", citeYearSep=" ", locatorLabel=False,
               punctInQuote=True, titleCase="title-en", viSort="family",
               bibTitle={"vi": "TÀI LIỆU THAM KHẢO", "other": "Bibliography"})
STYLES["chicago-tac-gia-nam"] = {
    "id": "chicago-tac-gia-nam", "name": "Chicago 18 – tác giả, năm", "class": "author-date",
    "description": "(Smith 2020, 15), (Smith and Doe 2020), (Smith et al. 2020). Danh mục: Smith, John, and Jane Doe. 2020. "
                   "*Title*. New York: Norton.",
    "source": ["The Chicago Manual of Style, 18th ed. (2024), chương 13"],
    "options": intl_opts(yearSuffix=True, collapseYears=True, citeSort=False, disambiguateInitials=True,
                    **dict(CH_OPTS, bibTitle={"vi": "TÀI LIỆU THAM KHẢO", "other": "References"})),
    "terms": {"en": {"editor": ["ed.", "eds."]}},
    "macros": {}, "layouts": chicago_ad_bib(),
    "alias": dict(ALIAS, **{"paper-conference": "chapter", "report": "default", "legislation": "default",
                            "article-newspaper": "webpage"}),
}
NOTE_AUTHOR = v("author", nameForm="given-family", etAl="noteEtAl",
                substitute=[v("editor", nameForm="given-family", label="editor", labelPos="comma")], suffix=", ")
NOTE_PUB = g(g(v("publisher-place", suffix=": "), v("publisher")), v("issued", form="year"), delimiter=", ",
             wrap="()", prefix=" ")
NOTE_LOC = v("locator", prefix=", ")
BOOKS = ",".join(["book"] + sorted(kind for kind, target in ALIAS.items() if target == "book"))
VN_TITLE = v("title-or-short", italic=True, suffix=", ",
             **{"if": "type=" + BOOKS + ",report,thesis,webpage,legislation,document",
                "else": [v("title-or-short", quotes=True, suffix=", ")]})
# Tạp chí Luật học, mục 2.6: from the second cite on, "author, sđd" for a book and "tlđd" for anything else; the
# title comes first when the author has several cited works; no form for "the previous note".
VN_NOTES = {
    "id": "chu-thich-viet-nam", "name": "Chú thích kiểu Việt Nam: sđd, tlđd, tr. (theo Tạp chí Luật học)",
    "source": "Tạp chí Luật học (Trường ĐH Luật Hà Nội), Yêu cầu đối với bài đăng, mục 2.6: https://tapchi.hlu.edu.vn/"
              "Images/Post/files/Ho%E1%BA%A1t%20%C4%91%E1%BB%99ng%20%C4%91%C6%A1n%20v%E1%BB%8B/Yeu%20cau%20doi%20voi"
              "%20bai%20dang%20Tap%20chi%20Luat%20hoc.pdf",
    "options": {"ibid": False, "locatorLabel": True},
    "notes": {"short": [v("author", form="short", etAl="noteEtAl", suffix=", ", **{"if": "!suppress-author"}),
                        g(VN_TITLE, **{"if": "shared-author", "else": [g(VN_TITLE, **{"if": "suppress-author"})]}),
                        term("op-cit", **{"if": "type=" + BOOKS, "else": [term("loc-cit")]}), NOTE_LOC]},
}
STYLES["chicago-chu-thich"] = {
    "id": "chicago-chu-thich", "name": "Chicago 18 – chú thích cuối trang", "class": "note",
    "description": "Mỗi trích dẫn là một chú thích cuối trang: lần đầu ghi đủ, lần sau ghi ngắn (tác giả, tên ngắn, trang). "
                   "Mẫu “chú thích kiểu Việt Nam” dùng Sđd, Tlđd và “tr.”.",
    "source": ["The Chicago Manual of Style, 18th ed. (2024), chương 14"],
    "options": intl_opts(ibid=False, **CH_OPTS),
    "presets": [VN_NOTES],
    "terms": {"en": {"editor": ["ed.", "eds."]}},
    "macros": {},
    "layouts": chicago_bib(False),
    "alias": dict(ALIAS, **{"paper-conference": "chapter", "report": "default", "legislation": "default",
                            "article-newspaper": "webpage"}),
    "notes": {
        "layouts": {
            "book": [NOTE_AUTHOR, v("title", italic=True), v("edition", prefix=", "),
                     v("translator", nameForm="given-family", label="translated-by", labelPos="before", prefix=", "),
                     NOTE_PUB, NOTE_LOC, v("DOI", prefix=", ", **{"if": "!loc"})],
            "chapter": [NOTE_AUTHOR, v("title", quotes=True, suffix=", "),
                        g(term("in"), v("container-title", italic=True), delimiter=" "),
                        v("editor", nameForm="given-family", label="edited-by", labelPos="before", prefix=", "),
                        NOTE_PUB, NOTE_LOC],
            "article-journal": [NOTE_AUTHOR, v("title", quotes=True, suffix=", "), v("container-title", italic=True),
                                v("volume", prefix=" "), g(t("no."), v("issue"), delimiter=" ", prefix=", "),
                                v("issued", form="year", wrap="()", prefix=" "),
                                v("locator", prefix=": ", **{"if": "loc", "else": [v("page", prefix=": ")]}),
                                v("DOI", prefix=", ", **{"if": "DOI", "else": [v("URL", prefix=", ")]})],
            "thesis": [NOTE_AUTHOR, v("title", quotes=True),
                       g(v("genre", fallbackTerm="phd-thesis"), v("publisher"), v("issued", form="year"),
                         delimiter=", ", wrap="()", prefix=" "), NOTE_LOC],
            "webpage": [NOTE_AUTHOR, v("title", quotes=True, suffix=", "), v("container-title", suffix=", "),
                        v("issued", form="full", suffix=", "), v("URL")],
            "default": [NOTE_AUTHOR, v("title", italic=True), NOTE_PUB, NOTE_LOC],
        },
        "short": [v("author", form="short", etAl="noteEtAl", suffix=", "),
                  term("op-cit", **{"if": ["opt.shortNoteVi=sdd", "lang=vi"],
                                    "else": [v("title-or-short", italic=True,
                                               **{"if": "type=book,report,thesis,webpage,legislation,document",
                                                  "else": [v("title-or-short", quotes=True)]})]}),
                  NOTE_LOC],
    },
}
