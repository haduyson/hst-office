# SPDX-License-Identifier: AGPL-3.0-only
"""Words that citation styles print around the data ("tr.", "pp.", "Nxb", "et al."), in Vietnamese and English.

HST wrote these from the style manuals and Vietnamese university guides; nothing is copied from the CSL locale files
(CC BY-SA). A term is a string or a ``(singular, plural)`` pair. Items in any language other than Vietnamese use the
English terms. A style can override any term per language (``"terms": {"en": {"editor": ["Ed.", "Eds."]}}``).
"""

TERMS = {
    "vi": {
        "page": "tr.", "chapter": "chương", "section": "mục", "figure": "hình", "table": "bảng", "paragraph": "đoạn",
        "line": "dòng", "volume": "tập", "issue": "số", "number": "số", "editor": "chủ biên", "translator": "dịch",
        "translated-by": "dịch bởi", "edited-by": "chủ biên", "edition": "xuất bản lần thứ %s", "and": "và",
        "accessed": "truy cập ngày", "retrieved": "truy cập ngày", "from": "từ", "no-date": "không năm",
        "in": "trong", "online": "trực tuyến", "available": "truy cập tại", "available-from": "truy cập tại",
        "issued-on": "ban hành ngày", "thesis": "Luận văn",
        "phd-thesis": "Luận án Tiến sĩ", "masters-thesis": "Luận văn Thạc sĩ", "report": "Báo cáo",
        "in-press": "đang in", "ibid": "Như trên", "op-cit": "sđd", "loc-cit": "tlđd", "cited": "trích dẫn ngày", "internet": "Internet",
        "viewed": "xem ngày", "anonymous": "Khuyết danh", "et-al": "và cộng sự", "presented-at": "trình bày tại",
        "dataset": "bộ dữ liệu", "preprint": "bản thảo",
    },
    "en": {
        "page": ("p.", "pp."), "chapter": "chap.", "section": "sec.", "figure": "fig.", "table": "table",
        "paragraph": "para.", "line": ("line", "lines"), "volume": ("vol.", "vols."), "issue": "no.", "number": "no.",
        "editor": ("ed.", "eds."), "translator": "trans.", "translated-by": "translated by",
        "edited-by": "edited by", "edition": "%s ed.", "and": "and", "accessed": "accessed",
        "retrieved": "Retrieved", "from": "from", "no-date": "n.d.", "in": "in", "online": "Online",
        "available": "Available", "available-from": "Available from", "issued-on": "issued on",
        "thesis": "Thesis", "phd-thesis": "PhD thesis",
        "masters-thesis": "Master's thesis", "report": "Report", "in-press": "in press", "ibid": "Ibid.",
        "op-cit": "op. cit.", "loc-cit": "loc. cit.", "cited": "cited", "internet": "Internet", "viewed": "viewed",
        "anonymous": "Anonymous", "et-al": "et al.", "presented-at": "presented at", "dataset": "dataset",
        "preprint": "preprint",
    },
}

MONTHS_EN = ("January", "February", "March", "April", "May", "June", "July", "August", "September", "October",
             "November", "December")
MONTHS_EN_ABBR = ("Jan.", "Feb.", "Mar.", "Apr.", "May", "Jun.", "Jul.", "Aug.", "Sep.", "Oct.", "Nov.", "Dec.")
MONTHS_EN_SHORT = ("Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec")  # NLM, no period
LOCATOR_LABELS = ("page", "chapter", "section", "figure", "table", "paragraph", "line", "volume", "issue")


def term_language(lang):
    """'vi' for Vietnamese, 'en' for every other language (the bundled term tables)."""
    return "vi" if (lang or "").lower().startswith("vi") else "en"


def term(name, lang, plural=False, overrides=None):
    """The term in the item's language; style overrides win. Unknown names raise KeyError (styles are validated)."""
    code = term_language(lang)
    value = None
    if overrides:
        value = (overrides.get(code) or {}).get(name)
    if value is None:
        value = TERMS[code][name]
    if isinstance(value, (list, tuple)):
        return value[1] if plural and len(value) > 1 else value[0]
    return value


def known(name):
    return name in TERMS["vi"] and name in TERMS["en"]


def ordinal(number, lang):
    """English ordinals for editions (2nd, 3rd, 21st); Vietnamese keeps the plain number ("lần thứ 2")."""
    text = str(number)
    if term_language(lang) == "vi" or not text.isdigit():
        return text
    value = int(text)
    suffix = "th" if 10 <= value % 100 <= 20 else {1: "st", 2: "nd", 3: "rd"}.get(value % 10, "th")
    return text + suffix


def localize(value, lang):
    """Option and template values may be {"vi": ..., "other": ..., "<lang>": ...}; plain values pass through."""
    if not isinstance(value, dict):
        return value
    code = (lang or "").lower().split("-")[0]
    if code in value:
        return value[code]
    if term_language(code) == "vi" and "vi" in value:
        return value["vi"]
    return value.get("other", value.get("en", ""))
