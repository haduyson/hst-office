# SPDX-License-Identifier: AGPL-3.0-only
"""VND() and USD(): the number-words functions Vietnamese Excel users know from add-ins, with the arguments and the
reading those add-ins document publicly (tutorials and the authors' own posts; no add-in code was used). Pure Python,
built on number_words / number_words_en.

Two argument layouts are accepted, told apart by the arguments themselves:
  - add-in workbook layout:  VND(number; [add_unit]; [charset]; [unit]; [sub_unit])   USD(number; [add_unit])
      add_unit TRUE appends the unit ("đồng" / "dollar") and reads two decimals as the sub-unit ("xu" / "cent");
      without it only the number is read, decimals as "phẩy" and a two-digit number ("Chín phẩy năm mươi").
  - XLL layout (a text third argument for VND, a text second argument for USD, or a sixth argument for VND):
      VND(amount; [charset]; [unit]; [sub_unit]; [sub_unit_factor]; [grouping])
      USD(amount; [unit]; [sub_unit]; [sub_unit_factor]; [grouping])
      the unit is always read; sub_unit_factor turns the fraction into sub-units (default 1 = hundredths:
      12,5 with "hào" and 10 reads "năm hào"); grouping TRUE puts ", " after each triệu/ngàn/tỷ group.
The charset argument (TCVN3, VNI, Unicode) is accepted and ignored: the result is always Unicode.

Reading: "ngàn" and "lẻ" as both add-ins print by default, "mốt", "lăm", "bốn", "không trăm" inside a number,
"tỷ", "Âm" for negatives, a capital first letter, no final period and no "chẵn". At most 15 integer digits.
"""
from decimal import ROUND_HALF_UP, Decimal

from . import number_words as nw
from . import number_words_en as en

READING = nw.Options(thousand="ngàn", odd="lẻ", four="bốn")
VND_UNIT, VND_SUB_UNIT = "đồng", "xu"
SCALES = ("triệu", "ngàn", "tỷ")


def _missing(value):
    return value is None or value == ""


def _flag(value, default=False):
    """A TRUE/FALSE argument: Calc passes a boolean as the number 1 or 0; a text "TRUE"/"FALSE" is accepted too."""
    if _missing(value):
        return default
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return value != 0
    if isinstance(value, str) and value.strip().upper() in ("TRUE", "FALSE", "1", "0"):
        return value.strip().upper() in ("TRUE", "1")
    raise nw.NumberWordsError("bad-option", str(value))


def _text(value, default):
    """A unit name; left out (None) gives the default, an empty text "" asks for no sub-unit (whole units)."""
    if value is None:
        return default
    if isinstance(value, float):
        return format(value, ".15g")
    if not isinstance(value, str):
        raise nw.NumberWordsError("bad-option", str(value))
    return value.strip()


def _factor(value):
    """The sub-unit factor: 1 (or none) means hundredths, otherwise how many sub-units make one unit."""
    if _missing(value):
        return 100
    if isinstance(value, str):
        value = nw.to_decimal(value)
    factor = Decimal(format(float(value), ".15g")) if isinstance(value, float) else Decimal(value)
    if factor <= 0:
        raise nw.NumberWordsError("bad-option", str(value))
    return 100 if factor == 1 else factor


def _amount(value):
    if isinstance(value, (tuple, list)):
        raise nw.NumberWordsError("not-a-number", "range")
    return nw.to_decimal(value)


def _split_money(amount, factor):
    """(negative, whole, sub-units) of an amount, the fraction rounded half up to whole sub-units."""
    negative, amount = amount < 0, abs(amount)
    whole = int(amount)
    sub = int(((amount - whole) * factor).quantize(Decimal(1), rounding=ROUND_HALF_UP))
    if sub >= factor:
        whole, sub = whole + 1, 0
    if whole >= 10 ** nw.MAX_DIGITS:
        raise nw.NumberWordsError("too-many-digits", str(whole))
    return bool(negative and (whole or sub)), whole, sub


def _vi_words(number, grouping=False):
    words = nw.integer_words(number, READING)
    if not grouping:
        return words
    out = []
    for index, word in enumerate(words):
        following = words[index + 1] if index + 1 < len(words) else None
        out.append(word + "," if word in SCALES and following and following not in SCALES else word)
    return out


def _vi_fraction(digits):
    """Two decimals read as a two-digit number: "50" (from ,5) "năm mươi", "04" "không bốn"."""
    value = int(digits.ljust(2, "0")[:2])
    return ["không", nw.DIGITS[value]] if value < 10 else nw.integer_words(value, READING)


def _vi_number(amount):
    negative, whole, cents = _split_money(amount, 100)
    words = (["âm"] if negative else []) + nw.integer_words(whole, READING)
    if cents:
        words += ["phẩy"] + _vi_fraction("%02d" % cents)
    return nw.capitalise(" ".join(words))


def _vi_money(amount, unit, sub_unit, factor=100, grouping=False):
    if not sub_unit:
        amount, factor = amount.quantize(Decimal(1), rounding=ROUND_HALF_UP), 100
    negative, whole, sub = _split_money(amount, factor)
    words = ["âm"] if negative else []
    if whole or not sub:
        words += _vi_words(whole, grouping) + ([unit] if unit else [])
    if sub:
        words += _vi_words(sub, grouping) + ([sub_unit] if sub_unit else [])
    return nw.capitalise(" ".join(words))


def vnd(number, arg2=None, arg3=None, arg4=None, arg5=None, arg6=None):
    """VND() in either layout (see the module doc)."""
    amount = _amount(number)
    if isinstance(arg3, str) and arg3 != "" or not _missing(arg6):
        return _vi_money(amount, _text(arg3, VND_UNIT), _text(arg4, VND_SUB_UNIT), _factor(arg5), _flag(arg6))
    if not _flag(arg2):
        return _vi_number(amount)
    return _vi_money(amount, _text(arg4, VND_UNIT), _text(arg5, VND_SUB_UNIT))


def _en_money(amount, unit, sub_unit, factor=100):
    if not sub_unit:
        amount, factor = amount.quantize(Decimal(1), rounding=ROUND_HALF_UP), 100
    negative, whole, sub = _split_money(amount, factor)
    return nw.capitalise(en.money_words(negative, whole, sub, unit, sub_unit))


def _en_number(amount):
    negative, whole, cents = _split_money(amount, 100)
    return nw.capitalise(en.number_words(negative, whole, ("%02d" % cents).rstrip("0") if cents else ""))


_EN_NUMBER_WORDS = frozenset(en.ONES + en.TENS[2:])


def _en_grouped(text):
    """", " after thousand/million/... when more number words follow ("Two million, five hundred dollars")."""
    words = text.split(" ")
    for index, word in enumerate(words[:-1]):
        if word in en.SCALES[1:] and words[index + 1].split("-")[0].lower() in _EN_NUMBER_WORDS:
            words[index] = word + ","
    return " ".join(words)


def usd(number, arg2=None, arg3=None, arg4=None, arg5=None):
    """USD() in either layout (see the module doc): English words, "dollar"/"cent" by default."""
    amount = _amount(number)
    if isinstance(arg2, str) and arg2 != "" and arg2.strip().upper() not in ("TRUE", "FALSE"):
        text = _en_money(amount, _text(arg2, en.DEFAULT_UNIT), _text(arg3, en.DEFAULT_SUB_UNIT), _factor(arg4))
        return _en_grouped(text) if _flag(arg5) else text
    if not _flag(arg2):
        return _en_number(amount)
    return _en_money(amount, en.DEFAULT_UNIT, en.DEFAULT_SUB_UNIT)
