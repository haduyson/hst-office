# SPDX-License-Identifier: AGPL-3.0-only
"""One-line edits grow to the height the platform draws them, within the room below them (dialog_edit_heights).

On macOS a native edit box is 29 px high (21 px frame and a 4 px focus ring above and below, text area from 6 px below
the top: vcl/inc/osx/salnativewidgets.h). The ND30 wizard gave its one-line edits 12 Map AppFont units, about 22 px
there: the text sat on the top border and the descenders of g/y were cut. Without an office: a fake peer answers the
preferred height and the AppFont/pixel conversion; the layout is the wizard's own."""
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

from hst_office import dialog_edit_heights, dialogs, wizard_nd30  # noqa: E402
from hst_office.data_files import load_locale  # noqa: E402


class _Peer:
    """AppFont <-> pixels like VCL: pixels = units * px_per_unit, rounded; logic = pixels / px_per_unit, rounded down."""

    def __init__(self, px_per_unit):
        self.px = px_per_unit

    def convertSizeToLogic(self, size, unit):  # noqa: N802 - UNO method name
        return Size(0, int(size.Height / self.px))

    def convertSizeToPixel(self, size, unit):  # noqa: N802 - UNO method name
        return Size(0, int(round(size.Height * self.px)))


class _Control:
    def __init__(self, preferred):
        self.preferred = preferred

    def getPreferredSize(self):  # noqa: N802 - UNO method name
        return Size(0, self.preferred)


class _UnoDialog:
    def __init__(self, px_per_unit, preferred):
        self.peer, self.control = _Peer(px_per_unit), _Control(preferred)

    def getPeer(self):  # noqa: N802 - UNO method name
        return self.peer

    def getControl(self, name):  # noqa: N802 - UNO method name
        return self.control


class _Model:
    def __init__(self, dialog):
        self.d = dialog

    def getByName(self, name):  # noqa: N802 - UNO method name
        return self.d.controls[name]

    @property
    def ElementNames(self):  # noqa: N802 - UNO attribute name
        return tuple(self.d.order)

    @property
    def Height(self):  # noqa: N802 - UNO attribute name
        return wizard_nd30.HEIGHT


class FakeDialog(dialogs.Dialog):
    """The real Dialog bookkeeping (_single_lines) for dialog_edit_heights on a recorded model."""

    px_per_unit, preferred = 1.875, 29  # macOS: 13 pt system font, native edit 29 px

    def __init__(self, ctx, title, width, height):
        self.order, self.controls = [], {}
        self.model = _Model(self)
        self.dialog = _UnoDialog(self.px_per_unit, self.preferred)
        self._listeners, self._watchers = [], []
        self._single_lines = []
        self.on_oversize = self.on_ready = self.on_closed = None

    def _add(self, kind, name, x, y, w, h, **props):
        control = types.SimpleNamespace(PositionX=x, PositionY=y, Width=w, Height=h, Text="", Label="", State=0, Enabled=True,
                                        EnableVisible=True, TextColor=0, FontWeight=0, MultiLine=False, HelpText="",
                                        FontDescriptor=types.SimpleNamespace(Name="", Height=0))
        self.order.append(name)
        self.controls[name] = control
        return control

    def listbox(self, name, x, y, w, items, selected=0, h=12, help_text="", dropdown=True):
        control = self._add("ListBox", name, x, y, w, h)
        control.SelectedItems = (selected,)
        return control

    def get(self, name):
        control = self.controls[name]
        return control.SelectedItems[0] if hasattr(control, "SelectedItems") else control.Text

    def select(self, name, index):
        pass


def _wizard(px_per_unit, preferred):
    FakeDialog.px_per_unit, FakeDialog.preferred = px_per_unit, preferred
    wizard_nd30.Dialog, wizard_nd30.palette = FakeDialog, lambda ctx: {"muted": 0, "error": 0, "link": 0}
    wizard = wizard_nd30.Nd30Wizard(None, load_locale("vi"))
    before = {name: wizard.d.model.getByName(name).Height for name in wizard.d._single_lines}
    dialog_edit_heights.fit_edits(wizard.d)
    return wizard, before


def _overlap(a, b):
    return (a.PositionX < b.PositionX + b.Width and b.PositionX < a.PositionX + a.Width
            and a.PositionY < b.PositionY + b.Height and b.PositionY < a.PositionY + a.Height)


class FitEdits(unittest.TestCase):
    def test_macos_edits_reach_the_native_height(self):
        wizard, before = _wizard(1.875, 29)
        model = wizard.d.model
        self.assertIn("contact", wizard.d._single_lines)
        self.assertNotIn("summary", wizard.d._single_lines)  # several lines: text at the top is right there
        self.assertNotIn("preview", wizard.d._single_lines)
        for name in wizard.d._single_lines:
            self.assertEqual(before[name], 12, name)
            pixels = round(model.getByName(name).Height * 1.875)
            self.assertGreaterEqual(pixels, 29, name)

    def test_grown_edits_overlap_nothing(self):
        wizard, _ = _wizard(1.875, 29)
        model, d = wizard.d.model, wizard.d
        names = list(model.ElementNames)
        for name in d._single_lines:
            for other in names:
                if other != name:
                    self.assertFalse(_overlap(model.getByName(name), model.getByName(other)), (name, other))

    def test_room_is_capped_by_the_control_below(self):
        wizard, _ = _wizard(1.0, 200)  # absurd preferred height: every edit stops at the next control
        model = wizard.d.model
        self.assertEqual(model.getByName("parentAgency").Height, 16)  # next row 16 units lower
        self.assertEqual(model.getByName("signerAuthority").Height, 22)  # its label takes two lines
        self.assertEqual(model.getByName("contact").Height, 16)  # the check boxes are 16 units lower

    def test_the_type_list_does_not_limit_the_type_field(self):
        wizard, _ = _wizard(1.875, 29)
        self.assertEqual(wizard.d.model.getByName("type").Height, 16)

    def test_edits_high_enough_keep_their_layout(self):
        for px_per_unit, preferred in ((2.0, 22), (2.25, 27), (1.67, 20)):  # Windows Segoe UI 9 pt; within 12 units
            wizard, before = _wizard(px_per_unit, preferred)
            for name in wizard.d._single_lines:
                self.assertEqual(wizard.d.model.getByName(name).Height, before[name], (px_per_unit, name))


class TypeArrow(unittest.TestCase):
    def test_the_arrow_is_not_a_tab_stop(self):
        """Tab from "Loại văn bản" goes to the next field, not to the arrow that swallowed what the user typed next."""
        wizard, _ = _wizard(2.0, 22)
        self.assertIs(wizard.d.model.getByName("typeOpen").Tabstop, False)


if __name__ == "__main__":
    unittest.main()
