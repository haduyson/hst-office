# SPDX-License-Identifier: AGPL-3.0-only
"""English number and money words for DOCSO/DOCTIEN with the "en" option (export invoices in USD).

British usage, as taught in Vietnam: "one hundred and five", "twenty-one", "one thousand and five";
money: "One hundred dollars and fifty cents". Called by number_words with the sign, the whole part (int, at most
15 digits, checked there) and the fraction digits.
"""

DEFAULT_UNIT, DEFAULT_SUB_UNIT = "dollar", "cent"
ONES = ("zero", "one", "two", "three", "four", "five", "six", "seven", "eight", "nine", "ten", "eleven", "twelve",
        "thirteen", "fourteen", "fifteen", "sixteen", "seventeen", "eighteen", "nineteen")
TENS = ("", "", "twenty", "thirty", "forty", "fifty", "sixty", "seventy", "eighty", "ninety")
SCALES = ("", "thousand", "million", "billion", "trillion")
# plural of the units people write in English; any other unit is used as typed
PLURALS = {"dollar": "dollars", "cent": "cents", "euro": "euros", "pound": "pounds", "penny": "pence"}


def _below_hundred(number):
    if number < 20:
        return ONES[number]
    tens, units = divmod(number, 10)
    return TENS[tens] + ("-" + ONES[units] if units else "")


def _below_thousand(number):
    hundreds, rest = divmod(number, 100)
    words = [ONES[hundreds], "hundred"] if hundreds else []
    if rest:
        words += (["and"] if hundreds else []) + [_below_hundred(rest)]
    return words


def integer_words(number):
    """English words of a non-negative int below 10**15 (list of words)."""
    if number == 0:
        return [ONES[0]]
    groups, scale = [], 0
    while number:
        number, group = divmod(number, 1000)
        groups.append((group, scale))
        scale += 1
    words = []
    for group, scale in reversed(groups):
        if group:
            words += _below_thousand(group) + ([SCALES[scale]] if scale else [])
    last = groups[0][0]
    if len(groups) > 1 and 0 < last < 100:
        words.insert(len(words) - 1, "and")  # "one thousand and five"
    return words


def number_words(negative, whole, digits):
    words = (["minus"] if negative else []) + integer_words(whole)
    if digits:
        words += ["point"] + [ONES[int(d)] for d in digits]
    return " ".join(words)


def _unit(name, count):
    return PLURALS.get(name.lower(), name) if count != 1 else name


def money_words(negative, whole, cents, unit, sub_unit):
    words = ["minus"] if negative else []
    if whole or not cents:
        words += integer_words(whole) + ([_unit(unit, whole)] if unit else [])
    if cents:
        words += (["and"] if whole else []) + integer_words(cents) + ([_unit(sub_unit, cents)] if sub_unit else [])
    return " ".join(words)
