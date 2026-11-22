# SPDX-License-Identifier: LicenseRef-HST-Proprietary
# Copyright (C) 2026 HASON TECH
"""A dialog moved onto a new full screen document (macOS) keeps what the user entered: its on_ready hook runs again
to hook the new controls, and every control value the hook changed is put back (dialog_model_state). Before, the
citation entry dialog filled its fields with the edited item again and the typing was lost. No office: control models
are fakes with a property set info; the UNO module is stubbed."""
import types
import unittest
from unittest import mock

import _paths  # noqa: F401
import test_dialog_on_screen as screen  # noqa: F401 - installs the UNO stubs dialogs needs
from hst_office import dialog_model_state as state  # noqa: E402
from hst_office import dialogs  # noqa: E402


class Prop:
    def __init__(self, name, type_name, attributes=0):
        self.Name, self.Attributes = name, attributes
        self.Type = types.SimpleNamespace(typeName=type_name)


class Control:
    TYPES = {"Text": "string", "Enabled": "boolean", "Label": "string", "StringItemList": "[]string",
             "SelectedItems": "[]short", "State": "short"}

    def __init__(self, log, name, **values):
        self.log, self.name, self.values = log, name, dict(values)

    def getPropertySetInfo(self):  # noqa: N802 - UNO method names
        props = [Prop(key, self.TYPES[key]) for key in self.values]
        return types.SimpleNamespace(getProperties=lambda: props + [Prop("Name", "string", state.READONLY)])

    def getPropertyValue(self, name):  # noqa: N802
        if name == "Name":
            return self.name
        return self.values[name]

    def setPropertyValue(self, name, value):  # noqa: N802
        if name == "Name":
            raise AssertionError("read-only property written")
        if name == "StringItemList":
            self.values["SelectedItems"] = ()  # like a list box: new items clear the selection
        self.values[name] = value
        self.log.append((self.name, name))


class Model:
    def __init__(self, controls):
        self.controls = {c.name: c for c in controls}
        self.Title = "Trích dẫn"

    def getElementNames(self):  # noqa: N802
        return tuple(self.controls)

    def getByName(self, name):  # noqa: N802
        return self.controls[name]


FAKE_UNO = types.SimpleNamespace(
    Any=lambda type_name, value: ("any", type_name, value),
    invoke=lambda obj, method, args: getattr(obj, method)(args[0], args[1][2]))


def citation_form(log):
    return Model([Control(log, "f_title", Text="Typed title", Enabled=True),
                  Control(log, "type", StringItemList=("book", "article"), SelectedItems=(1,)),
                  Control(log, "preview", Label="Typed title (preview)"),
                  Control(log, "f_volume", Text="", Enabled=False)])


def refill(model):
    """What the citation entry dialog's on_ready does: the edited item back into every field."""
    model.getByName("f_title").setPropertyValue("Text", "Old title")
    model.getByName("type").setPropertyValue("StringItemList", ("book", "article", "webpage"))
    model.getByName("type").setPropertyValue("SelectedItems", (0,))
    model.getByName("preview").setPropertyValue("Label", "Old title (preview)")
    model.getByName("f_volume").setPropertyValue("Enabled", True)


class SnapshotRestoreTests(unittest.TestCase):
    def setUp(self):
        patcher = mock.patch.object(state, "uno", FAKE_UNO)
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_what_the_hook_changed_is_put_back_and_nothing_else_is_written(self):
        log = []
        model = citation_form(log)
        saved = state.snapshot(model)
        refill(model)
        del log[:]
        self.assertEqual(state.restore(model, saved), 5)
        self.assertEqual(model.getByName("f_title").values, {"Text": "Typed title", "Enabled": True})
        self.assertEqual(model.getByName("type").values["SelectedItems"], (1,))
        self.assertEqual(model.getByName("preview").values["Label"], "Typed title (preview)")
        self.assertFalse(model.getByName("f_volume").values["Enabled"])
        # the items before the selection: setting the items clears a selection put back before them
        self.assertLess(log.index(("type", "StringItemList")), log.index(("type", "SelectedItems")))
        self.assertNotIn(("f_volume", "Text"), log)  # unchanged: not written

    def test_a_property_that_cannot_be_set_does_not_stop_the_others(self):
        log = []
        model = citation_form(log)
        saved = state.snapshot(model)
        refill(model)
        broken = model.getByName("preview")
        broken.setPropertyValue = mock.Mock(side_effect=RuntimeError("disposed"))
        state.restore(model, saved)
        self.assertEqual(model.getByName("f_title").values["Text"], "Typed title")

    def test_not_a_container_keeps_nothing(self):
        self.assertEqual(state.snapshot(object()), {})


class MoveKeepsEntriesTests(unittest.TestCase):
    """dialogs.Dialog._move_to: the on_ready fallback runs with the entered values kept; on_moved runs as it is."""

    def moved_dialog(self, model):
        office = screen.Office()
        dialog = dialogs.Dialog.__new__(dialogs.Dialog)
        dialog.ctx = dialog.smgr = office
        dialog.model, dialog._listeners, dialog._watchers = model, [], []
        old = screen.UnoDialog()
        old.dispose = lambda: None
        dialog.dialog = old

        def new_control():
            d = screen.UnoDialog()
            d.setModel = d.setVisible = lambda *args: None
            d.createPeer = lambda toolkit, parent: None
            return d
        office.createInstanceWithContext = lambda name, ctx: new_control()
        return dialog

    def test_citation_dialog_keeps_what_was_typed_after_the_move(self):
        model = citation_form([])
        dialog = self.moved_dialog(model)
        dialog.on_moved, dialog.on_ready = None, lambda: refill(model)
        with mock.patch.object(state, "uno", FAKE_UNO), mock.patch.object(dialogs.dialog_on_screen.diag_log, "info"):
            dialog._move_to(None, screen.Window(True))
        self.assertEqual(model.getByName("f_title").values["Text"], "Typed title")
        self.assertEqual(model.getByName("type").values["SelectedItems"], (1,))

    def test_an_own_on_moved_hook_runs_without_on_ready(self):
        model = citation_form([])
        dialog = self.moved_dialog(model)
        calls = []
        dialog.on_moved, dialog.on_ready = (lambda: calls.append("moved")), (lambda: calls.append("ready"))
        with mock.patch.object(dialogs.dialog_on_screen.diag_log, "info"):
            dialog._move_to(None, screen.Window(True))
        self.assertEqual(calls, ["moved"])


if __name__ == "__main__":
    unittest.main()
