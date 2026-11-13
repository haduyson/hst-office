# SPDX-License-Identifier: AGPL-3.0-only
"""Strings of the citation commands and dialogs, in the UI language (owner decision 13/11/2026: Vietnamese or
English, unlike the other HST commands that are Vietnamese in every UI language).

The strings live in locales/citations-vi.json and locales/citations-en.json (same keys, checked by
tests/unit/test_citation_texts.py). Messages coming from the formatter and the importers stay Vietnamese.
"""
import json
import os

from .data_files import EXT_ROOT

_CACHE = {}


def language_of(locale):
    """"vi" for a Vietnamese UI locale, "en" for any other."""
    return "vi" if str(locale or "").lower().replace("_", "-").startswith("vi") else "en"


def ui_language(ctx):
    """The language the office UI is shown in (the effective locale, also when it follows the system)."""
    try:
        import uno
        provider = ctx.ServiceManager.createInstanceWithContext(
            "com.sun.star.configuration.ConfigurationProvider", ctx)
        arg = uno.createUnoStruct("com.sun.star.beans.PropertyValue")
        arg.Name, arg.Value = "nodepath", "/org.openoffice.Setup/L10N"
        node = provider.createInstanceWithArguments("com.sun.star.configuration.ConfigurationAccess", (arg,))
        return language_of(node.getPropertyValue("ooLocale"))
    except Exception:  # noqa: BLE001 - unknown: HST's default UI language
        return "vi"


def load_language(language):
    code = language_of(language)
    if code not in _CACHE:
        with open(os.path.join(EXT_ROOT, "locales", "citations-%s.json" % code), encoding="utf-8") as handle:
            _CACHE[code] = json.load(handle)
        _CACHE[code]["language"] = code
    return _CACHE[code]


def load(ctx):
    return load_language(ui_language(ctx))
