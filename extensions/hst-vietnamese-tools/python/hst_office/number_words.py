# SPDX-License-Identifier: AGPL-3.0-only
"""Numbers read as Vietnamese (or English) words: DOCSO, DOCTIEN, the "Đọc số thành chữ" dialog and the Writer command.

Pure Python (no uno). Defaults follow the owner's decision: "nghìn" and "lẻ" (105 = "một trăm lẻ năm"), "bốn" after
"mươi"; options switch to "ngàn", "linh" and "tư". Zero groups after a larger unit read "không trăm" (1.000.001 = "một
triệu không trăm lẻ một"), the accounting convention. At most 15 integer digits (what a spreadsheet number holds
exactly): more raises NumberWordsError instead of reading a rounded number. The first letter is a capital.
"""
import math
import re
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation

from . import number_words_en as en

MAX_DIGITS = 15
DIGITS = ("không", "một", "hai", "ba", "bốn", "năm", "sáu", "bảy", "tám", "chín")
_SPLIT = re.compile(r"[\s,;]+")
# option word (without diacritics) -> (setting, value)
_OPTION_WORDS = {"nghin": ("thousand", "nghìn"), "ngan": ("thousand", "ngàn"), "le": ("odd", "lẻ"), "linh": ("odd", "linh"),
                 "bon": ("four", "bốn"), "tu": ("four", "tư"), "vi": ("language", "vi"), "viet": ("language", "vi"),
                 "en": ("language", "en"), "anh": ("language", "en"), "english": ("language", "en")}
_IGNORED_WORDS = {"tieng", "doc"}  # "tiếng Anh", "đọc ngàn"
_STRIP_TONES = str.maketrans("àáảãạăằắẳẵặâầấẩẫậđèéẻẽẹêềếểễệìíỉĩịòóỏõọôồốổỗộơờớởỡợùúủũụưừứửữựỳýỷỹỵ",
                             "aaaaaaaaaaaaaaaaadeeeeeeeeeeeiiiiiooooooooooooooooouuuuuuuuuuuyyyyy")


class NumberWordsError(ValueError):
    """`code`: too-many-digits, not-a-number or bad-option (shown to the user through the caller's strings)."""

    def __init__(self, code, detail=""):
        super().__init__("%s%s" % (code, ": " + detail if detail else ""))
        self.code, self.detail = code, detail


class Options:
    def __init__(self, thousand="nghìn", odd="lẻ", four="bốn", language="vi"):
        self.thousand, self.odd, self.four, self.language = thousand, odd, four, language

    def text(self):
        """The option text DOCSO/DOCTIEN accept for these options ("" for the defaults)."""
        words = [w for w, default in ((self.thousand, "nghìn"), (self.odd, "lẻ"), (self.four, "bốn")) if w != default]
        return " ".join(words + (["en"] if self.language == "en" else []))


def parse_options(text):
    """Options from a free text such as "ngàn linh", "tư", "en" (any case, with or without diacritics)."""
    options = Options()
    for word in _SPLIT.split((text or "").strip().lower()):
        key = word.translate(_STRIP_TONES)
        if not key or key in _IGNORED_WORDS:
            continue
        if key not in _OPTION_WORDS:
            raise NumberWordsError("bad-option", word)
        setattr(options, *_OPTION_WORDS[key])
    return options


def to_decimal(value):
    """Decimal of a cell value: float/int/Decimal or a number text (see parse_number_text). Floats keep 15 digits."""
    if isinstance(value, bool):
        value = int(value)
    if isinstance(value, float):
        if not math.isfinite(value):
            raise NumberWordsError("not-a-number", repr(value))
        return Decimal(format(value, ".15g"))
    if isinstance(value, int):
        return Decimal(value)
    if isinstance(value, Decimal):
        if not value.is_finite():
            raise NumberWordsError("not-a-number", str(value))
        return value
    return parse_number_text(str(value))


_NUMBER_TEXT = re.compile(r"^([-−+]?)\s*(?:\$|₫)?\s*([0-9][0-9., ]*)\s*(?:đ|đồng|vnd|vnđ|₫|usd|\$)?$", re.I)


