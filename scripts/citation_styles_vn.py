# SPDX-License-Identifier: AGPL-3.0-only
"""Vietnamese thesis styles: numbered (ĐHQGHN/HVTC pattern) and author–year (NEU/UEL pattern)."""
from citation_styles_common import ALIAS, DOT, VN_PUB, g, m, opts, t, term, v

STYLES = {}


# ---------------------------------------------------------------- Vietnamese thesis styles
def vn_layouts(author_date):
    """UET/HVTC (numeric) and NEU/UEL (author-date) share the order of elements; they differ in quotes and pages.
    Elements after the year join with a ", " prefix; the entry ends with a period."""
    page_prefix = {"vi": ", tr. ", "other": ", pp. "}
    pages = v("page", prefix=", " if author_date else page_prefix)
    head = [m("author"), m("year")]
    c = ", "
    year_full = g(term("issued-on"), v("issued", form="full"), delimiter=" ", prefix=c, **{"if": "day=issued"})
    accessed = g(term("accessed"), v("accessed", form="full"), delimiter=" ", prefix=c)
    url = g(term("from"), v("URL", wrap="<>"), delimiter=" ", prefix=c)
    doi = v("DOI", prefix=c, **{"if": "opt.doiPrefix"})
    translated = v("translator", label="translated-by", labelPos="before", prefix=c)
    original = g(t({"vi": "Sách gốc xuất bản năm ", "other": "Original work published "}), v("original-date"),
                 wrap="()", prefix=" ")
    volume = g(term("volume", case="capfirst"), v("volume"), delimiter=" ", prefix=c)
    title_i = v("title", italic=True, prefix=c)
    title_q = v("title", quotes=True, prefix=c)
    container_i = v("container-title", italic=True, prefix=c)
    place = v("publisher-place", prefix=c)
    return {
        "book": head + [title_i, volume, translated, v("edition", case="capfirst", prefix=c),
                        v("publisher", form="prefixed", prefix=c), place, original, doi, DOT],
        "chapter": head + [title_q,
                           g(term("in"), v("editor", label="editor", suffix=","), v("container-title", italic=True),
                             delimiter=" ", prefix=c),
                           v("publisher", form="prefixed", prefix=c), place, pages, doi, DOT],
        "article-journal": head + [title_q, container_i,
                                   g(v("volume"), v("issue", wrap="()"), delimiter=" ", prefix=c),
                                   g(term("issue"), v("issue"), delimiter=" ", prefix=c, **{"if": "!volume"}),
                                   pages, doi, DOT],
        "paper-conference": head + [title_q, container_i, v("publisher", prefix=c), place, pages, doi, DOT],
        "thesis": head + [title_i, v("genre", fallbackTerm="thesis", prefix=c), v("publisher", prefix=c), place, DOT],
        "report": head + [title_i, g(v("genre"), v("number"), delimiter=" ", prefix=c), v("publisher", prefix=c),
                          place, url, DOT],
        "legislation": head + [title_i, year_full, DOT],
        "webpage": head + [title_i, v("container-title", prefix=c), accessed, url, DOT],
        "article-newspaper": head + [title_q, container_i,
                                     v("issued", form="full", prefix={"vi": ", ngày ", "other": ", "},
                                       **{"if": "day=issued"}), pages, url, DOT],
        "default": head + [title_i, v("container-title", prefix=c), v("publisher", prefix=c), place, url, DOT],
    }


VN_MACROS = {
    "author": [v("author", substitute=[v("editor", label="editor"), v("title", italic=True)])],
    "year": [v("issued", form="year", wrap="()", prefix=" ", noDate=True)],
}
VN_SOURCES = [
    "ĐHQGHN – Trường ĐH Công nghệ, mẫu luận án tiến sĩ (mẫu “Hướng dẫn xếp tài liệu tham khảo”)",
    "Học viện Tài chính, Hướng dẫn trình bày luận văn, đề án, luận án (2022)",
    "ĐH Hồng Đức, Hướng dẫn trích dẫn tài liệu tham khảo (2022)",
    "Thông tư 18/2021/TT-BGDĐT và 23/2021/TT-BGDĐT giao cơ sở đào tạo quy định hình thức trình bày",
]

