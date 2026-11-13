# SPDX-License-Identifier: AGPL-3.0-only
"""The remembered answer of the save format warning, per user in /org.hasontech.hstoffice.SaveFormatCheck
(saveformatcheck.xcs): empty asks every time (the default); "convert" or "keep" is used without asking. Written only
when "Không hỏi lại" is ticked; Tùy chọn ▸ HST Office ▸ Đọc số và tiền shows it and turns the question back on."""
from . import diag_log
from .save_format_rules import ASK, CONVERT, KEEP, remembered

CONFIG_PATH = "/org.hasontech.hstoffice.SaveFormatCheck"
KEY = "Remembered"
PAGE_ORDER = (ASK, CONVERT, KEEP)  # entries of the options page list (utilities_texts.SAVE_OPTIONS)


def _access(ctx, writable):
    import uno
    provider = ctx.ServiceManager.createInstanceWithContext("com.sun.star.configuration.ConfigurationProvider", ctx)
    arg = uno.createUnoStruct("com.sun.star.beans.PropertyValue")
    arg.Name, arg.Value = "nodepath", CONFIG_PATH
    kind = "ConfigurationUpdateAccess" if writable else "ConfigurationAccess"
    return provider.createInstanceWithArguments("com.sun.star.configuration." + kind, (arg,))


def load(ctx):
    """The remembered choice (CONVERT or KEEP), or ASK; ASK also when the profile cannot be read."""
    try:
        return remembered(_access(ctx, False).getPropertyValue(KEY))
    except Exception:  # noqa: BLE001 - schema missing or profile unreadable: ask
        diag_log.exception("save_format_check")
        return ASK


def save(ctx, choice):
    """Store a choice (ASK turns the question back on). Returns False if it is not one or the write failed."""
    if choice != ASK and remembered(choice) != choice:
        return False
    try:
        node = _access(ctx, True)
        node.setPropertyValue(KEY, choice)
        node.commitChanges()
        return True
    except Exception:  # noqa: BLE001 - a failing write must never block the save
        diag_log.exception("save_format_check")
        return False


def page_index(choice):
    """Position of a choice in the options page list."""
    return PAGE_ORDER.index(remembered(choice))


def from_page_index(index):
    """The choice of an options page list position; ASK for no or a bad selection."""
    return PAGE_ORDER[index] if 0 <= index < len(PAGE_ORDER) else ASK
