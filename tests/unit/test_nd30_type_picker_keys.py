# SPDX-License-Identifier: AGPL-3.0-only
"""Quick Search of the ND30 wizard's "Loại văn bản": Tab after a typed query takes the highlighted type and closes the list.

The list covers the next seven fields. When Tab left it open, the focus moved to a control under it: what the user typed
next went nowhere, a click on a covered field chose a list row, and the next key closed the list and silently restored the
old type ("moving between fields freezes"). Tab must also stay with the dialog, which moves the focus. Without an office."""
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

from hst_office import nd30, wizard_type_picker  # noqa: E402
from hst_office.data_files import load_locale  # noqa: E402

# Key codes as the picker module itself bound them: another test module may have imported it first with other stubs.
_keys = types.SimpleNamespace(TAB=wizard_type_picker.TAB, RETURN=wizard_type_picker.RETURN)


class _Peer:
    def hasFocus(self):  # noqa: N802 - UNO method name
        return True


class _List:
    def __init__(self):
        self.visible, self.top = False, []

    def setVisible(self, value):  # noqa: N802 - UNO method name
        self.visible = value

    def makeVisible(self, index):  # noqa: N802 - UNO method name
        self.top.append(index)

    def getPeer(self):  # noqa: N802 - UNO method name
        return _Peer()


class _Popup:
    """The list's popup window (wizard_type_popup.TypePopup): its list model and whether it is shown."""

    def __init__(self):
        self.model, self.visible = types.SimpleNamespace(StringItemList=(), SelectedItems=()), False
        self.tops = []  # scroll positions top_row() reports next; 0 when empty

    def top_row(self):
        return self.tops.pop(0) if self.tops else 0

    def show(self, visible):
        self.visible = visible


class _Dialog:
    def __init__(self):
        self.models = {"type": types.SimpleNamespace(Text="", PositionY=20, Height=12)}
        self.model = types.SimpleNamespace(getByName=self.models.__getitem__)

    def set_text(self, name, text):
        self.models[name].Text = text


class TabLeavesTheList(unittest.TestCase):
    def setUp(self):
        # the picker imports `uno` inside its methods: give whichever module is installed the two helpers it uses
        uno = sys.modules["uno"]
        helpers = {"invoke": lambda obj, method, args: setattr(obj, args[0], getattr(args[1], "value", args[1])),
                   "Any": lambda kind, value: types.SimpleNamespace(value=value)}
        for name, value in helpers.items():
            if name in vars(uno):
                self.addCleanup(setattr, uno, name, vars(uno)[name])
            else:
                self.addCleanup(delattr, uno, name)
            setattr(uno, name, value)
        self.chosen = []
        self.picker = wizard_type_picker.TypePicker(_Dialog(), nd30.rules()["documentTypes"], load_locale("vi")["nd30"]["groups"],
                                                    lambda: self.chosen.append(self.picker.current))
        self.picker.field, self.picker.list, self.picker.handler = _Peer(), _List(), object()
        self.picker.popup = _Popup()
        self.picker.field.getPeer = lambda: _Peer()

    def type_query(self, text):
        self.picker.d.models["type"].Text = text
        self.picker.typed()

    def test_tab_takes_the_highlighted_type_and_closes_the_list(self):
        self.type_query("quyet")
        self.assertTrue(self.picker.open)
        self.assertTrue(self.picker.popup.visible)
        handled = self.picker.key(_keys.TAB)
        self.assertFalse(handled, "Tab must stay with the dialog so the focus moves on")
        self.assertEqual(self.picker.current, "quyet-dinh")
        self.assertFalse(self.picker.open)
        self.assertFalse(self.picker.popup.visible)
        self.assertEqual(self.picker.d.models["type"].Text, self.picker.label_of("quyet-dinh"))
        self.assertEqual(self.chosen, ["quyet-dinh"])

    def test_tab_with_nothing_found_closes_and_keeps_the_type(self):
        self.type_query("zzzz")
        self.assertTrue(self.picker.open)
        self.assertFalse(self.picker.key(_keys.TAB))
        self.assertEqual(self.picker.current, "cong-van")
        self.assertFalse(self.picker.open)
        self.assertEqual(self.picker.d.models["type"].Text, self.picker.label_of("cong-van"))

    def test_tab_with_the_list_closed_is_left_alone(self):
        self.assertFalse(self.picker.key(_keys.TAB))
        self.assertEqual(self.chosen, [])

    def test_pointer_moves_the_highlight_and_enter_takes_it(self):
        """A plain VCL list box never follows the pointer (only a dropdown's list does): the picker moves it itself."""
        self.type_query("")
        heading = next(i for i, row in enumerate(self.picker.table) if not row[1])
        row = next(i for i, r in enumerate(self.picker.table) if r[1] and i != self.picker.index)
        self.picker.hovered(row)
        self.assertEqual(self.picker.index, row)
        self.assertEqual(self.picker.popup.model.SelectedItems, (row,))
        self.picker.hovered(heading)
        self.picker.hovered(-1)
        self.assertEqual(self.picker.index, row, "a heading or the border keeps the highlight")
        self.assertEqual(self.chosen, [], "hovering never chooses")
        self.assertTrue(self.picker.key(_keys.RETURN))
        self.assertEqual(self.picker.current, self.picker.table[row][1])

    def test_pointer_keeps_the_scroll_position(self):
        """VCL scrolls a selected row of the lower half to the middle; under the pointer the list then ran away."""
        self.type_query("")
        row = next(i for i, r in enumerate(self.picker.table) if r[1] and i > 8)
        self.picker.list.top = []
        self.picker.popup.tops = [0, 5]  # before the selection, after it
        self.picker.hovered(row)
        self.assertEqual(self.picker.list.top, [0])
        self.picker.popup.tops = [0, 0]
        self.picker.hovered(row + 1 if self.picker.table[row + 1][1] else row + 2)
        self.assertEqual(self.picker.list.top, [0], "no scroll when VCL kept the position")

    def test_pointer_over_a_closed_list_does_nothing(self):
        self.picker.hovered(3)
        self.assertEqual(self.picker.index, -1)

    def test_enter_still_chooses_and_is_kept_from_the_dialog(self):
        self.type_query("thong tri")
        self.assertTrue(self.picker.key(_keys.RETURN))
        self.assertEqual(self.picker.current, "dang-thong-tri")


if __name__ == "__main__":
    unittest.main()
