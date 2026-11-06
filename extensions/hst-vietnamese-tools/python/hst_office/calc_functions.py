# SPDX-License-Identifier: AGPL-3.0-only
"""Sheets add-in functions DOCSO, DOCTIEN, BODAU, TACHHO, TACHTEN (service org.hst.office.vi.CalcFunctions).

Calc finds the functions, their Vietnamese help and the "Tiếng Việt" category in CalcAddIns.xcu and the method types in
types/hst-calc-functions.rdb (interface org.hst.office.vi.XCalcFunctions). A bad argument (more than 15 integer digits,
an unknown reading option) raises IllegalArgumentException, which the cell shows as an error, never a wrong reading.
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

        def docso(self, number, options):
            return self._guard(lambda: number_words.read_number(number, number_words.parse_options(_text(options))))

        def doctien(self, number, unit, sub_unit, options):
            return self._guard(lambda: number_words.read_money(number, _text(unit), _text(sub_unit),
                                                               number_words.parse_options(_text(options))))

        def bodau(self, text):
            return vietnamese_text.remove_diacritics(text)

        def tachho(self, text):
            return vietnamese_text.family_name(text)

        def tachten(self, text):
            return vietnamese_text.given_name(text)

    return CalcFunctions