STYLES["vn-so"] = {
    "id": "vn-so", "name": "Luận văn Việt Nam – số thứ tự [1]", "class": "numeric",
    "description": "Trích [15], [15, tr. 314–315], [5, 21, 49], [7–11]. Danh mục chia nhóm ngôn ngữ (tiếng Việt trước), "
                   "xếp ABC; tác giả Việt viết đủ họ tên, xếp theo tên; số thứ tự là vị trí trong danh mục. "
                   "Bộ GD&ĐT không quy định kiểu trích dẫn: mỗi cơ sở đào tạo tự quy định, nên các khác biệt là tùy chọn.",
    "source": VN_SOURCES,
    "options": opts(groupByLanguage=True, groupHeadings=True, foreignName="family-initials", initialsSpace=False,
                    publisherPrefix=VN_PUB, bibLabel="[%s]", doiPrefix=""),
    "presets": [
        {"id": "tung-ngoac", "name": "Mỗi số một ngoặc: [19], [25], [41] (Học viện Tài chính)",
         "options": {"multiCite": "separate", "compress": False}},
        {"id": "thu-tu-trich", "name": "Số theo thứ tự trích, không chia nhóm, [15, 314–315] (ĐH Hồng Đức)",
         "options": {"order": "cite", "groupByLanguage": False, "groupHeadings": False, "locatorLabel": False,
                     "multiCite": "separate", "compress": False, "bibEtAl": {"min": 4, "use": 3},
                     "bibAnd": {"vi": "và", "other": "and"}}},
        {"id": "khong-nhom", "name": "Một danh mục ABC, không chia nhóm ngôn ngữ",
         "options": {"groupByLanguage": False, "groupHeadings": False}},
    ],
    "macros": VN_MACROS, "layouts": vn_layouts(False), "alias": ALIAS,
}
vn_ad_layouts = vn_layouts(True)
STYLES["vn-tac-gia-nam"] = {
    "id": "vn-tac-gia-nam", "name": "Luận văn Việt Nam – tác giả, năm (Nguyễn Văn An, 2010)", "class": "author-date",
    "description": "Trích (Nguyễn Văn An, 2010), (Nguyễn Văn An & Lê Bình, 2009), (Romer & cộng sự, 2006), "
                   "Nguyễn Văn An (2010). Mặc định: danh mục chia nhóm ngôn ngữ, tiếng Việt trước xếp theo tên, "
                   "tiếng nước ngoài xếp theo họ (quyết định của chủ sản phẩm 13/11/2026); có sẵn mẫu một danh mục xếp theo họ.",
    "source": ["ĐH Kinh tế Quốc dân, Quy chế đào tạo tiến sĩ 2021, phụ lục hướng dẫn trích dẫn",
               "ĐH Kinh tế – Luật (ĐHQG-HCM), Phụ lục cách trích tài liệu tham khảo (thạc sĩ)"] + VN_SOURCES[:1],
    "options": opts(groupByLanguage=True, groupHeadings=True, bibAnd="&", citeAnd="&",
                    etAlTerm={"vi": "& cộng sự", "other": "& cộng sự"}, yearSuffix=True, quotes="single",
                    publisherPrefix=VN_PUB, collapseYears=True, citeSort=False, doiPrefix=""),
    "presets": [
        {"id": "mot-danh-muc-theo-ho", "name": "Một danh mục, xếp theo họ (ĐH Kinh tế Quốc dân, ĐH Kinh tế – Luật)",
         "options": {"groupByLanguage": False, "groupHeadings": False, "viSort": "family"}},
        {"id": "et-al", "name": "Tác giả nước ngoài: “et al.” thay cho “& cộng sự”",
         "options": {"etAlTerm": {"vi": "& cộng sự", "other": "et al."}}},
    ],
    "macros": VN_MACROS, "layouts": vn_ad_layouts, "alias": ALIAS,
}
# NEU/UEL: translated books say "dịch bởi …" and journal pages have no "tr." (handled by author_date=True)
