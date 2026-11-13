# SPDX-License-Identifier: AGPL-3.0-only
"""Pure rules of the save format check (save_format_check.py): what the warning offers, what is remembered, and what
the core save code is told (hst-save-format-check.patch, hst-save-hst-functions-as-values.patch). No UNO here.

The core save code reads the job's answer as: False cancels the save; True saves unchanged; named values Proceed and
ValueFunctions save, and that one save writes the cells calling those add-in functions as their current results
(.xls and .xlsx). The open document is never touched, so Save, Save As and Save a Copy leave its URL, title, undo
list and modified state exactly as a normal save would."""
from .vietnamese_calc_logic import FUNCTION_NAMES

CONVERT, KEEP, CANCEL = "convert", "keep", "cancel"
ASK = ""  # remembered "choice": ask every time (the default)
REMEMBERABLE = (CONVERT, KEEP)  # Hủy is never remembered: it would block every later save to these formats
ADDIN = "org.hst.office.vi.CalcFunctions"  # CalcAddIns.xcu: its methods are the functions of FUNCTION_NAMES
# filter name fragment -> file extension shown to the user, first match wins (vba_template.is_excel_filter filters)
EXTENSIONS = (("VBA", ".xlsm"), ("2007 XML Template", ".xltx"), ("Open XML Template", ".xltx"), ("2007", ".xlsx"),
              ("Open XML", ".xlsx"), ("Vorlage", ".xlt"), ("Template", ".xlt"))


def value_functions():
    """Programmatic names of the HST functions, as the formula tokens hold them (compared ignoring case)."""
    return tuple("%s.%s" % (ADDIN, name.lower()) for name in FUNCTION_NAMES)


def file_extension(filter_name):
    """The extension of the file a filter writes, as the user knows it: ".xlsx", ".xls", ..."""
    return next((ext for fragment, ext in EXTENSIONS if fragment in (filter_name or "")), ".xls")


def remembered(value):
    """A stored choice made usable: CONVERT or KEEP; anything else (empty, damaged, hand-edited) asks."""
    return value if value in REMEMBERABLE else ASK


def to_remember(choice, dont_ask):
    """The choice to store after the dialog, or None to store nothing (box not ticked, or Hủy)."""
    return choice if dont_ask and choice in REMEMBERABLE else None


def answer(choice):
    """The job's answer to the core save code for a choice (see the module doc). CONVERT gives (name, value) pairs,
    turned into com.sun.star.beans.NamedValue by the service."""
    if choice == CANCEL:
        return False
    if choice == CONVERT:
        return (("Proceed", True), ("ValueFunctions", value_functions()))
    return True
