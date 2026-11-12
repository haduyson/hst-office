# SPDX-License-Identifier: AGPL-3.0-only
"""Setting and administrator lock of "Phiên bản trước" and its options page."""
import os
import plistlib
import tempfile
import unittest
import xml.etree.ElementTree as ET
from unittest import mock

from install_id_support import DLG, EXT, OOR
from hst_office import version_config as config
from hst_office import version_options as opts
from hst_office import version_texts as T


class FakeWinreg:
    HKEY_LOCAL_MACHINE, HKEY_CURRENT_USER = "HKLM", "HKCU"

    def __init__(self, keys):
        self.keys = keys  # {(hive, path): {name: value}}

    class _Key:
        def __init__(self, values):
            self.values = values

        def __enter__(self):
            return self

        def __exit__(self, *exc):
            return False

    def OpenKey(self, hive, path):  # noqa: N802 - winreg API
        if (hive, path) not in self.keys:
            raise FileNotFoundError(path)
        return self._Key(self.keys[(hive, path)])

    def QueryValueEx(self, key, name):  # noqa: N802 - winreg API
        if name not in key.values:
            raise FileNotFoundError(name)
        return key.values[name], 1


class Policy(unittest.TestCase):
    def test_precedence(self):
        self.assertEqual(config.resolve(None, None, None), (True, False))  # default on
        self.assertEqual(config.resolve((False, False), None, None), (False, False))  # the user's choice
        self.assertEqual(config.resolve((False, True), None, None), (False, True))  # finalized configuration
        self.assertEqual(config.resolve((True, True), None, False), (False, True))  # macOS profile over it
        self.assertEqual(config.resolve((True, False), False, True), (False, True))  # Windows policy first

    def test_windows_policy_key(self):
        key = config.POLICY_KEY
        self.assertEqual(key, "SOFTWARE\\Policies\\HASON TECH\\HST Office\\"
                              "org.hasontech.hstoffice.PreviousVersions\\Enabled")
        self.assertIsNone(config.windows_policy(FakeWinreg({})))
        self.assertIsNone(config.windows_policy(FakeWinreg({("HKLM", key): {"Value": "false"}})))  # not final
        self.assertFalse(config.windows_policy(FakeWinreg({("HKLM", key): {"Value": "false", "Final": 1}})))
        both = {("HKLM", key): {"Value": "true", "Final": 1}, ("HKCU", key): {"Value": "false", "Final": 1}}
        self.assertTrue(config.windows_policy(FakeWinreg(both)))  # the machine's policy wins
        self.assertFalse(config.windows_policy(FakeWinreg({("HKCU", key): {"Value": "False", "Final": 1}})))
        self.assertIsNone(config.windows_policy(FakeWinreg({("HKLM", key): {"Value": "maybe", "Final": 1}})))

    def test_macos_profile(self):
        with tempfile.TemporaryDirectory() as base:
            self.assertIsNone(config.macos_policy("an", base))
            with open(os.path.join(base, "vn.hasontech.hstoffice.plist"), "wb") as handle:
                plistlib.dump({"PreviousVersions": {"Enabled": False}, "HSTUpdate": {"AutoCheck": False}}, handle)
            self.assertIs(config.macos_policy("an", base), False)
            os.makedirs(os.path.join(base, "an"))
            with open(os.path.join(base, "an", "vn.hasontech.hstoffice.plist"), "wb") as handle:
                plistlib.dump({"PreviousVersions": {"Enabled": True}}, handle)
            self.assertIs(config.macos_policy("an", base), True)  # the per-user profile over the machine's
            from hst_office import update_config
            self.assertEqual(update_config.macos_managed("an", base), {"AutoCheck": False})  # update lock unchanged

    def test_load_and_save_through_the_configuration(self):
        node = mock.Mock()
        with mock.patch("hst_office.update_config._read", return_value={"Enabled": (False, False)}), \
                mock.patch("hst_office.update_config._node", return_value=node), \
                mock.patch.object(config, "windows_policy", return_value=None), \
                mock.patch.object(config, "macos_policy", return_value=None):
            self.assertEqual(config.load(None), (False, False))
            self.assertTrue(config.save(None, True))
            node.setPropertyValue.assert_called_with("Enabled", True)
            node.commitChanges.assert_called_once()
        with mock.patch("hst_office.update_config._read", return_value={"Enabled": (True, True)}), \
                mock.patch("hst_office.update_config._node", return_value=node), \
                mock.patch.object(config, "windows_policy", return_value=None), \
                mock.patch.object(config, "macos_policy", return_value=None):
            self.assertFalse(config.save(None, False))  # locked: nothing written
            self.assertEqual(node.commitChanges.call_count, 1)


