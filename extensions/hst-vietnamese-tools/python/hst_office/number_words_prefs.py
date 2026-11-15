# SPDX-License-Identifier: AGPL-3.0-only
"""The user's default of number and money reading, per user in /org.hasontech.hstoffice.NumberWords
(numberwords.xcs): unit, sub-unit, money and number reading options (Tùy chọn ▸ HST Office ▸ Đọc số và tiền), and
what the "Đọc số thành chữ" dialog last used (number or money, text or formula). The dialog writes back what it
used, so the page and the dialog edit one default. Cells are never kept: they follow the selection.

It is the "user" layer of number_words_defaults: the dialog uses it, DOCSO()/DOCTIEN() in a cell never do. Everything
read back is checked there, so a damaged or hand-edited profile only falls back to the program default."""
from . import diag_log
from .number_words_defaults import DEFAULTS, options_key, resolve, valid_entries

CONFIG_PATH = "/org.hasontech.hstoffice.NumberWords"
KEYS = {"money": "Money", "formula": "Formula", "unit": "Unit", "sub_unit": "SubUnit",
        "money_options": "MoneyOptions", "number_options": "NumberOptions"}


def from_choice(choice, calc):
    """The entries an accepted dialog choice updates: the reading options of the kind it read (numbers or money);
    Writer has no text/formula choice, so it leaves the remembered one alone."""
    layer = {"money": choice["money"], "unit": choice["unit"], "sub_unit": choice["sub_unit"],
             options_key(choice["money"]): choice["options"].text()}
    if calc:
        layer["formula"] = bool(choice["formula"])
    return layer


def _access(ctx, writable):
    import uno
    provider = ctx.ServiceManager.createInstanceWithContext("com.sun.star.configuration.ConfigurationProvider", ctx)
    arg = uno.createUnoStruct("com.sun.star.beans.PropertyValue")
    arg.Name, arg.Value = "nodepath", CONFIG_PATH
    kind = "ConfigurationUpdateAccess" if writable else "ConfigurationAccess"
    return provider.createInstanceWithArguments("com.sun.star.configuration." + kind, (arg,))


def load(ctx):
    """The user's default (complete, checked); the program default when the profile has none or cannot be read."""
    try:
        node = _access(ctx, False)
        return resolve({key: node.getPropertyValue(name) for key, name in KEYS.items()})
    except Exception:  # noqa: BLE001 - schema missing or profile unreadable: the program default
        diag_log.exception("number_words")
        return dict(DEFAULTS)


def save(ctx, layer):
    """Write the valid entries of `layer` (the others keep their value). Returns False if the write failed."""
    entries = valid_entries(layer)
    try:
        node = _access(ctx, True)
        for key, value in entries.items():
            node.setPropertyValue(KEYS[key], value)
        node.commitChanges()
        return True
    except Exception:  # noqa: BLE001 - a failing write must not lose the words just written
        diag_log.exception("number_words")
        return False
