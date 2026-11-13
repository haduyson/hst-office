# SPDX-License-Identifier: AGPL-3.0-only
"""Defaults resolver of number and money reading (DOCSO, DOCTIEN, "Đọc số thành chữ"). Pure Python, no UNO, so the
dialog and the Sheets add-in functions can share it.

Precedence, highest first: the file's own default (user-defined document properties, number_words_file_default.py)
> the user's choice (profile, number_words_prefs.py) > the program default (owner: "đồng" without "xu", Vietnamese,
nghìn / lẻ / bốn, plain words). Each layer may be partial or damaged: only its valid entries count, so a hand-edited
profile or property falls back entry by entry. A unit always comes with its own sub-unit (an empty one when the layer
has none): "dollar" from one layer never meets "xu" from another."""

DEFAULTS = {"money": False, "unit": "đồng", "sub_unit": "", "thousand": "nghìn", "odd": "lẻ", "four": "bốn",
            "language": "vi", "formula": False}
# allowed values of the list choices, in the order of the dialog's list boxes
CHOICES = {"thousand": ("nghìn", "ngàn"), "odd": ("lẻ", "linh"), "four": ("bốn", "tư"), "language": ("vi", "en")}
FLAGS = ("money", "formula")
MAX_UNIT = 40  # characters of a unit name; longer text is not a unit


def clean_unit(value, fallback):
    """A unit as typed in the dialog (str, at most MAX_UNIT characters, no line break), else `fallback`."""
    if not isinstance(value, str):
        return fallback
    value = value.strip()
    return fallback if len(value) > MAX_UNIT or "\n" in value or "\r" in value else value


def valid_entries(layer):
    """Only the valid entries of one layer (a dict, possibly partial; anything else counts as empty)."""
    layer = layer if isinstance(layer, dict) else {}
    found = {key: layer[key] for key in FLAGS if isinstance(layer.get(key), bool)}
    found.update({key: layer[key] for key, allowed in CHOICES.items() if layer.get(key) in allowed})
    unit = clean_unit(layer.get("unit"), "")
    if unit:  # an empty unit is no choice at all: the pair comes from a lower layer
        found["unit"], found["sub_unit"] = unit, clean_unit(layer.get("sub_unit"), "")
    return found


def resolve(*layers):
    """The complete values: `layers` highest precedence first (file default, user choice), over DEFAULTS."""
    values = dict(DEFAULTS)
    for layer in reversed(layers):
        values.update(valid_entries(layer))
    return values


def unit_layer(pair):
    """A (unit, sub-unit) pair, or None, as a layer."""
    return {"unit": pair[0], "sub_unit": pair[1]} if pair else None