def parse_number_text(text):
    """A number typed in a document: "1.000.001" and "1 000 001" (Vietnamese grouping), "1,000,001", "3,5" or "3.5",
    "1.234,5", "1,234.5"; an optional sign and currency (đ, đồng, VND, ₫, USD, $). Raises not-a-number otherwise."""
    match = _NUMBER_TEXT.match((text or "").strip().replace(" ", " ").replace(" ", " "))
    if not match:
        raise NumberWordsError("not-a-number", text)
    sign, body = match.group(1), re.sub(r"(?<=\d) (?=\d{3}(?!\d))", "", match.group(2).strip())  # 1 000 001
    if " " in body:
        raise NumberWordsError("not-a-number", text)
    dot, comma = body.rfind("."), body.rfind(",")
    if dot >= 0 and comma >= 0:
        decimal_mark = "." if dot > comma else ","
    elif dot >= 0 or comma >= 0:
        mark = "." if dot >= 0 else ","
        parts = body.split(mark)
        # one mark followed by exactly three digits groups thousands (1.000 = một nghìn); otherwise it is the decimal mark
        decimal_mark = None if len(parts) > 2 or len(parts[1]) == 3 else mark
    else:
        decimal_mark = None
    whole, _, fraction = body.partition(decimal_mark) if decimal_mark else (body, "", "")
    groups = re.split(r"[.,]", whole)
    if (len(groups) > 1 and not (1 <= len(groups[0]) <= 3 and all(len(g) == 3 for g in groups[1:]))) \
            or not all(groups) or not fraction.isdigit() and fraction:
        raise NumberWordsError("not-a-number", text)
    try:
        number = Decimal("".join(groups) + ("." + fraction if fraction else ""))
    except InvalidOperation:
        raise NumberWordsError("not-a-number", text) from None
    return -number if sign in ("-", "−") else number


def _check_digits(whole):
    if whole >= 10 ** MAX_DIGITS:
        raise NumberWordsError("too-many-digits", str(whole))


def _triple(number, full, options):
    """Words of 0 < number < 1000; `full` reads "không trăm" and "lẻ" (a group after a larger unit)."""
    hundreds, tens, units = number // 100, number // 10 % 10, number % 10
    words = [DIGITS[hundreds], "trăm"] if full or hundreds else []
    if tens == 0:
        if units and words:
            words.append(options.odd)
        if units:
            words.append(DIGITS[units])
    elif tens == 1:
        words.append("mười")
        if units:
            words.append("lăm" if units == 5 else DIGITS[units])
    else:
        words += [DIGITS[tens], "mươi"]
        if units:
            words.append({1: "mốt", 4: options.four, 5: "lăm"}.get(units, DIGITS[units]))
    return words


def _below_billion(number, leading, options):
    words, started = [], not leading
    for value, unit in (((number // 10 ** 6) % 1000, "triệu"), ((number // 1000) % 1000, options.thousand), (number % 1000, "")):
        if value:
            words += _triple(value, started, options) + ([unit] if unit else [])
            started = True
    return words


def integer_words(number, options):
    """Vietnamese words of a non-negative int (list of words)."""
    if number == 0:
        return [DIGITS[0]]
    if number < 10 ** 9:
        return _below_billion(number, True, options)
    high, low = divmod(number, 10 ** 9)
    return integer_words(high, options) + ["tỷ"] + (_below_billion(low, False, options) if low else [])


def capitalise(text):
    return text[:1].upper() + text[1:]


def _split(number):
    """(negative, whole int, fraction digits text) of a Decimal, refusing more than 15 integer digits."""
    negative, number = number < 0, abs(number)
    whole = int(number)
    _check_digits(whole)
    digits = format(number, "f").partition(".")[2].rstrip("0")
    return bool(negative and (whole or digits)), whole, digits


def read_number(value, options=None):
    """DOCSO: "Một trăm lẻ năm", "Âm hai phẩy năm", "Ba phẩy một bốn"; English with options.language == "en"."""
    options = options or Options()
    negative, whole, digits = _split(to_decimal(value))
    if options.language == "en":
        return capitalise(en.number_words(negative, whole, digits))
    words = (["âm"] if negative else []) + integer_words(whole, options)
    if digits:
        words += ["phẩy"] + [DIGITS[int(d)] for d in digits]
    return capitalise(" ".join(words))


def read_money(value, unit=None, sub_unit=None, options=None):
    """DOCTIEN: "Mười triệu đồng chẵn", "Một nghìn đồng năm mươi xu". `unit`/`sub_unit` None = the default of the
    language (đồng/xu, dollar/cent); sub_unit "" rounds to a whole amount. English: "Ten dollars and fifty cents"."""
    options = options or Options()
    english = options.language == "en"
    unit = (en.DEFAULT_UNIT if english else "đồng") if unit is None else unit.strip()
    sub_unit = (en.DEFAULT_SUB_UNIT if english else "xu") if sub_unit is None else sub_unit.strip()
    amount = to_decimal(value).quantize(Decimal("0.01") if sub_unit else Decimal(1), rounding=ROUND_HALF_UP)
    negative, whole, digits = _split(amount)
    cents = int(digits.ljust(2, "0")) if digits else 0
    if english:
        return capitalise(en.money_words(negative, whole, cents, unit, sub_unit))
    words = ["âm"] if negative else []
    if whole or not cents:
        words += integer_words(whole, options) + ([unit] if unit else [])
    words += integer_words(cents, options) + [sub_unit] if cents else ["chẵn"]
    return capitalise(" ".join(words))
