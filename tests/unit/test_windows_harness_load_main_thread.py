# SPDX-License-Identifier: AGPL-3.0-only
"""The Windows harness loads documents on the office's main thread (OnMainThread), as a user's open does.

Loaded from the UNO bridge thread, the frame, sidebar and toolbars were built in that thread; on Windows each
drop-down box's frame is then created by the main thread with the SolarMutex released, and the main thread's own
sidebar update ran into the half-built boxes: an access violation at Sheets start in 3 of 20 fresh starts on
HST4 (DataChanged on a ComboBox without its list, or a FloatingWindow built on a ComboBox disposed meanwhile)."""
import sys
import tempfile
import types
import unittest
from unittest import mock

import windows_input_fakes as fakes
from windows_input_fakes import FakeApi


class PropertyValue:
    def __init__(self):
        self.Name, self.Value = None, None


def install_uno_stub():
    beans = types.ModuleType("com.sun.star.beans")
    beans.PropertyValue = PropertyValue
    for name in ("com", "com.sun", "com.sun.star"):
        sys.modules.setdefault(name, types.ModuleType(name))
    sys.modules["com.sun.star.beans"] = beans


def loaded_args(load):
    """The (url, target, flags, args) the harness passed to Desktop.loadComponentFromURL, args as a dict."""
    desktop = mock.Mock()
    load(desktop)
    url, target, flags, args = desktop.loadComponentFromURL.call_args.args
    return url, target, {p.Name: p.Value for p in args}


class WinOfficeLoadTests(unittest.TestCase):
    def setUp(self):
        install_uno_stub()
        fakes.install(FakeApi())
        import windows_gui_office as office_module
        self.office = office_module.WinOffice("C:/inst", tempfile.mkdtemp(), 2170, tempfile.mkdtemp())

    def load(self, *args, **kwargs):
        def run(desktop):
            with mock.patch.object(type(self.office), "desktop", new_callable=mock.PropertyMock,
                                   return_value=desktop):
                self.office.load(*args, **kwargs)
        return loaded_args(run)

    def test_loads_on_the_main_thread_by_default(self):
        url, target, args = self.load("private:factory/scalc")
        self.assertEqual((url, target), ("private:factory/scalc", "_blank"))
        self.assertEqual(args, {"OnMainThread": True, "Hidden": False})

    def test_extra_properties_and_hidden_keep_the_main_thread(self):
        _, _, args = self.load("file:///C:/hst-test/a.ods", hidden=True, ReadOnly=True)
        self.assertEqual(args, {"OnMainThread": True, "ReadOnly": True, "Hidden": True})

    def test_a_bridge_thread_load_stays_possible_on_purpose(self):
        _, _, args = self.load("private:factory/swriter", OnMainThread=False)
        self.assertIs(args["OnMainThread"], False)


class HstGuiWindowsLoadTests(unittest.TestCase):
    def test_loads_on_the_main_thread(self):
        install_uno_stub()
        sys.modules.setdefault("windows_gui", types.SimpleNamespace(WinOffice=object))
        sys.modules.setdefault("hst_gui_profile", types.SimpleNamespace(seed_profile=lambda *a, **k: None))
        import hst_gui_windows
        harness = object.__new__(hst_gui_windows.Office)
        _, target, args = loaded_args(lambda desktop: (setattr(harness, "desktop", lambda: desktop),
                                                       harness.load("private:factory/scalc")))
        self.assertEqual(target, "_blank")
        self.assertEqual(args, {"Hidden": False, "OnMainThread": True})


if __name__ == "__main__":
    unittest.main()
