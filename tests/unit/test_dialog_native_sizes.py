# SPDX-License-Identifier: LicenseRef-HST-Proprietary
# Copyright (C) 2026 HASON TECH
"""Radio/check rows and spin fields grow to the size the platform draws them, and only then (dialog_native_sizes).

The Finish & Merge dialog (mail merge) is laid out in Map AppFont units: radio rows 10 units high, 12 apart. A GTK3
theme draws the radio indicator in fixed pixels, so with a 7 pt UI font (12 units = 20 px), GDK_SCALE=2 with
GDK_DPI_SCALE=0.5 (12 units = 14 px logical) or a theme with a 24 px indicator (preferred height 38 px) the rows
overlapped; GTK3's two side-by-side spin buttons (preferred width 115 px) covered the digits of a 40-unit number field.
Without an office: a fake peer answers the preferred sizes and the AppFont/pixel conversion; the layout is the dialog's
own. The pixel figures of the GTK3 cases were measured on Xvfb with the 1.0.3 package; the Windows and macOS ones are
the usual native control sizes (radio/check 13-18 px, a narrow vertical spin button)."""
import sys
import types
import unittest

import _paths  # noqa: F401


class _StubModule(types.ModuleType):
    def __getattr__(self, name):
        if name.startswith("__"):
            raise AttributeError(name)
        value = type(name, (), {})
        setattr(self, name, value)
        return value


for _name in ("uno", "unohelper", "com", "com.sun", "com.sun.star", "com.sun.star.awt", "com.sun.star.awt.Key",
              "com.sun.star.lang", "com.sun.star.util", "com.sun.star.util.MeasureUnit"):
    sys.modules.setdefault(_name, _StubModule(_name))


class Size:
    def __init__(self, Width=0, Height=0):  # noqa: N803 - UNO struct member names
        self.Width, self.Height = Width, Height


sys.modules["com.sun.star.awt"].Size = Size
sys.modules["com.sun.star.util.MeasureUnit"].APPFONT = 17

from hst_office import dialog_native_sizes, dialogs, mail_merge_finish_dialog, mail_merge_table, mail_merge_texts  # noqa: E402


class _Peer:
    """AppFont <-> pixels like VCL, per axis: pixels = units * px, rounded; logic = pixels / px, rounded down."""

    def __init__(self, px_x, px_y):
        self.px_x, self.px_y = px_x, px_y

    def convertSizeToLogic(self, size, unit):  # noqa: N802 - UNO method name
        return Size(int(size.Width / self.px_x), int(size.Height / self.px_y))

    def convertSizeToPixel(self, size, unit):  # noqa: N802 - UNO method name
        return Size(int(round(size.Width * self.px_x)), int(round(size.Height * self.px_y)))


class _Control:
    def __init__(self, size):
        self.size = size

    def getPreferredSize(self):  # noqa: N802 - UNO method name
        return Size(*self.size)


class _UnoDialog:
    def __init__(self, owner):
        self.owner = owner

    def getPeer(self):  # noqa: N802 - UNO method name
        return _Peer(self.owner.px_x, self.owner.px_y)

    def getControl(self, name):  # noqa: N802 - UNO method name
        kind = self.owner.kinds[name]
        if kind in ("RadioButton", "CheckBox"):
            return _Control((60, self.owner.choice_px))
        if kind == "NumericField":
            return _Control((self.owner.spin_px, 20))
        return _Control((10, 10))


class _Model:
    def __init__(self, owner, width, height):
        self.owner, self.Width, self.Height = owner, width, height

    def getByName(self, name):  # noqa: N802 - UNO method name
        return self.owner.controls[name]

    @property
    def ElementNames(self):  # noqa: N802 - UNO attribute name
        return tuple(self.owner.order)


