# SPDX-License-Identifier: AGPL-3.0-only
"""A scrolling band of controls in a dialogs.Dialog, for dialogs taller than the screen's work area (the ND30 wizard at
1366x768 with 125 % scaling: about 708 px of work area for a 920 px dialog).

VCL scrolls only a whole dialog or a tab page (toolkit/source/awt/vclxcontainer.cxx), which would take the OK/Cancel
buttons out of view too. Here the controls between two lines of the dialog move together under a vertical scroll
bar; what lies below the band (check boxes, buttons) moves up and stays in place, and the dialog is cut to the work
area. A control is shown only while it lies wholly inside the band (VCL does not clip sibling controls), and a control
that gets the keyboard focus is scrolled into the middle of the band, so Tab and Shift+Tab reach every field.
All positions are Map AppFont units.
"""
import unohelper
from com.sun.star.awt import XAdjustmentListener, XFocusListener

from . import screen_work_area

BAR = "bandScroll"
BAR_WIDTH = 8


class _Adjust(unohelper.Base, XAdjustmentListener):
    def __init__(self, band):
        self.band = band

    def adjustmentValueChanged(self, event):
        self.band.scroll_to(event.Value, from_bar=True)

    def disposing(self, event):
        pass


class _Focus(unohelper.Base, XFocusListener):
    """A band control scrolls itself into view; the edges of the fixed controls below scroll the band to its end
    (Shift+Tab goes back into the band at its last field) or to its start (Tab wraps round to the first field)."""

    def __init__(self, band, name, to=None):
        self.band, self.name, self.to = band, name, to

    def focusGained(self, event):
        if self.to is None:
            self.band.reveal(self.name)
        else:
            self.band.scroll_to(self.band.span if self.to == "end" else 0)

    def focusLost(self, event):
        pass

    def disposing(self, event):
        pass


def max_height(dialog):
    """The dialog height (AppFont) the screen's work area holds, frame and title bar included, or None."""
    try:
        toolkit = dialog.smgr.createInstanceWithContext("com.sun.star.awt.Toolkit", dialog.ctx)
        size = dialog.dialog.getPeer().getPosSize()
        per_unit = size.Height / float(dialog.model.Height)
        height = screen_work_area.work_area(toolkit)[1]
        return int((height - screen_work_area.DECORATION_PX) / per_unit) if per_unit > 0 else None
    except Exception:  # noqa: BLE001 - no peer or no work area: leave the layout as it is
        return None


class ScrollBand:
    def __init__(self, dialog, names, top, height):
        self.d, self.names, self.top, self.height, self.offset = dialog, list(names), top, height, 0
        model = dialog.model
        self.base = {n: model.getByName(n).PositionY for n in self.names}
        bottom = max(self.base[n] + model.getByName(n).Height for n in self.names)
        self.span = max(0, bottom - top - height + 4)  # how far the band can move

    def attach(self, bar_x, first_below, last):
        """Add the scroll bar (the dialog's peer exists) and follow the focus of the band's controls and of the first
        and last focusable control below it."""
        self.d._add("ScrollBar", BAR, bar_x, self.top, BAR_WIDTH, self.height, Orientation=1, ScrollValueMin=0,
                    ScrollValueMax=self.span, VisibleSize=self.height, LineIncrement=12, BlockIncrement=max(12, self.height - 24),
                    ScrollValue=0, HelpText="Cuộn", Tabstop=False)  # the mouse scrolls; the keyboard follows the focus
        control = self.d.dialog.getControl
        control(BAR).addAdjustmentListener(_Adjust(self))
        for name in self.names:
            control(name).addFocusListener(_Focus(self, name))
        control(first_below).addFocusListener(_Focus(self, first_below, "end"))
        control(last).addFocusListener(_Focus(self, last, "start"))
        self.place()

    def place(self):
        model = self.d.model
        for name in self.names:
            item = model.getByName(name)
            item.PositionY = self.base[name] - self.offset
            item.EnableVisible = self.top <= item.PositionY and item.PositionY + item.Height <= self.top + self.height

    def scroll_to(self, offset, from_bar=False):
        offset = max(0, min(self.span, int(offset)))
        if offset == self.offset:
            return
        self.offset = offset
        self.place()
        if not from_bar:
            self.d.model.getByName(BAR).ScrollValue = offset

    def reveal(self, name):
        """Scroll so that `name` sits in the middle of the band (the rows around it come into view with it)."""
        item_height = self.d.model.getByName(name).Height
        self.scroll_to(self.base[name] - self.top - (self.height - item_height) // 2)


def fit(dialog, names, band_top, band_bottom, below, limit, bar_x):
    """Cut `dialog` to `limit` units high when it is taller: the band [band_top, band_bottom) shrinks and scrolls,
    the controls named in `below` (in tab order: first and last are focusable) move up by as much. Returns the
    ScrollBand, or None when the dialog fits."""
    model = dialog.model
    if limit is None or model.Height <= limit:
        return None
    excess = model.Height - limit
    excess = min(excess, band_bottom - band_top - 40)  # keep at least a few rows of the form in view
    for name in below:
        model.getByName(name).PositionY -= excess
    model.Height -= excess
    band = ScrollBand(dialog, names, band_top, band_bottom - band_top - excess)
    band.attach(bar_x, below[0], below[-1])
    return band
