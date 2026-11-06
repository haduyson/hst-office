# SPDX-License-Identifier: AGPL-3.0-only
"""Vietnamese text helpers for BODAU, TACHHO, TACHTEN and the "Sắp xếp theo tên" command. Pure Python (no uno).

`sort_key` follows the Vietnamese alphabet (a ă â b c d đ e ê … o ô ơ … u ư …) and compares tones after the letters,
in dictionary order: no tone, huyền, hỏi, ngã, sắc, nặng; case comes last. So "An" < "Ân" < "Bình" < "Đào".
"""
import re
import unicodedata

_SPACES = re.compile(r"\s+")
_MARKS = {"̆": "breve", "̂": "circumflex", "̛": "horn"}  # marks that make another letter (ă â ê ô ơ ư)
_TONES = {"̀": 1, "̉": 2, "̃": 3, "́": 4, "̣": 5}  # huyền hỏi ngã sắc nặng
_ALPHABET = ("a", "ă", "â", "b", "c", "d", "đ", "e", "ê", "f", "g", "h", "i", "j", "k", "l", "m", "n", "o", "ô", "ơ", "p",
             "q", "r", "s", "t", "u", "ư", "v", "w", "x", "y", "z")
_RANK = {letter: index for index, letter in enumerate(_ALPHABET)}
_LETTER_OFFSET = 0x10000  # letters sort after spaces, digits and punctuation (which keep their code point order)


def remove_diacritics(text):
    """BODAU: "Nguyễn Văn Đức" -> "Nguyen Van Duc"; other characters are kept."""
    decomposed = unicodedata.normalize("NFD", text or "")
    stripped = "".join(c for c in decomposed if unicodedata.category(c) != "Mn")
    return unicodedata.normalize("NFC", stripped.replace("đ", "d").replace("Đ", "D"))


def normalise_name(text):
    return _SPACES.sub(" ", (text or "").strip())


def split_name(text):
    """(họ đệm, tên) of a full name: the given name is the last word. "Nguyễn Thị Minh Khai" -> ("Nguyễn Thị Minh", "Khai");
    a single word is a given name only."""
    words = normalise_name(text).split(" ")
    if words == [""]:
        return "", ""
    return " ".join(words[:-1]), words[-1]


def family_name(text):
    """TACHHO: everything before the given name (family and middle names)."""
    return split_name(text)[0]


def given_name(text):
    """TACHTEN: the last word of the name."""
    return split_name(text)[1]


def _letters(text):
    """[(base letter, tone, is upper)] in reading order; base letters include ă â ê ô ơ ư đ."""
    result = []
    for char in unicodedata.normalize("NFD", text):
        if char in _TONES and result:
            base, _, upper = result[-1]
            result[-1] = (base, _TONES[char], upper)
        elif char in _MARKS and result:
            base, tone, upper = result[-1]
            result[-1] = (unicodedata.normalize("NFC", base + char), tone, upper)
        elif unicodedata.category(char) == "Mn" and result:
            continue  # any other accent does not change the order
        else:
            result.append((char.lower(), 0, char != char.lower()))
    return result


def sort_key(text):
    """Collation key for Vietnamese text (see the module docstring)."""
    letters = _letters(normalise_name(text))
    primary = tuple(_LETTER_OFFSET + _RANK[b] if b in _RANK else ord(b[0]) for b, _, _ in letters)
    return primary, tuple(t for _, t, _ in letters), tuple(u for _, _, u in letters)


def name_sort_key(full_name=None, family=None, given=None):
    """Key for "Sắp xếp theo tên": by given name, then by family and middle names. Give either the full name or
    the two parts (a sheet with separate "Họ đệm" and "Tên" columns)."""
    if full_name is not None:
        family, given = split_name(full_name)
    return sort_key(given or ""), sort_key(family or "")