class FakeDialog(dialogs.Dialog):
    """The real Dialog builders (label, edit, check, button) on recorded control models."""

    px_x = px_y = 2.0
    choice_px, spin_px = 18, 50

    def __init__(self, ctx, title, width, height):
        self.order, self.controls, self.kinds = [], {}, {}
        self.ctx, self.model, self.dialog = ctx, _Model(self, width, height), _UnoDialog(self)
        self._listeners, self._watchers, self._single_lines = [], [], []
        self.on_oversize = self.on_ready = self.on_closed = self.on_moved = None

    def _add(self, kind, name, x, y, w, h, **props):
        control = types.SimpleNamespace(PositionX=x, PositionY=y, Width=w, Height=h, **props)
        control.supportsService = lambda service, kind=kind: service == "com.sun.star.awt.UnoControl%sModel" % kind
        self.order.append(name)
        self.controls[name], self.kinds[name] = control, kind
        return control

    def listbox(self, name, x, y, w, items, selected=0, h=12, help_text="", dropdown=True):
        return self._add("ListBox", name, x, y, w, h, SelectedItems=(selected,))


def _finish_dialog(px_x, px_y, choice_px, spin_px):
    FakeDialog.px_x, FakeDialog.px_y, FakeDialog.choice_px, FakeDialog.spin_px = px_x, px_y, choice_px, spin_px
    mail_merge_finish_dialog.Dialog = FakeDialog
    table = mail_merge_table.Table(["Họ và tên", "Năm sinh"], ["text", "text"], [["A", "1990"], ["B", "1991"]])
    session = types.SimpleNamespace(table=table, checked=lambda: [0, 1], meta={"pattern": "", "folder": "/tmp/out"})
    return mail_merge_finish_dialog.FinishDialog(None, mail_merge_texts.EN, session).d


def _layout(d):
    return ({name: (c.PositionX, c.PositionY, c.Width, c.Height) for name, c in d.controls.items()},
            d.model.Width, d.model.Height)


def _overlaps(d):
    found = set()
    names = d.order
    for i, a in enumerate(names):
        for b in names[i + 1:]:
            p, q = d.controls[a], d.controls[b]
            if (p.PositionX < q.PositionX + q.Width and q.PositionX < p.PositionX + p.Width
                    and p.PositionY < q.PositionY + q.Height and q.PositionY < p.PositionY + p.Height):
                found.add((a, b))
    return found


# (px per unit across, px per unit down, radio/check preferred height, spin field preferred width)
FITTING = {"gtk3 Adwaita 10 pt": (2.2, 2.25, 22, 115), "Windows Segoe UI 9 pt": (1.75, 2.0, 17, 50),
           "macOS 13 pt": (2.0, 1.875, 18, 60), "gen backend": (1.75, 1.5, 13, 60)}
RADIO_TOO_HIGH = {"gtk3 7 pt": (1.6, 20 / 12, 22), "gtk3 GDK_SCALE=2 GDK_DPI_SCALE=0.5": (1.1, 14 / 12, 22),
                  "gtk3 24 px indicator": (2.2, 2.25, 38)}


