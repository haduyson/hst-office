# SPDX-License-Identifier: AGPL-3.0-only
"""The user's last choice in the "Đọc số thành chữ" dialog, kept per user in /org.hasontech.hstoffice.NumberWords
(numberwords.xcs): number or money, unit, sub-unit, reading options, language and text or formula. The cells are
never kept: they follow the selection. It is the "user" layer of number_words_defaults.resolve(); everything read
back goes through it, so a damaged or hand-edited profile only falls back to the program default."""
from . import diag_log
from .number_words_defaults import DEFAULTS, resolve

CONFIG_PATH = "/org.hasontech.hstoffice.NumberWords"
KEYS = {"money": "Money", "unit": "Unit", "sub_unit": "SubUnit", "thousand": "Thousand", "odd": "Odd", "four": "Four",
        "language": "Language", "formula": "Formula"}


def from_choice(choice):
    """The values to remember from an accepted dialog choice (number_words_dialog.NumberWordsDialog.choice)."""
    options = choice["options"]
    return resolve({"money": choice["money"], "unit": choice["unit"], "sub_unit": choice["sub_unit"],
                    "thousand": options.thousand, "odd": options.odd, "four": options.four,
                    "language": options.language, "formula": bool(choice.get("formula"))})


def _access(ctx, writable):
    import uno
    provider = ctx.ServiceManager.createInstanceWithContext("com.sun.star.configuration.ConfigurationProvider", ctx)
    arg = uno.createUnoStruct("com.sun.star.beans.PropertyValue")
    arg.Name, arg.Value = "nodepath", CONFIG_PATH
    kind = "ConfigurationUpdateAccess" if writable else "ConfigurationAccess"
    return provider.createInstanceWithArguments("com.sun.star.configuration." + kind, (arg,))


def load(ctx):
    """The user's last choice (cleaned); the program default when the profile has none or cannot be read."""
    try:
        node = _access(ctx, False)
        return resolve({key: node.getPropertyValue(name) for key, name in KEYS.items()})
    except Exception:  # noqa: BLE001 - schema missing or profile unreadable: open with the program default
        diag_log.exception("number_words")
        return dict(DEFAULTS)


def save(ctx, values, calc):
    """Remember `values`; Writer has no text/formula choice, so it leaves the remembered one alone."""
    try:
        node = _access(ctx, True)
        for key, name in KEYS.items():
            if key != "formula" or calc:
                node.setPropertyValue(name, values[key])
        node.commitChanges()
    except Exception:  # noqa: BLE001 - a failing write must not lose the words just written
        diag_log.exception("number_words")
