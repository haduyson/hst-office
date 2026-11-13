# SPDX-License-Identifier: AGPL-3.0-only
"""Tùy chọn ▸ HST Office ▸ Đọc số và tiền (OptionsDialog.xcu, dialogs/NumberWords.xdl): the user's default of
number reading (DOCSO column) and money reading (DOCTIEN column: unit, sub-unit, reading options).

It is the "user" layer of number_words_defaults, kept by number_words_prefs: the dialog "Đọc số thành chữ" opens
with it (below a file's own default) and writes back what it used. DOCSO()/DOCTIEN() in a cell never read it.
Saved on OK; Cancel keeps the old values. An empty unit is not a unit: the saved one stays."""
import unohelper
from com.sun.star.awt import XContainerWindowEventHandler
from com.sun.star.lang import XServiceInfo

from . import diag_log
from . import utilities_texts as T
from .number_words_defaults import CHOICES, option_indexes, options_text

HANDLER_NAME = "org.hst.office.vi.OptionsNumberWords"
METHODS = ("external_event",)
COLUMNS = {"n": "number_options", "m": "money_options"}  # control name prefix -> entry


def page_layer(selected, unit, sub_unit):
    """Pure: the layer to save from {prefix: {choice: list index}} and the two unit fields."""
    layer = {key: options_text(selected.get(prefix, {})) for prefix, key in COLUMNS.items()}
    layer.update(unit=unit.strip(), sub_unit=sub_unit.strip())
    return layer


class NumberWordsOptionsHandler(unohelper.Base, XServiceInfo, XContainerWindowEventHandler):
    def __init__(self, ctx):
        self.ctx = ctx

    def getImplementationName(self):
        return HANDLER_NAME

    def supportsService(self, name):
        return name in self.getSupportedServiceNames()

    def getSupportedServiceNames(self):
        return (HANDLER_NAME,)

    def getSupportedMethodNames(self):
        return METHODS

    def callHandlerMethod(self, window, event, method):
        if method not in METHODS:
            return False
        try:
            if event in ("initialize", "back"):
                self._load(window)
            elif event == "ok":
                self._save(window)
        except Exception:  # noqa: BLE001 - never raise into the options dialog
            diag_log.exception("number_words_options")
        return True

    def _load(self, window):
        from . import number_words_prefs as prefs
        values = prefs.load(self.ctx)
        for prefix, key in COLUMNS.items():
            indexes = option_indexes(values[key])
            for choice in CHOICES:
                control = window.getControl("%s_%s" % (prefix, choice))
                control.getModel().StringItemList = T.OPTIONS_PAGE[choice]
                control.selectItemPos(indexes[choice], True)
        window.getControl("m_unit").setText(values["unit"])
        window.getControl("m_sub").setText(values["sub_unit"])

    def _save(self, window):
        from . import number_words_prefs as prefs
        selected = {prefix: {choice: window.getControl("%s_%s" % (prefix, choice)).getSelectedItemPos()
                             for choice in CHOICES} for prefix in COLUMNS}
        prefs.save(self.ctx, page_layer(selected, window.getControl("m_unit").getText(),
                                        window.getControl("m_sub").getText()))