class FitChoiceRows(unittest.TestCase):
    def test_rows_that_fit_do_not_change(self):
        for case, (px_x, px_y, choice_px, spin_px) in FITTING.items():
            d = _finish_dialog(px_x, px_y, choice_px, spin_px)
            before = _layout(d)
            dialog_native_sizes.fit_choice_rows(d)
            self.assertEqual(_layout(d), before, case)

    def test_windows_macos_and_gen_layouts_do_not_change_at_all(self):
        for case, (px_x, px_y, choice_px, spin_px) in FITTING.items():
            if not case.startswith("gtk3"):  # GTK3 widens its spin fields (FitSpinWidths)
                d = _finish_dialog(px_x, px_y, choice_px, spin_px)
                before = _layout(d)
                dialog_native_sizes.fit_all(d)
                self.assertEqual(_layout(d), before, case)

    def test_the_designed_layout_overlaps_nothing(self):
        self.assertEqual(_overlaps(_finish_dialog(2.0, 2.0, 18, 50)), set())

    def test_high_radios_grow_and_push_the_rows_below(self):
        for case, (px_x, px_y, choice_px) in RADIO_TOO_HIGH.items():
            d = _finish_dialog(px_x, px_y, choice_px, 10)
            (before, _, height), peer = _layout(d), _Peer(px_x, px_y)
            dialog_native_sizes.fit_choice_rows(d)
            for name, kind in d.kinds.items():
                if kind in ("RadioButton", "CheckBox"):
                    drawn = peer.convertSizeToPixel(Size(0, d.controls[name].Height), 17).Height
                    self.assertGreaterEqual(drawn, choice_px, (case, name))
            self.assertEqual(_overlaps(d), set(), case)
            order = sorted(d.order, key=lambda n: (before[n][1], before[n][0]))
            self.assertEqual(order, sorted(d.order, key=lambda n: (d.controls[n].PositionY, d.controls[n].PositionX)),
                             case)  # rows keep their order
            grown = d.controls["cancel"].PositionY - before["cancel"][1]
            self.assertGreater(grown, 0, case)
            self.assertEqual(d.model.Height, height + grown, case)  # the bottom margin stays

    def test_a_row_moves_as_a_whole(self):
        d = _finish_dialog(1.6, 20 / 12, 22, 10)
        dialog_native_sizes.fit_choice_rows(d)
        radio, start, label, end = (d.controls[n] for n in ("w_range", "from", "toLabel", "to"))
        self.assertEqual((start.PositionY - radio.PositionY, label.PositionY - radio.PositionY,
                          end.PositionY - radio.PositionY), (-1, 1, -1))  # as designed: 118, 117, 119, 117

    def test_free_room_below_is_used_before_moving_anything(self):
        d = _finish_dialog(2.0, 2.0, 22, 10)  # 11 units: within the 12-unit row pitch
        before, width, height = _layout(d)
        dialog_native_sizes.fit_choice_rows(d)
        self.assertEqual(d.controls["a_edit"].Height, 11)
        self.assertEqual(d.model.Height, height)
        for name, place in before.items():
            self.assertEqual(d.controls[name].PositionY, place[1], name)

    def test_check_boxes_side_by_side_push_their_rows_once(self):
        FakeDialog.px_x, FakeDialog.px_y, FakeDialog.choice_px = 2.0, 1.5, 24  # 16 units
        d = FakeDialog(None, "t", 200, 60)
        d.check("left", "A", 8, 8, 90)
        d.check("right", "B", 102, 8, 90)
        d.button("ok", "OK", 136, 20, 56)
        dialog_native_sizes.fit_choice_rows(d)
        self.assertEqual((d.controls["left"].Height, d.controls["right"].Height), (16, 16))
        self.assertEqual(d.controls["ok"].PositionY, 24)  # 12 units of room under "right", 16 needed
        self.assertEqual(d.model.Height, 64)

    def test_fitting_twice_changes_nothing_more(self):
        d = _finish_dialog(1.1, 14 / 12, 22, 115)
        dialog_native_sizes.fit_all(d)
        once = _layout(d)
        dialog_native_sizes.fit_all(d)
        self.assertEqual(_layout(d), once)

    def test_no_peer_keeps_the_layout(self):
        d = _finish_dialog(1.6, 20 / 12, 22, 115)
        before = _layout(d)
        d.dialog.getPeer = lambda: (_ for _ in ()).throw(RuntimeError("disposed"))
        dialog_native_sizes.fit_all(d)
        self.assertEqual(_layout(d), before)


class FitSpinWidths(unittest.TestCase):
    def test_gtk3_spin_fields_show_digits_and_both_buttons(self):
        d = _finish_dialog(2.2, 2.25, 22, 115)  # 115 px: 53 units
        dialog_native_sizes.fit_spin_widths(d)
        start, label, end = (d.controls[n] for n in ("from", "toLabel", "to"))
        self.assertEqual((start.PositionX, start.Width), (86, 53))
        self.assertEqual(label.PositionX, 130 + 13)  # "to" keeps its gap to the first field
        self.assertEqual((end.PositionX, end.Width), (150 + 13, 53))
        self.assertEqual(_overlaps(d), set())

    def test_the_row_stays_inside_the_right_margin(self):
        d = _finish_dialog(1.0, 1.0, 10, 400)
        dialog_native_sizes.fit_spin_widths(d)
        end = d.controls["to"]
        self.assertEqual(end.PositionX + end.Width, 300 - 8)
        self.assertEqual(_overlaps(d), set())


if __name__ == "__main__":
    unittest.main()
