# SPDX-License-Identifier: AGPL-3.0-only
"""Defaults of number and money reading (DOCSO, DOCTIEN, "Đọc số thành chữ"). Pure Python, no UNO, shared by the
dialog, the options page and the Sheets add-in functions.

Layers, highest first: the file's own default (user-defined document properties, number_words_file_default.py) >
the user's default (Tùy chọn ▸ HST Office ▸ Đọc số và tiền, also updated by the dialog: number_words_prefs.py) > the
program default (owner: "đồng" without "xu", nghìn / lẻ / bốn, Vietnamese, plain words).
  * The dialog uses every layer (resolve).
  * DOCSO()/DOCTIEN() with an argument left out use the FILE layer only, never the user's, so a file reads the
    same on every machine; an argument written in the formula always wins (number_args, money_args).
Each layer may be partial or damaged: only its valid entries count. A unit always comes with its own sub-unit:
"dollar" from one layer never meets "xu" from another. Reading options are kept as the option text DOCSO/DOCTIEN
accept ("" = nghìn lẻ bốn in Vietnamese), one for numbers and one for money."""
from . import number_words

DEFAULTS = {"money": False, "formula": False, "unit": number_words.DEFAULT_UNIT,
            "sub_unit": number_words.DEFAULT_SUB_UNIT, "number_options": "", "money_options": ""}
# the reading choices, in the order of the list boxes of the dialog and the options page
CHOICES = {"thousand": ("nghìn", "ngàn"), "odd": ("lẻ", "linh"), "four": ("bốn", "tư"), "language": ("vi", "en")}
FLAGS = ("money", "formula")
OPTIONS = ("number_options", "money_options")
MAX_UNIT = 40  # characters of a unit name; longer text is not a unit


def options_key(money):
    return "money_options" if money else "number_options"


def clean_unit(value, fallback):
    """A unit as typed (str, at most MAX_UNIT characters, no line break), else `fallback`."""
    if not isinstance(value, str):
        return fallback
    value = value.strip()
    return fallback if len(value) > MAX_UNIT or "\n" in value or "\r" in value else value


def clean_options(value):
    """The canonical option text of `value` ("ngàn linh"), or None when it is not an option text."""
    if not isinstance(value, str):
        return None
    try:
        return number_words.parse_options(value).text()
    except number_words.NumberWordsError:
        return None


def option_indexes(text):
    """{choice: list box index} of an option text (bad text: the program default)."""
    options = number_words.parse_options(clean_options(text) or "")
    return {key: allowed.index(getattr(options, key)) for key, allowed in CHOICES.items()}


def options_text(indexes):
    """The option text of {choice: list box index} (an index out of range counts as the first entry)."""
    picked = {key: allowed[indexes.get(key, 0) if 0 <= indexes.get(key, 0) < len(allowed) else 0]
              for key, allowed in CHOICES.items()}
    return number_words.Options(**picked).text()


def valid_entries(layer):
    """Only the valid entries of one layer (a dict, possibly partial; anything else counts as empty)."""
    layer = layer if isinstance(layer, dict) else {}
    found = {key: layer[key] for key in FLAGS if isinstance(layer.get(key), bool)}
    for key in OPTIONS:
        text = clean_options(layer.get(key))
        if text is not None:
            found[key] = text
    unit = clean_unit(layer.get("unit"), "")
    if unit:  # an empty unit is no choice at all: the pair comes from a lower layer
        found["unit"], found["sub_unit"] = unit, clean_unit(layer.get("sub_unit"), "")
    return found


def resolve(*layers):
    """The complete values: `layers` highest precedence first (file default, user default), over DEFAULTS."""
    values = dict(DEFAULTS)
    for layer in reversed(layers):
        values.update(valid_entries(layer))
    return values


def number_args(file_layer, options):
    """DOCSO's reading options: the `options` argument when written (None = left out), else the file's."""
    if options is None:
        options = valid_entries(file_layer).get("number_options", "")
    return number_words.parse_options(options)


def money_args(file_layer, unit, sub_unit, options):
    """DOCTIEN's (unit, sub-unit, Options): written arguments win (None = left out); a left-out unit takes the
    file's unit pair (a written sub-unit still wins), else the default of the language, like read_money()."""
    found = valid_entries(file_layer)
    parsed = number_words.parse_options(found.get("money_options", "") if options is None else options)
    if unit is None and "unit" in found:
        unit, sub_unit = found["unit"], found["sub_unit"] if sub_unit is None else sub_unit
    english = parsed.language == "en"
    if unit is None:
        unit = number_words.en.DEFAULT_UNIT if english else number_words.DEFAULT_UNIT
    if sub_unit is None:
        sub_unit = number_words.en.DEFAULT_SUB_UNIT if english else number_words.DEFAULT_SUB_UNIT
    return unit.strip(), sub_unit.strip(), parsed
