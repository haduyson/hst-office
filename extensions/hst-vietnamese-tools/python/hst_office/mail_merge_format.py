# SPDX-License-Identifier: AGPL-3.0-only
"""Trộn thư: how a merged value is shown. Pure Python (no UNO): the format kinds offered for a column, the vi-VN
number-format codes the fields carry (the engine formats the merged documents with them) and the same rendering in
Python for the preview, the recipient table and file names.

Kinds: "text" (as in the list), "number" (1.234.567), "number2" (1.234.567,50), "date" (07/03/1985), "date_long"
(ngày 07 tháng 03 năm 1985), "words" (Một triệu năm trăm nghìn) and "money_words" (… đồng chẵn). The two word kinds
cannot be number formats: the staging copy has a computed column for each (mail_merge_table.computed_columns) and
the field points to that column."""
import datetime
from decimal import ROUND_HALF_UP, Decimal

from . import number_words

TEXT, NUMBER, NUMBER2, DATE, DATE_LONG, WORDS, MONEY_WORDS = (
    "text", "number", "number2", "date", "date_long", "words", "money_words")
# column kinds of the recipient list
COL_TEXT, COL_NUMBER, COL_DATE = "text", "number", "date"
# number-format codes in the vi-VN locale ("." groups thousands, "," is the decimal separator)
CODES = {NUMBER: "#.##0", NUMBER2: "#.##0,00", DATE: "DD/MM/YYYY", DATE_LONG: '"ngày "DD" tháng "MM" năm "YYYY'}
# suffix of the computed column a word kind reads
WORD_SUFFIX = {WORDS: " (bằng chữ)", MONEY_WORDS: " (tiền bằng chữ)"}
KINDS_FOR_COLUMN = {COL_NUMBER: (NUMBER, NUMBER2, WORDS, MONEY_WORDS), COL_DATE: (DATE, DATE_LONG), COL_TEXT: (TEXT,)}
NULL_DATE = datetime.date(1899, 12, 30)  # day 0 of spreadsheet date numbers


def default_kind(column_kind, values=()):
    """The kind a newly inserted field gets: grouped whole numbers unless the column has fractions, dd/mm/yyyy."""
    if column_kind == COL_NUMBER:
        return NUMBER2 if any(isinstance(v, float) and v != int(v) for v in values if v is not None) else NUMBER
    return DATE if column_kind == COL_DATE else TEXT


def word_column(column, kind):
    return column + WORD_SUFFIX[kind]


def split_word_column(name):
    """(base column, word kind) for a computed column name, else (name, None)."""
    for kind, suffix in WORD_SUFFIX.items():
        if name.endswith(suffix):
            return name[:-len(suffix)], kind
    return name, None


def kind_of_field(column, code, database_format):
    """The kind of a field in the document from its column, its format code and its DataBaseFormat flag."""
    base, word = split_word_column(column)
    if word:
        return base, word
    if not database_format:
        for kind, known in CODES.items():
            if known == code:
                return base, kind
    return base, TEXT


def group_digits(whole):
    text = str(abs(whole))
    groups = []
    while text:
        groups.insert(0, text[-3:])
        text = text[:-3]
    return ("-" if whole < 0 else "") + ".".join(groups or ["0"])


def format_number(value, decimals=0):
    """1500000 -> "1.500.000"; decimals=2: 1234.5 -> "1.234,50" (half up, like the office)."""
    quantum = Decimal(1).scaleb(-decimals)
    amount = Decimal(str(value)).quantize(quantum, rounding=ROUND_HALF_UP)
    whole = int(amount)
    text = group_digits(whole) if whole or amount >= 0 else "-0"
    if decimals:
        text += "," + ("%s" % abs(amount - whole)).split(".")[1].ljust(decimals, "0")[:decimals]
    return text


def to_date(value):
    if isinstance(value, datetime.date):
        return value
    return NULL_DATE + datetime.timedelta(days=int(float(value)))


def plain_number(value):
    """A number as typed in the list: no grouping, no ".0" for whole numbers."""
    return str(int(value)) if float(value) == int(value) else ("%.10f" % value).rstrip("0").replace(".", ",")


def render(kind, value, words=None):
    """The text a field of `kind` shows for `value` (str, float or None). `words`: number-words settings
    (number_words_defaults.resolve values); None = program defaults. Values that do not fit the kind are shown as
    they are, so a stray text in a number column never breaks the preview."""
    if value is None or value == "":
        return ""
    if isinstance(value, str):
        return value
    try:
        if kind in (NUMBER, NUMBER2):
            return format_number(value, 2 if kind == NUMBER2 else 0)
        if kind == DATE:
            return to_date(value).strftime("%d/%m/%Y")
        if kind == DATE_LONG:
            day = to_date(value)
            return "ngày %02d tháng %02d năm %d" % (day.day, day.month, day.year)
        if kind in (WORDS, MONEY_WORDS):
            return read_words(kind, value, words)
    except (ValueError, OverflowError, ArithmeticError, number_words.NumberWordsError):
        pass
    return plain_number(value)


def read_words(kind, value, words=None):
    words = words or {}
    if kind == WORDS:
        return number_words.read_number(value, number_words.parse_options(words.get("number_options", "")))
    return number_words.read_money(value, words.get("unit"), words.get("sub_unit"),
                                   number_words.parse_options(words.get("money_options", "")))


def display(column_kind, value):
    """How the recipient table and file names show a value of a column of `column_kind`."""
    return render(default_kind(column_kind, (value,)), value)
