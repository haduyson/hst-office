# SPDX-License-Identifier: AGPL-3.0-only
"""The Windows harness input gate: real keys reach only a verified HST Office window. A key meant for an office
dialog must never land on the desktop, the taskbar or a system dialog (Alt+F4 then Enter there powers the PC off),
and windows are closed with WM_CLOSE to their own HWND, never with keys."""
import ctypes
import importlib
import os
import sys
import types
import unittest
from unittest import mock

import windows_input_fakes as fakes
from windows_input_fakes import (DESKTOP, DIALOG, DOC, EXPLORER, FOREIGN_SAL, OTHER_OFFICE, SHELL, SHUTDOWN, TRAY,
                                 FakeApi)


class GuardRulesTests(unittest.TestCase):
    def setUp(self):
        self.api = FakeApi()
        self.guard, *_ = fakes.install(self.api)

    def test_office_windows_pass_and_everything_else_is_refused(self):
        self.assertIsNone(self.guard.refusal(DOC, self.api))
        self.assertIsNone(self.guard.refusal(DIALOG, self.api))
        for hwnd in (0, DESKTOP, SHELL, TRAY, 0x60, SHUTDOWN, EXPLORER, FOREIGN_SAL, 0x999):
            self.assertIsNotNone(self.guard.refusal(hwnd, self.api), hex(hwnd))

    def test_foreground_check_raises_for_desktop_shell_and_system_dialogs(self):
        for hwnd in (0, DESKTOP, SHELL, TRAY, 0x60, SHUTDOWN, EXPLORER, FOREIGN_SAL):
            self.api.foreground_window = hwnd
            with self.assertRaises(self.guard.BlockedInput, msg=hex(hwnd)):
                self.guard.check_foreground()
        self.api.foreground_window = DIALOG
        self.assertEqual(self.guard.check_foreground(DOC), DIALOG)  # same office process

    def test_another_office_process_is_not_the_target(self):
        self.api.foreground_window = OTHER_OFFICE
        self.assertEqual(self.guard.check_foreground(), OTHER_OFFICE)
        with self.assertRaises(self.guard.BlockedInput):
            self.guard.check_foreground(DOC)

    def test_alt_f4_and_windows_keys_are_never_allowed(self):
        for chord in ((0x12, 0x73), (0xA4, 0x73), (0x5B,), (0x5C, 0x58), (0x5F,)):
            with self.assertRaises(self.guard.BlockedInput, msg=chord):
                self.guard.check_chord(chord)
        self.guard.check_chord((0x11, 0x12, 0xBE))  # Ctrl+Alt+. stays allowed
        self.guard.check_chord((0x73,))

    def test_bring_to_front_presses_alt_only_while_an_office_window_is_in_front(self):
        pressed = []
        self.api.foreground_window = SHELL
        self.assertFalse(self.guard.bring_to_front(DOC, lambda: pressed.append("alt"), self.api))
        self.assertEqual(pressed, [])
        self.api.foreground_window = DIALOG
        self.guard.bring_to_front(DOC, lambda: pressed.append("alt"), self.api)
        self.assertEqual(pressed, ["alt"])
        self.api.grants.add(DOC)
        self.assertTrue(self.guard.bring_to_front(DOC, lambda: pressed.append("alt"), self.api))
        self.assertEqual(pressed, ["alt"])  # the plain call worked: no key

    def test_clicks_only_into_office_windows(self):
        self.guard.check_point(10, 10)
        for hwnd in (SHELL, TRAY, SHUTDOWN, EXPLORER):
            self.api.under_pointer = hwnd
            with self.assertRaises(self.guard.BlockedInput):
                self.guard.check_point(10, 10)


