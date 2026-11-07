# SPDX-License-Identifier: AGPL-3.0-only
"""ND30 wizard dialog model, without an office: no list control lies over the fields. The "Loại văn bản" list used to
be a list box of the dialog shown over the fields below the type. VCL does not clip sibling controls against each
other: inserted after the fields it lay under them (hover, wheel and clicks went to the fields on macOS and Linux), and
inserted before them the fields still repainted through it on Windows, where themed edits redraw on hover. The list is
now a popup outside the dialog model (wizard_type_popup). Also: the "In hai mặt" box is offered for every type."""
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
              "com.sun.star.lang"):
    sys.modules.setdefault(_name, _StubModule(_name))

from hst_office import wizard_nd30  # noqa: E402
from hst_office.data_files import load_locale  # noqa: E402


class _Control(types.SimpleNamespace):
    pass


class _Model:
    def __init__(self, dialog):
        self.dialog = dialog

    def getByName(self, name):
        return self.dialog.controls[name]

    @property
    def ElementNames(self):
        return tuple(self.dialog.order)


class FakeDialog:
    """Records controls in insertion order with their rectangles (Map AppFont units), like the UNO dialog model."""

    def __init__(self, ctx, title, width, height):
        self.order, self.controls = [], {}
        self.model = _Model(self)
        self.on_oversize = self.on_ready = self.on_closed = None

    def _add(self, kind, name, x, y, w, h, **props):
        control = _Control(kind=kind, PositionX=x, PositionY=y, Width=w, Height=h, Text="", State=0, Label="",
                           Enabled=True, EnableVisible=True, HelpText="", TextColor=0, **props)
        self.order.append(name)
        self.controls[name] = control
        return control

    def label(self, name, text, x, y, w, h=10, wrap=False):
        return self._add("label", name, x, y, w, h, Label_text=text)

    def edit(self, name, x, y, w, h=12, text="", multiline=False, readonly=False, help_text=""):
        control = self._add("edit", name, x, y, w, h, FontDescriptor=types.SimpleNamespace(Name="", Height=0))
        control.Text = text
        return control

    def plain_list(self, name, x, y, w, h, help_text=""):
        return self._add("list", name, x, y, w, h)

    def check(self, name, text, x, y, w, state=True, h=10):
        control = self._add("check", name, x, y, w, h)
        control.State, control.Label = 1 if state else 0, text
        return control

    def button(self, name, text, x, y, w, kind=None, callback=None, default=False, h=14):
        return self._add("button", name, x, y, w, h)

    def on_change(self, names, callback):
        pass

    def get(self, name):
        control = self.controls[name]
        return bool(control.State) if control.kind == "check" else control.Text

    def set_text(self, name, text):
        self.controls[name].Text = text


def _intersects(a, b):
    return (a.PositionX < b.PositionX + b.Width and b.PositionX < a.PositionX + a.Width
            and a.PositionY < b.PositionY + b.Height and b.PositionY < a.PositionY + a.Height)


class ModelOrder(unittest.TestCase):
    def setUp(self):
        wizard_nd30.Dialog, wizard_nd30.palette = FakeDialog, lambda ctx: {"muted": 0, "error": 0, "link": 0}
        self.wizard = wizard_nd30.Nd30Wizard(None, load_locale("vi"))
        self.names = list(self.wizard.d.model.ElementNames)

    def test_no_control_overlaps_another(self):
        model = self.wizard.d.model
        kinds = [n for n in self.names if model.getByName(n).kind == "list"]
        self.assertEqual(kinds, [])
        visible = [n for n in self.names if n not in ("l_preview", "preview", "status")]
        for i, name in enumerate(visible):
            for other in visible[i + 1:]:
                self.assertFalse(_intersects(model.getByName(name), model.getByName(other)), (name, other))

    def test_type_list_is_a_popup_under_the_type_field(self):
        popup = self.wizard.picker.popup
        self.assertEqual(type(popup).__name__, "TypePopup")
        self.assertIsNone(popup.box())  # created when the dialog's peer exists (TypePicker.attach)

    def test_duplex_box_is_offered_off_and_reported(self):
        duplex = self.wizard.d.model.getByName("duplex")
        self.assertEqual((duplex.Label, duplex.State), ("In hai mặt", 0))
        self.assertIs(self.wizard.outcome()["duplex"], False)
        page_numbers = self.wizard.d.model.getByName("pageNumbers")
        self.assertFalse(_intersects(duplex, page_numbers))
        self.assertLessEqual(duplex.PositionX + duplex.Width, wizard_nd30.PREVIEW_X)


if __name__ == "__main__":
    unittest.main()
