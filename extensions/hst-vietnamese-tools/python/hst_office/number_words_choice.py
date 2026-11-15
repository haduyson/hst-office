# SPDX-License-Identifier: AGPL-3.0-only
"""What the "Đọc số thành chữ" dialog writes: the words, the DOCSO/DOCTIEN formula, the error text. Pure Python."""
from . import number_words
from . import number_words_defaults as defaults
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


def _quoted(text):
    return '"%s"' % text.replace('"', '""')


def formula(choice, source, file_layer=None):
    """=DOCSO(A1) / =DOCTIEN(A1;"đồng";"xu";"ngàn linh"): the shortest formula that reads exactly like `choice`.
    An argument is left out only when what DOCSO/DOCTIEN use in its place (the file's default, else the program
    default: number_words_defaults) gives the same reading, so the cell always shows what the preview showed."""
    options = choice["options"].text()
    if not choice["money"]:
        same = defaults.number_args(file_layer, None).text() == options
        return "=DOCSO(%s)" % ";".join([source] + ([] if same else [_quoted(options)]))
    wanted = (choice["unit"], choice["sub_unit"], options)
    pair = [choice["unit"], choice["sub_unit"]]
    for args in ([], pair, pair + [options]):
        unit, sub_unit, parsed = defaults.money_args(file_layer, *(args + [None] * (3 - len(args))))
        if (unit, sub_unit, parsed.text()) == wanted:
            break
    return "=DOCTIEN(%s)" % ";".join([source] + [_quoted(arg) for arg in args])
