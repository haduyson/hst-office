# SPDX-License-Identifier: AGPL-3.0-only
"""What the "Đọc số thành chữ" dialog writes: the words, the DOCSO/DOCTIEN formula, the error text. Pure Python."""
from . import number_words
from . import utilities_texts as T


def words(value, choice):
    """The words for `value` with the dialog `choice` (NumberWordsError for an unreadable value)."""
    if value is None or value == "":
        raise number_words.NumberWordsError("not-a-number", "")
    if choice["money"]:
        return number_words.read_money(value, choice["unit"], choice["sub_unit"], choice["options"])
    return number_words.read_number(value, choice["options"])


def error_text(exc):
    text = T.NUMBER_ERRORS.get(exc.code, exc.code)
    return text % exc.detail if "%s" in text else text


def formula(choice, source):
    """=DOCSO(A1) / =DOCTIEN(A1;"đồng";"xu";"ngàn linh"), leaving out trailing default arguments (Vietnamese: "đồng"
    without a sub-unit, so the default choice gives =DOCTIEN(A1); English: "dollar"/"cent")."""
    options = choice["options"].text()
    if not choice["money"]:
        args = [source] + (['"%s"' % options] if options else [])
        return "=DOCSO(%s)" % ";".join(args)
    english = choice["options"].language == "en"
    if english:
        defaults = (number_words.en.DEFAULT_UNIT, number_words.en.DEFAULT_SUB_UNIT)
    else:
        defaults = (number_words.DEFAULT_UNIT, number_words.DEFAULT_SUB_UNIT)
    args = [source]
    if options or (choice["unit"], choice["sub_unit"]) != defaults:
        args += ['"%s"' % choice["unit"].replace('"', '""'), '"%s"' % choice["sub_unit"].replace('"', '""')]
    if options:
        args.append('"%s"' % options)
    return "=DOCTIEN(%s)" % ";".join(args)