class SendInputTests(unittest.TestCase):
    def setUp(self):
        self.api = FakeApi()
        self.guard, self.input, self.dialogs, self.user32 = fakes.install(self.api)

    def test_keys_into_the_office_window_are_sent(self):
        self.input.keys("tab", "space")
        self.assertEqual([events for _front, events in self.user32.sent],
                         [[(0x09, False), (0x09, True)], [(0x20, False), (0x20, True)]])
        self.assertTrue(all(front == DOC for front, _events in self.user32.sent))

    def test_no_key_reaches_the_desktop_taskbar_or_shutdown_dialog(self):
        for hwnd in (0, DESKTOP, SHELL, TRAY, 0x60, SHUTDOWN, EXPLORER, FOREIGN_SAL):
            self.api.foreground_window = hwnd
            for send in (lambda: self.input.keys("escape"), lambda: self.input.keys("enter"),
                         lambda: self.input.key_press(0x0D), lambda: self.input.chord(0x11, 0x57)):
                with self.assertRaises(self.input.BlockedInput):
                    send()
        self.assertEqual(self.user32.sent, [])

    def test_the_foreground_is_rechecked_before_every_key(self):
        def dialog_closed_desktop_in_front(user32):
            self.api.foreground_window = SHELL
        self.user32.after_send = dialog_closed_desktop_in_front
        with self.assertRaises(self.input.BlockedInput):
            self.input.keys("escape", "enter", target=DOC)
        self.assertEqual(len(self.user32.sent), 1)  # Escape went to the office; Enter never reached the desktop

    def test_target_not_ours_or_not_in_front_sends_nothing(self):
        with self.assertRaises(self.input.BlockedInput):
            self.input.keys("escape", target=EXPLORER)
        self.api.foreground_window = SHELL  # cannot be brought to the front and Alt is not pressed into the shell
        with self.assertRaises(self.input.BlockedInput):
            self.input.keys("escape", target=DOC)
        self.assertEqual(self.user32.sent, [])

    def test_alt_f4_is_refused_even_into_an_office_window(self):
        with self.assertRaises(self.input.BlockedInput):
            self.input.chord(0x12, 0x73, target=DOC)
        self.assertEqual(self.user32.sent, [])

    def test_foreground_and_activate_ignore_foreign_windows(self):
        self.assertFalse(self.input.foreground(EXPLORER))
        self.assertFalse(self.input.activate(SHUTDOWN))
        self.assertEqual(self.user32.sent, [])

    def test_close_dialog_posts_wm_close_to_its_own_hwnd_and_sends_no_key(self):
        window = mock.Mock()
        window.getWindowHandle.return_value = DIALOG
        sys.modules["uno"] = types.SimpleNamespace(ByteSequence=bytes)
        self.addCleanup(sys.modules.pop, "uno", None)
        self.assertEqual(self.dialogs.close_dialog(window), "wm_close")
        self.assertEqual(self.api.posted, [(DIALOG, 0x0010)])
        window.endExecute.assert_not_called()
        self.assertEqual(self.user32.sent, [])

    def test_close_dialog_falls_back_to_end_execute_never_to_keys(self):
        window = mock.Mock()
        window.getWindowHandle.return_value = SHUTDOWN  # not ours: never posted to
        window.getTitle.return_value = "Shut Down Windows"
        sys.modules["uno"] = types.SimpleNamespace(ByteSequence=bytes)
        self.addCleanup(sys.modules.pop, "uno", None)
        self.assertEqual(self.dialogs.close_dialog(window), "endExecute")
        window.endExecute.side_effect = RuntimeError("no XDialog")
        self.assertEqual(self.dialogs.close_dialog(window), "open")
        self.assertEqual((self.api.posted, self.user32.sent), ([], []))


class ToolingKeyboardTests(unittest.TestCase):
    """r1auto/native.py (the tooling Python's SendInput) passes the same gate."""

    def setUp(self):
        sys.path.insert(0, os.path.join(fakes.RUNTIME, "r1auto"))
        self.addCleanup(sys.path.remove, os.path.join(fakes.RUNTIME, "r1auto"))
        sys.modules.pop("native", None)
        self.native = importlib.import_module("native")
        self.api = FakeApi()
        self.native.guard._API[:] = [self.api]
        self.sent = []
        user32 = types.SimpleNamespace(SendInput=lambda n, ref, size: self.sent.append(ref._obj.value.key.vk) or 1,
                                       SetProcessDPIAware=lambda: 1, SetCursorPos=lambda x, y: 1)
        patcher = mock.patch.object(ctypes, "windll", types.SimpleNamespace(user32=user32), create=True)
        patcher.start()
        self.addCleanup(patcher.stop)
        self.native.SYSTEM = "Windows"
        self.native.time = types.SimpleNamespace(sleep=lambda seconds: None)

    def test_keys_go_to_the_office_and_never_to_the_shell(self):
        self.native.keyboard(["escape"])
        self.assertEqual(self.sent, [27, 27])
        self.api.foreground_window = TRAY
        with self.assertRaises(self.native.guard.BlockedInput):
            self.native.keyboard(["enter"])
        with self.assertRaises(self.native.guard.BlockedInput):
            self.native.keyboard(text="x")
        self.assertEqual(self.sent, [27, 27])

    def test_click_on_the_desktop_is_refused(self):
        self.api.under_pointer = SHELL
        with self.assertRaises(self.native.guard.BlockedInput):
            self.native.pointer("click", 5, 5)
        self.assertEqual(self.sent, [])


if __name__ == "__main__":
    unittest.main()
