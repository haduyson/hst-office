# SPDX-License-Identifier: AGPL-3.0-only
"""Sheets add-in functions DOCSO, DOCTIEN, BODAU, TACHHO, TACHTEN (service org.hst.office.vi.CalcFunctions).

Calc finds the functions, their Vietnamese help and the "Tiếng Việt" category in CalcAddIns.xcu and the method types in
types/hst-calc-functions.rdb (interface org.hst.office.vi.XCalcFunctions). A bad argument (more than 15 integer digits,
an unknown reading option) raises IllegalArgumentException, which the cell shows as an error, never a wrong reading.

DOCSO and DOCTIEN get the calling document from Calc (the hidden caller argument `document`). An argument left out
takes the file's own default (user-defined properties HST.DocSo.* / HST.DocTien.*, number_words_file_default.py), else
the program default ("đồng", no "xu"); never the user's own default, so a file reads the same on every machine. A
changed file default shows after recalculation (the dialog recalculates; otherwise Ctrl+Shift+F9).
"""
import unohelper
from com.sun.star.lang import IllegalArgumentException, XServiceInfo

from . import number_words, vietnamese_text
from .vietnamese_calc_logic import FUNCTION_NAMES  # noqa: F401 - the names, for callers of this module

SERVICE_NAME = "org.hst.office.vi.CalcFunctions"
SERVICES = (SERVICE_NAME, "com.sun.star.sheet.AddIn")


def _text(value):
    """Optional argument (uno any): None when omitted; numbers become their text ("5" not "5.0")."""
    if value is None:
        return None
    if isinstance(value, float):
        return format(value, ".15g")
    return str(value)


def _file_layer(document):
    """The calling document's default (imported on first use: the component loads this module at start-up)."""
    from . import number_words_file_default
    return number_words_file_default.read(document)


def implementation():
    """The component class; imported lazily because XCalcFunctions exists only once the extension's types are loaded."""
    from org.hst.office.vi import XCalcFunctions  # noqa: N811 - UNO interface name

    class CalcFunctions(unohelper.Base, XCalcFunctions, XServiceInfo):
        def __init__(self, ctx):
            self.ctx = ctx

        def getImplementationName(self):
            return SERVICE_NAME

        def supportsService(self, name):
            return name in SERVICES

        def getSupportedServiceNames(self):
            return SERVICES

        @staticmethod
        def _guard(call):
            try:
                return call()
            except number_words.NumberWordsError as exc:
                raise IllegalArgumentException(str(exc), None, 0) from None

        def docso(self, document, number, options):
            from .number_words_defaults import number_args
            return self._guard(lambda: number_words.read_number(number, number_args(_file_layer(document),
                                                                                    _text(options))))

        def doctien(self, document, number, unit, sub_unit, options):
            from .number_words_defaults import money_args
            return self._guard(lambda: number_words.read_money(number, *money_args(
                _file_layer(document), _text(unit), _text(sub_unit), _text(options))))

        def bodau(self, text):
            return vietnamese_text.remove_diacritics(text)

        def tachho(self, text):
            return vietnamese_text.family_name(text)

        def tachten(self, text):
            return vietnamese_text.given_name(text)

    return CalcFunctions
