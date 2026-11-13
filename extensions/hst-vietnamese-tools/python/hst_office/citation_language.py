# SPDX-License-Identifier: AGPL-3.0-only
"""Language of a reference and the language groups of Vietnamese bibliographies. Pure Python (no uno).

The CSL ``language`` field (``vi``, ``en-US``, ``fr``…) decides the group; when it is empty HST guesses from the
title: Vietnamese letters -> ``vi``, Cyrillic -> ``ru``, kana -> ``ja``, Hangul -> ``ko``, Han -> ``zh``,
anything else -> ``en``. Groups follow the usual thesis order (Việt, Anh, Pháp, Đức, Nga, Trung, Nhật), then the
remaining languages by their Vietnamese name.
"""
import re

from . import citation_names as names
from . import vietnamese_text as vt

DEFAULT_ORDER = ("vi", "en", "fr", "de", "ru", "zh", "ja")
HEADINGS = {
    "vi": "Tiếng Việt", "en": "Tiếng Anh", "fr": "Tiếng Pháp", "de": "Tiếng Đức", "ru": "Tiếng Nga",
    "zh": "Tiếng Trung", "ja": "Tiếng Nhật", "ko": "Tiếng Hàn", "es": "Tiếng Tây Ban Nha", "it": "Tiếng Ý",
    "pt": "Tiếng Bồ Đào Nha", "th": "Tiếng Thái", "lo": "Tiếng Lào", "km": "Tiếng Khmer", "nl": "Tiếng Hà Lan",
    "pl": "Tiếng Ba Lan", "cs": "Tiếng Séc", "uk": "Tiếng Ukraina", "ar": "Tiếng Ả Rập", "id": "Tiếng Indonesia",
    "ms": "Tiếng Mã Lai", "la": "Tiếng Latinh",
}
HEADINGS_EN = {"vi": "Vietnamese", "en": "English", "fr": "French", "de": "German", "ru": "Russian",
               "zh": "Chinese", "ja": "Japanese", "ko": "Korean", "es": "Spanish"}
# ISO 639-2 / names some exporters write instead of the two-letter code
ALIASES = {"vie": "vi", "vietnamese": "vi", "tiếng việt": "vi", "eng": "en", "english": "en", "fre": "fr",
           "fra": "fr", "french": "fr", "ger": "de", "deu": "de", "german": "de", "rus": "ru", "russian": "ru",
           "chi": "zh", "zho": "zh", "chinese": "zh", "jpn": "ja", "japanese": "ja", "kor": "ko", "korean": "ko",
           "spa": "es", "spanish": "es", "ita": "it", "italian": "it", "por": "pt", "portuguese": "pt",
           "tha": "th", "dut": "nl", "nld": "nl", "pol": "pl", "ukr": "uk", "ara": "ar", "ind": "id"}
_CODE = re.compile(r"^[a-z]{2,3}$")


def normalize(code):
    """Two-letter primary code of a language field ("en-US" -> "en", "vie" -> "vi"); "" when unknown."""
    text = (code or "").strip().lower().replace("_", "-")
    if not text:
        return ""
    if text in ALIASES:
        return ALIASES[text]
    primary = text.split("-")[0]
    primary = ALIASES.get(primary, primary)
    return primary if _CODE.match(primary) else ""


def guess_from_text(text):
    text = text or ""
    if names.has_vietnamese_marks(text):
        return "vi"
    if re.search("[Ѐ-ӿ]", text):
        return "ru"
    if re.search("[぀-ヿ]", text):
        return "ja"
    if re.search("[가-힯]", text):
        return "ko"
    if re.search("[一-鿿]", text):
        return "zh"
    return ""


def guess(item):
    """Guessed language of an item from its title, container and authors (``en`` when nothing points elsewhere)."""
    for field in ("title", "container-title", "publisher"):
        found = guess_from_text(item.get(field, ""))
        if found:
            return found
    for name in item.get("author", []) or []:
        if names.is_vietnamese(name):
            return "vi"
    return "en"


def group_of(item):
    """The language group of an item: its ``language`` field when valid, else the guess."""
    return normalize(item.get("language")) or guess(item)


def heading(code, document_language="vi"):
    if document_language == "en":
        return HEADINGS_EN.get(code, code.upper())
    return HEADINGS.get(code, "Tiếng " + code.upper())


def group_rank(code, order=DEFAULT_ORDER):
    """Sort key of a group: listed languages first in the given order, then the rest by Vietnamese heading."""
    order = list(order or DEFAULT_ORDER)
    if code in order:
        return (0, order.index(code), ())
    return (1, 0, vt.sort_key(heading(code)))
