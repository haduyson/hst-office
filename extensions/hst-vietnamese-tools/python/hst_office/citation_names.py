# SPDX-License-Identifier: AGPL-3.0-only
"""Personal and organisation names of references (CSL-JSON name objects). Pure Python (no uno).

A Vietnamese author is stored family-first and is always shown in full and in that order:
``{"family": "Nguyễn", "given": "Văn An", "hst-vi": true}`` -> "Nguyễn Văn An". A foreign author is
``{"family": "Smith", "given": "John A."}``; an organisation is ``{"literal": "Bộ Giáo dục và Đào tạo"}``.
The stored ``hst-vi`` flag wins over guessing. Sorting reuses ``vietnamese_text`` (Vietnamese alphabet, tones after
letters): a Vietnamese name sorts by its given name (tên) then family and middle names, or letter by letter when
the style sorts by family name.
"""
import functools
import re
import unicodedata

from . import vietnamese_text as vt

VN_SURNAMES = frozenset((
    "Nguyễn Trần Lê Phạm Hoàng Huỳnh Phan Vũ Võ Đặng Bùi Đỗ Hồ Ngô Dương Lý Đào Đoàn Đinh Lâm Mai Trịnh Trương Cao "
    "Lưu Tạ Tô Hà Quản Quách Châu Từ Thái Kiều Lương Chu Tăng Triệu La Phùng Mạc Âu Lạc Tôn Vương Khổng Doãn Thân "
    "Nghiêm Giang Diệp Kim Đàm Vi Lò Hứa Hầu Bạch Bế Nông Lã Ông Trang Khúc Ninh Phương Tống Thạch Biện Cù Đồng Hàn "
    "Khương Liêu Mã Sầm Lục Viên Ung Thiều Tiêu Phí Cung Đậu Lại Nhan Kha Vy Phó Đới Ngụy Giáp Nhữ Bành Tào "
    "Tiết Trình Lường Mẫn Bồ").split())  # common middle/given names (Văn, Quang, Kim, Sơn…) are left out on purpose
_STRONG_MARKS = {"\u0306", "\u031b", "\u0323", "\u0309"}  # breve, horn, dot below, hook above
_TONES = {"\u0300", "\u0301", "\u0303", "\u0309", "\u0323"}  # huyền, sắc, ngã, hỏi, nặng
_ORG_START = ("bộ ", "tổng cục", "cục ", "viện ", "trường ", "đại học", "học viện", "ủy ban", "uỷ ban", "quốc hội",
              "chính phủ", "ngân hàng", "tổ chức", "hội ", "sở ", "ban ", "văn phòng", "tòa án", "toà án", "thủ tướng",
              "công ty", "tập đoàn", "trung tâm", "liên hợp quốc", "hiệp hội", "nhà xuất bản", "tạp chí", "báo ")
_ORG_WORDS = re.compile(r"\b(organi[sz]ation|association|universit(y|ies)|institut(e|o)|ministry|department|committee|"
                        r"council|bank|agency|society|foundation|corporation|inc|ltd|group|commission|office|"
                        r"programme|program|cent(er|re)|federation|union|bureau|board|government|nations|fund|"
                        r"consortium|collaboration|team|network|press)\b", re.I)
_PARTICLES = frozenset("van von de da di du le la der den ter dos das del della bin al el".split())
_SUFFIXES = frozenset(("Jr.", "Jr", "Sr.", "Sr", "II", "III", "IV"))


def has_vietnamese_marks(text):
    """True when Latin letters carry marks only Vietnamese uses (ă ơ ư đ, dot below, hook above, circumflex + tone);
    Cyrillic й (also a breve) does not count."""
    decomposed = unicodedata.normalize("NFD", text or "")
    if "đ" in decomposed.lower():
        return True
    for match in re.finditer("([A-Za-z])([\u0300-\u036f]+)", decomposed):
        marks = set(match.group(2))
        if _STRONG_MARKS & marks or ("\u0302" in marks and _TONES & marks):
            return True
    return False


def is_east_asian(name):
    """Chinese, Japanese and Korean names in their own script print family name first, without spaces or initials."""
    text = (name.get("family", "") + name.get("given", "")) if isinstance(name, dict) else (name or "")
    return bool(re.search("[\u3040-\u30ff\u3400-\u9fff\uac00-\ud7af]", text))


def has_any_mark(text):
    return any(unicodedata.category(c) == "Mn" for c in unicodedata.normalize("NFD", text or ""))


def is_vn_surname(word):
    return unicodedata.normalize("NFC", (word or "").strip()).capitalize() in VN_SURNAMES


def looks_vietnamese(words):
    """Guess for a full name in words: Vietnamese letters, or a Vietnamese family name plus some accent."""
    text = " ".join(words)
    return has_vietnamese_marks(text) or (has_any_mark(text) and any(is_vn_surname(w) for w in words))


