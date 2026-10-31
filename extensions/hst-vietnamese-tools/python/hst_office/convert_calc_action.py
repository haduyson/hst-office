# SPDX-License-Identifier: AGPL-3.0-only
"""ConvertEncoding command in Calc: selection (or active cell / whole sheet) -> wizard -> one undo step -> summary."""
from . import encoding_calc
from .wizard_convert import ConvertWizard


class Progress:
    """Status-bar progress (XStatusIndicator); silently inactive when the frame offers none."""

    def __init__(self, frame, text):
        self.text, self.indicator = text, None
        try:
            self.indicator = frame.createStatusIndicator()
        except Exception:  # noqa: BLE001 - progress is cosmetic
            pass

    def start(self, total):
        if self.indicator:
            self.indicator.start(self.text, max(total, 1))

    def update(self, value):
        if self.indicator:
            self.indicator.setValue(value)

    def end(self):
        if self.indicator:
            self.indicator.end()


def run(host):
    rects = encoding_calc.selection_rects(host.controller.getSelection())
    if rects is None:
        return host.refuse(["no-selection-cells"])
    sheet_index = host.controller.getActiveSheet().RangeAddress.Sheet
    single = len(rects) == 1 and rects[0][1:3] == rects[0][3:5]  # nothing selected beyond the active cell
    reasons = encoding_calc.check(host.doc, {r[0] for r in rects})
    if reasons:
        return host.refuse(reasons)
    targets = encoding_calc.target_rects(host.doc, rects)
    items = encoding_calc.sample(host.doc, targets)
    if not items and not single:
        return host.say(host.s["convert"]["nothing"])
    calc = {"single": single, "sample": lambda whole: encoding_calc.sample(
        host.doc, encoding_calc.target_rects(host.doc, rects, sheet_index if whole else None))}
    wizard = ConvertWizard(host.ctx, host.s, items, calc)
    key = wizard.run(host.peer)
    if key is None:
        return
    if wizard.whole:
        targets = encoding_calc.target_rects(host.doc, rects, sheet_index)
    result = encoding_calc.apply(host.doc, targets, key, wizard.names_notes,
                                 Progress(host.frame, host.s["convert"]["title"]), host.s["undo"]["convertCalc"])
    cv = host.s["convert"]
    note = cv["doneCalc"] % (result["cells"], result["formulas"])
    if result["unicode"]:
        note += "\n" + cv["unicodeCells"] % result["unicode"]
    if wizard.names_notes:
        note += "\n" + cv["doneExtra"] % (result["names"], result["notes"])
    host.say(note + "\n" + cv["calcHint"])
