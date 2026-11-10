# SPDX-License-Identifier: AGPL-3.0-only
"""Tùy chọn ▸ HST Office ▸ Mở tài liệu ▸ "Lối tắt ứng dụng": labelled per OS, hidden on Windows, asks before any change
and shows failures instead of raising."""
import os
import unittest
from unittest import mock
import xml.etree.ElementTree as ET

import _paths
from hst_office import app_shortcuts as sc
from hst_office import app_shortcuts_ui as ui

HOST = "/Applications/HST Office.app"


class Control:
    def __init__(self):
        self.visible, self.model = None, type("Model", (), {"Label": "", "HelpText": ""})()

    def setVisible(self, value):
        self.visible = value

    def getModel(self):
        return self.model


class Window:
    def __init__(self):
        self.controls = {name: Control() for name in ui.CONTROLS}

    def getControl(self, name):
        return self.controls.get(name)


class OptionsSection(unittest.TestCase):
    def test_labels_per_os_and_hidden_on_windows(self):
        for system, label in (("Darwin", "Thêm vào Dock"), ("Linux", "Tạo lối tắt trên màn hình nền")):
            window = Window()
            ui.configure_page(window, system)
            self.assertTrue(all(c.visible for c in window.controls.values()))
            self.assertEqual(window.controls["appShortcuts"].model.Label, label)
        window = Window()
        ui.configure_page(window, "Windows")
        self.assertTrue(all(c.visible is False for c in window.controls.values()))

    def test_page_has_the_section_controls(self):
        root = ET.parse(os.path.join(_paths.ROOT, "extensions/hst-vietnamese-tools/dialogs/DefaultApps.xdl")).getroot()
        ids = {e.get("{http://openoffice.org/2000/dialog}id") for e in root.iter()}
        self.assertTrue(set(ui.CONTROLS) <= ids)
        macro = [e.get("{http://openoffice.org/2000/script}macro-name") for e in root.iter()
                 if e.get("{http://openoffice.org/2000/script}macro-name")]
        self.assertIn("vnd.sun.star.UNO:appShortcuts", macro)

    def test_nothing_changes_when_the_user_says_later(self):
        asked = []
        with mock.patch.object(ui, "_message", side_effect=lambda *a, **k: asked.append(k.get("ask")) or False), \
                mock.patch.object(ui.shortcuts, "installed_launchers", return_value=[]), \
                mock.patch.object(ui.shortcuts, "copy_to_desktop") as copy:
            self.assertFalse(ui.run(None, None, "Linux"))
        copy.assert_not_called()
        self.assertEqual(asked, [True])

    def test_mac_asks_before_touching_the_dock_and_refuses_a_dmg_copy(self):
        launchers = sc.mac_launchers(HOST)
        answers = []
        with mock.patch("hst_office.mac_app_location._running_bundle", return_value=HOST), \
                mock.patch.object(ui.shortcuts, "dock_status", return_value=(launchers, launchers[:1])), \
                mock.patch.object(ui, "_message", side_effect=lambda *a, **k: answers.append(a[2]) or False), \
                mock.patch.object(ui.shortcuts, "add_to_dock") as add:
            ui.run(None, None, "Darwin")
        add.assert_not_called()
        self.assertEqual(answers, [ui.TEXTS["Darwin"]["ask"]])
        answers.clear()
        with mock.patch("hst_office.mac_app_location._running_bundle", return_value="/Volumes/HST Office/HST Office.app"), \
                mock.patch.object(ui, "_message", side_effect=lambda *a, **k: answers.append(a[2]) or True), \
                mock.patch.object(ui.shortcuts, "add_to_dock") as add:
            ui.run(None, None, "Darwin")
        add.assert_not_called()
        self.assertEqual(answers, [ui.MOVE_FIRST])

    def test_failures_are_shown_never_raised(self):
        shown = []
        with mock.patch.object(ui.shortcuts, "installed_launchers", side_effect=sc.ShortcutError("thiếu")), \
                mock.patch.object(ui, "_message", side_effect=lambda *a, **k: shown.append(a[2])), \
                mock.patch.object(ui.diag_log, "exception"):
            ui.run(None, None, "Linux")
        self.assertEqual(shown, [ui.FAILED % "thiếu"])
        self.assertFalse(ui.run(None, None, "Windows"))


if __name__ == "__main__":
    unittest.main()