def is_vietnamese(name):
    """Whether a CSL name object is a Vietnamese person (the stored flag wins over guessing)."""
    if not isinstance(name, dict) or name.get("literal"):
        return False
    if "hst-vi" in name:
        return bool(name["hst-vi"])
    return looks_vietnamese((name.get("family", "") + " " + name.get("given", "")).split())


def is_organization(text):
    text = vt.normalise_name(text)
    lower = text.lower()
    if lower.startswith(_ORG_START) or _ORG_WORDS.search(text):
        return True
    return bool(re.fullmatch(r"[A-ZĐ]{2,}(?:[-&][A-Z]+)?", text))


def parse_name(text, organization=None):
    """CSL name object from one written name: "Smith, John A.", "John A. Smith", "Nguyễn Văn An", "Văn An Nguyễn",
    "{World Health Organization}" (braced: an organisation), or an organisation guessed from its words."""
    text = vt.normalise_name(unicodedata.normalize("NFC", text or ""))
    if text.startswith("{") and text.endswith("}"):
        return {"literal": text[1:-1].strip()}
    if not text:
        return {}
    if organization or (organization is None and is_organization(text)):
        return {"literal": text}
    if "," in text:
        parts = [p.strip() for p in text.split(",")]
        family, given = parts[0], " ".join(p for p in parts[1:] if p not in _SUFFIXES)
        name = _with_particle(family, given)
        suffix = [p for p in parts[1:] if p in _SUFFIXES]
        if suffix:
            name["suffix"] = suffix[0]
        if looks_vietnamese((family + " " + given).split()):
            name["hst-vi"] = True
        return name
    words = text.split(" ")
    if len(words) == 1:
        return {"family": words[0]}
    if looks_vietnamese(words):
        if is_vn_surname(words[-1]) and not is_vn_surname(words[0]):
            return {"family": words[-1], "given": " ".join(words[:-1]), "hst-vi": True}
        return {"family": words[0], "given": " ".join(words[1:]), "hst-vi": True}
    split = len(words) - 1
    while split > 1 and words[split - 1].lower() in _PARTICLES:
        split -= 1
    return _with_particle(" ".join(words[split:]), " ".join(words[:split]))


def _with_particle(family, given):
    words = family.split(" ")
    name = {"family": family, "given": given} if given else {"family": family}
    if len(words) > 1 and words[0].lower() in _PARTICLES and words[0].islower():
        name["family"], name["non-dropping-particle"] = " ".join(words[1:]), words[0]
    return name


def full_name(name):
    """Natural written order: "Nguyễn Văn An", "John A. Smith", "Bộ Y tế"."""
    if name.get("literal"):
        return name["literal"]
    family = " ".join(p for p in (name.get("non-dropping-particle"), name.get("family")) if p)
    given = name.get("given", "")
    parts = (family, given) if is_vietnamese(name) else (given, family)
    return " ".join(p for p in parts if p) + (", " + name["suffix"] if name.get("suffix") else "")


def initials(given, period=True, space=True, ascii_only=False):
    """"John Ronald" -> "J. R."; "Jean-Paul" -> "J.-P."; "J.R." / "JR" (already initials) -> "J. R."."""
    given = vt.remove_diacritics(given or "") if ascii_only else (given or "")
    tokens = [t for t in re.split(r"[\s.]+", given) if t]
    if len(tokens) == 1 and tokens[0].isupper() and 1 < len(tokens[0]) <= 3 and "-" not in tokens[0]:
        tokens = list(tokens[0])  # Vancouver-style "JA"
    mark = "." if period else ""
    pieces = []
    for token in tokens:
        parts = [p for p in token.split("-") if p]
        text = "-".join(p[0].upper() + mark for p in parts)
        if token.startswith("-") and pieces:
            pieces[-1] += "-" + text  # "J.-P." split at its period
        elif text:
            pieces.append(text)
    return (" " if space and period else "").join(pieces)


@functools.lru_cache(maxsize=8192)
def collation_key(text):
    """Vietnamese-alphabet key; text in other scripts (Cyrillic, Chinese…) sorts after Latin text."""
    stripped = (text or "").lstrip(" “\"'‘([")
    other_script = bool(stripped) and stripped[0].isalpha() and not ("A" <= vt.remove_diacritics(stripped[0]) <= "z")
    return (1 if other_script else 0,) + vt.sort_key(text)


def name_sort_key(name, vi_order="given"):
    """Collation key: organisations by their name, Vietnamese by given name then family and middle names (or letter
    by letter when vi_order == "family"), others by family name then given names."""
    if name.get("literal"):
        return collation_key(name["literal"]), collation_key("")
    family, given = name.get("family", ""), name.get("given", "")
    if is_vietnamese(name):
        full = (family + " " + given).strip()
        if vi_order == "given":
            middle, last = vt.split_name(full)
            return collation_key(last), collation_key(middle)
        return collation_key(full), collation_key("")
    return collation_key(family), collation_key(given)


def search_text(name):
    """Accent- and case-folded text of a name for library search."""
    return vt.remove_diacritics(full_name(name)).lower()
