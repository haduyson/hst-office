# SPDX-License-Identifier: AGPL-3.0-only
"""The scrolling form of a dialog taller than the work area (wizard_scroll_band), and the ND30 wizard's compact
layout at 1366x768 with 125 % scaling: buttons and check boxes stay in view, every field is reachable by scrolling
and by Tab / Shift+Tab. Uses the fake dialog of test_nd30_wizard_model_order."""
import unittest
from unittest import mock

import _paths  # noqa: F401
from test_nd30_wizard_model_order import FakeDialog
from hst_office import wizard_nd30, wizard_scroll_band as band_module
from hst_office.data_files import load_locale


class _Control:
    def __init__(self):
        self.focus, self.adjust = [], []

    def addFocusListener(self, listener):
        self.focus.append(listener)

    def addAdjustmentListener(self, listener):
        self.adjust.append(listener)


class _Peer:
    def __init__(self, controls):
        self.controls = controls

    def getControl(self, name):
        return self.controls.setdefault(name, _Control())


class Dialog(FakeDialog):
    """The wizard test's fake with live controls (the peer exists when the band is attached)."""

    def __init__(self, ctx, title, width, height):
        super().__init__(ctx, title, width, height)
        self.model.Width, self.model.Height, self.live = width, height, {}
        self.dialog = _Peer(self.live)

    def _add(self, kind, name, x, y, w, h, **props):
        control = super()._add(kind, name, x, y, w, h)
        for key, value in props.items():
            setattr(control, key, value)
        return control


def small_dialog():
    d = Dialog(None, "t", 100, 200)
    for i in range(10):  # a form of ten 12-unit rows from y=10, then a fixed block
        d.edit("f%d" % i, 10, 10 + 16 * i, 80)
    d.check("fixed", "x", 10, 170, 80)
    d.button("ok", "OK", 10, 184, 40)
    return d


class Band(unittest.TestCase):
    def test_a_dialog_that_fits_is_left_alone(self):
        d = small_dialog()
        self.assertIsNone(band_module.fit(d, ["f%d" % i for i in range(10)], 8, 168, ("fixed", "ok"), 200, 92))
        self.assertIsNone(band_module.fit(d, ["f0"], 8, 168, ("fixed", "ok"), None, 92))
        self.assertEqual(d.model.Height, 200)

    def test_cut_to_the_limit_keeps_the_fixed_controls_in_view(self):
        d = small_dialog()
        band = band_module.fit(d, ["f%d" % i for i in range(10)], 8, 168, ("fixed", "ok"), 120, 92)
        self.assertEqual(d.model.Height, 120)
        self.assertEqual((d.model.getByName("fixed").PositionY, d.model.getByName("ok").PositionY), (90, 104))
        self.assertLessEqual(d.model.getByName("ok").PositionY + 14, d.model.Height)
        visible = [n for n in band.names if d.model.getByName(n).EnableVisible]
        self.assertEqual(visible, ["f0", "f1", "f2", "f3", "f4"])  # wholly inside [8, 88): f4 ends at 86
        bar = d.model.getByName(band_module.BAR)
        self.assertEqual((bar.PositionY, bar.Height, bar.ScrollValueMax, bar.Tabstop), (8, 80, band.span, False))

    def test_scrolling_reaches_the_last_field_and_moves_the_bar(self):
        d = small_dialog()
        band = band_module.fit(d, ["f%d" % i for i in range(10)], 8, 168, ("fixed", "ok"), 120, 92)
        band.scroll_to(10_000)
        self.assertTrue(d.model.getByName("f9").EnableVisible)
        self.assertFalse(d.model.getByName("f0").EnableVisible)
        self.assertEqual(d.model.getByName(band_module.BAR).ScrollValue, band.span)
        d.live[band_module.BAR].adjust[0].adjustmentValueChanged(type("E", (), {"Value": 0})())
        self.assertTrue(d.model.getByName("f0").EnableVisible)

    def test_focus_scrolls_the_field_into_view_and_the_edges_wrap(self):
        d = small_dialog()
        band = band_module.fit(d, ["f%d" % i for i in range(10)], 8, 168, ("fixed", "ok"), 120, 92)
        d.live["f6"].focus[0].focusGained(None)
        self.assertTrue(d.model.getByName("f6").EnableVisible)
        self.assertTrue(d.model.getByName("f7").EnableVisible)  # the next Tab stop is in view as well
        d.live["fixed"].focus[0].focusGained(None)  # Shift+Tab will go back into the band at its end
        self.assertEqual(band.offset, band.span)
        d.live["ok"].focus[0].focusGained(None)  # Tab will wrap round to the first field
        self.assertEqual(band.offset, 0)


class WizardOnASmallScreen(unittest.TestCase):
    def wizard(self, limit):
        wizard_nd30.Dialog, wizard_nd30.palette = Dialog, lambda ctx: {"muted": 0, "error": 0, "link": 0}
        w = wizard_nd30.Nd30Wizard(None, load_locale("vi"))
        with mock.patch.object(band_module, "max_height", return_value=limit):
            w._compact()
        return w

    def test_1366x768_at_125_percent_scrolls_the_form(self):
        w = self.wizard(229)  # measured: 658 px of a 708 px work area hold 229 units at 125 % (Linux, Xvfb)
        m = w.d.model
        self.assertIsNotNone(w.band)
        self.assertEqual(m.Height, 229)
        for name in ("applyPage", "pageNumbers", "duplex", "btnOk", "btnCancel"):
            item = m.getByName(name)
            self.assertLessEqual(item.PositionY + item.Height, m.Height, name)
        self.assertNotIn("btnOk", w.band.names)
        self.assertIn("agencyRule", w.band.names)
        w.band.reveal("agencyRule")
        self.assertTrue(m.getByName("agencyRule").EnableVisible)
        self.assertLessEqual(m.getByName(band_module.BAR).PositionX + band_module.BAR_WIDTH, m.Width)

    def test_a_screen_that_holds_the_compact_layout_gets_no_scroll_bar(self):
        w = self.wizard(400)
        self.assertIsNone(w.band)
        self.assertNotIn(band_module.BAR, w.d.model.ElementNames)


if __name__ == "__main__":
    unittest.main()
