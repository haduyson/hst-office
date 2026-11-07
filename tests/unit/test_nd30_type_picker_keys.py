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


for _name in ("uno", "unohelper", "com", "com.sun", "com.sun.star", "com.sun.star.awt", "com.sun.star.lang"):
    sys.modules.setdefault(_name, _StubModule(_name))
_keys = types.ModuleType("com.sun.star.awt.Key")
_keys.DOWN, _keys.UP, _keys.RETURN, _keys.ESCAPE, _keys.TAB, _keys.SPACE = 1024, 1025, 1280, 1281, 1282, 1284
sys.modules["com.sun.star.awt.Key"] = _keys
sys.modules["uno"].invoke = lambda obj, method, args: setattr(obj, args[0], getattr(args[1], "value", args[1]))
sys.modules["uno"].Any = lambda kind, value: types.SimpleNamespace(value=value)

from hst_office import nd30, wizard_type_picker  # noqa: E402
from hst_office.data_files import load_locale  # noqa: E402


class _Peer:
    def hasFocus(self):  # noqa: N802 - UNO method name
        return True


class _List:
    def __init__(self):
        self.visible = False

    def setVisible(self, value):  # noqa: N802 - UNO method name
        self.visible = value

    def makeVisible(self, index):  # noqa: N802 - UNO method name
        pass

    def getPeer(self):  # noqa: N802 - UNO method name
        return _Peer()


class _Dialog:
    def __init__(self):
        self.models = {"type": types.SimpleNamespace(Text="", PositionY=20, Height=12),
                       "typeList": types.SimpleNamespace(StringItemList=(), SelectedItems=(), PositionY=33)}
        self.model = types.SimpleNamespace(getByName=self.models.__getitem__)

    def set_text(self, name, text):
        self.models[name].Text = text


class TabLeavesTheList(unittest.TestCase):
    def setUp(self):
        self.chosen = []
        self.picker = wizard_type_picker.TypePicker(_Dialog(), nd30.rules()["documentTypes"], load_locale("vi")["nd30"]["groups"],
                                                    lambda: self.chosen.append(self.picker.current))
        self.picker.field, self.picker.list, self.picker.handler = _Peer(), _List(), object()
        self.picker.field.getPeer = lambda: _Peer()

    def type_query(self, text):
        self.picker.d.models["type"].Text = text
        self.picker.typed()

    def test_tab_takes_the_highlighted_type_and_closes_the_list(self):
        self.type_query("quyet")
        self.assertTrue(self.picker.open)
        self.assertTrue(self.picker.list.visible)
        handled = self.picker.key(_keys.TAB)
        self.assertFalse(handled, "Tab must stay with the dialog so the focus moves on")
        self.assertEqual(self.picker.current, "quyet-dinh")
        self.assertFalse(self.picker.open)
        self.assertFalse(self.picker.list.visible)
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

    def test_enter_still_chooses_and_is_kept_from_the_dialog(self):
        self.type_query("thong tri")
        self.assertTrue(self.picker.key(_keys.RETURN))
        self.assertEqual(self.picker.current, "dang-thong-tri")


if __name__ == "__main__":
    unittest.main()