class OptionsPage(unittest.TestCase):
    def controls(self):
        root = ET.parse(os.path.join(EXT, "dialogs", "PreviousVersions.xdl")).getroot()
        return {c.get(DLG + "id"): c for c in root.iter() if c.get(DLG + "id")}

    def window(self):
        controls = {name: mock.Mock() for name in self.controls()}
        window = mock.Mock()
        window.getControl.side_effect = controls.__getitem__
        return window, controls

    def test_registered_in_the_hst_office_group(self):
        root = ET.parse(os.path.join(EXT, "OptionsDialog.xcu")).getroot()
        leaf = next(n for n in root.iter("node")
                    if n.get(OOR + "name") == "vn.hasontech.hstoffice.Options.PreviousVersions")
        props = {p.get(OOR + "name"): p.find("value").text for p in leaf.findall("prop")}
        self.assertEqual(props["Label"], "Phiên bản trước")
        self.assertEqual(props["OptionsPage"], "%origin%/dialogs/PreviousVersions.xdl")
        self.assertEqual(props["EventHandlerService"], opts.HANDLER_NAME)

    def test_texts(self):
        controls = self.controls()
        box = controls["enabled"]
        self.assertEqual(box.tag, DLG + "checkbox")
        self.assertEqual(box.get(DLG + "value"), "Lưu phiên bản trước khi ghi đè tệp")
        self.assertEqual(box.get(DLG + "checked"), "true")
        self.assertEqual(controls["clear"].get(DLG + "value"), "Xóa toàn bộ phiên bản đã lưu")
        self.assertEqual(controls["confirmText"].get(DLG + "value"), T.CLEAR_CONFIRM)
        self.assertEqual(controls["locked"].get(DLG + "value"), T.OPTIONS_LOCKED)
        note = controls["note"].get(DLG + "value")
        for fact in ("10 bản", "30 ngày", "2 GB", "100 MB", "không được gửi đi"):
            self.assertIn(fact, note)
        methods = {e.get("{http://openoffice.org/2000/script}macro-name").split(":")[-1]
                   for e in ET.parse(os.path.join(EXT, "dialogs", "PreviousVersions.xdl")).getroot().iter()
                   if e.get("{http://openoffice.org/2000/script}macro-name")}
        self.assertEqual(methods, set(opts.METHODS) - {"external_event"})

    def test_value_to_save(self):
        self.assertIs(opts.value_to_save(False, True, False), False)
        self.assertIsNone(opts.value_to_save(True, True, False))  # unchanged
        self.assertIsNone(opts.value_to_save(False, True, True))  # locked

    def test_load_save_and_lock(self):
        window, controls = self.window()
        store = mock.Mock()
        store.usage.return_value = (2, 5, 3 * 1024 * 1024)
        handler = opts.PreviousVersionsOptionsHandler(None)
        with mock.patch("hst_office.version_config.load", return_value=(True, False)), \
                mock.patch("hst_office.version_config.store", return_value=store), \
                mock.patch("hst_office.version_config.save") as save:
            self.assertTrue(handler.callHandlerMethod(window, "initialize", "external_event"))
            controls["enabled"].setState.assert_called_with(1)
            controls["enabled"].setEnable.assert_called_with(True)
            controls["locked"].setVisible.assert_called_with(False)
            controls["usage"].setText.assert_called_with("Đang lưu 5 phiên bản của 2 tệp, tổng 3 MB.")
            for name in opts.CONFIRM_CONTROLS:
                controls[name].setVisible.assert_called_with(False)
            controls["enabled"].getState.return_value = 0
            handler.callHandlerMethod(window, "ok", "external_event")
            save.assert_called_once_with(None, False)
        window, controls = self.window()
        with mock.patch("hst_office.version_config.load", return_value=(False, True)), \
                mock.patch("hst_office.version_config.store", return_value=store), \
                mock.patch("hst_office.version_config.save") as save:
            handler.callHandlerMethod(window, "initialize", "external_event")
            controls["enabled"].setState.assert_called_with(0)
            controls["enabled"].setEnable.assert_called_with(False)
            controls["locked"].setVisible.assert_called_with(True)
            controls["enabled"].getState.return_value = 1
            handler.callHandlerMethod(window, "ok", "external_event")
            save.assert_not_called()

    def test_clear_asks_on_the_page_first(self):
        window, controls = self.window()
        store = mock.Mock()
        store.clear.return_value = 7
        handler = opts.PreviousVersionsOptionsHandler(None)
        with mock.patch("hst_office.version_config.store", return_value=store), \
                mock.patch("hst_office.diag_log.info"):
            handler.callHandlerMethod(window, None, "clearVersions")
            store.clear.assert_not_called()
            controls["confirmClear"].setVisible.assert_called_with(True)
            controls["clear"].setEnable.assert_called_with(False)
            handler.callHandlerMethod(window, None, "cancelClear")
            store.clear.assert_not_called()
            controls["confirmClear"].setVisible.assert_called_with(False)
            handler.callHandlerMethod(window, None, "clearVersions")
            handler.callHandlerMethod(window, None, "confirmClear")
            store.clear.assert_called_once()
            controls["usage"].setText.assert_called_with("Đã xóa 7 phiên bản.")
        self.assertFalse(handler.callHandlerMethod(window, None, "unknown"))


if __name__ == "__main__":
    unittest.main()
