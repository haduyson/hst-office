# SPDX-License-Identifier: LicenseRef-HST-Proprietary
# Copyright (C) 2026 HASON TECH
"""Native full screen of an office window read from AppKit (mac_native_window), without macOS: the Objective-C calls
are replaced by a fake that answers like [[view window] styleMask]."""
import sys
import types
import unittest
from unittest import mock

import _paths  # noqa: F401
from hst_office import mac_native_window as mnw  # noqa: E402

VIEW, WINDOW = 0x1000, 0x2000


class Peer:
    def __init__(self, handle):
        self.handle = handle

    def getWindowHandle(self, process_id, system_type):  # noqa: N802 - UNO method name
        assert system_type == mnw.SYSTEM_MAC
        return self.handle


def fake_send(mask):
    def send(obj, selector, restype=None):
        return {(VIEW, "window"): WINDOW, (WINDOW, "styleMask"): mask}.get((obj, selector))
    return send


class FullScreenTests(unittest.TestCase):
    def setUp(self):
        uno = types.SimpleNamespace(ByteSequence=bytes)
        patcher = mock.patch.dict(sys.modules, {"uno": uno})
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_full_screen_style_mask_is_read_on_macos(self):
        with mock.patch.object(mnw, "send", fake_send(mnw.FULL_SCREEN_MASK | 0xF)):
            self.assertIs(mnw.is_full_screen(Peer(VIEW), "darwin"), True)
        with mock.patch.object(mnw, "send", fake_send(0xF)):
            self.assertIs(mnw.is_full_screen(Peer(VIEW), "darwin"), False)

    def test_unknown_without_a_handle_a_window_or_the_runtime(self):
        with mock.patch.object(mnw, "send", fake_send(mnw.FULL_SCREEN_MASK)):
            self.assertIsNone(mnw.is_full_screen(Peer(0), "darwin"))
            self.assertIsNone(mnw.is_full_screen(Peer(None), "darwin"))
            self.assertIsNone(mnw.is_full_screen(Peer(0x3000), "darwin"))  # a view without a window
            self.assertIsNone(mnw.is_full_screen(None, "darwin"))
        with mock.patch.object(mnw, "send", side_effect=OSError("no libobjc")):
            self.assertIsNone(mnw.is_full_screen(Peer(VIEW), "darwin"))

    def test_other_platforms_are_never_asked(self):
        with mock.patch.object(mnw, "send", side_effect=AssertionError("asked")):
            for platform in ("win32", "linux"):
                self.assertIsNone(mnw.is_full_screen(Peer(VIEW), platform))


class AppKit:
    """Fake NSWindows: {address: dict(parent, visible, mask, active)}; records the calls that move a window."""

    def __init__(self, windows):
        self.windows, self.calls = windows, []

    def send(self, obj, selector, restype=None, argtypes=(), *args):
        w = self.windows.get(obj, {})
        if selector == "window":
            return obj + 1 if obj in (VIEW,) else None
        answers = {"parentWindow": w.get("parent"), "isVisible": w.get("visible", True),
                   "styleMask": w.get("mask", 0), "isOnActiveSpace": w.get("active", False)}
        if selector in answers:
            return answers[selector]
        self.calls.append((obj, selector) + args)
        return None


TARGET = VIEW + 1  # the new document's NSWindow (its view's window)
OLD, DIALOG, TOOLTIP, OWN_DIALOG = 0x5000, 0x5100, 0x5200, 0x5300
FS, TITLED = mnw.FULL_SCREEN_MASK | mnw.TITLED_MASK, mnw.TITLED_MASK


class AdoptTests(unittest.TestCase):
    def setUp(self):
        patcher = mock.patch.dict(sys.modules, {"uno": types.SimpleNamespace(ByteSequence=bytes)})
        patcher.start()
        self.addCleanup(patcher.stop)

    def appkit(self, old_active=False, target_active=True, dialog_visible=True):
        return AppKit({
            TARGET: {"mask": FS, "active": target_active},
            OLD: {"mask": FS, "active": old_active},
            DIALOG: {"parent": OLD, "mask": TITLED, "visible": dialog_visible},
            TOOLTIP: {"parent": OLD, "mask": 0},  # no title bar: a tooltip, menu or the tab strip
            OWN_DIALOG: {"parent": TARGET, "mask": TITLED},  # already on the new document
        })

    def adopt(self, kit):
        with mock.patch.object(mnw, "send", kit.send), \
                mock.patch.object(mnw, "app_windows", return_value=[OLD, DIALOG, TOOLTIP, TARGET, OWN_DIALOG]):
            return mnw.adopt_dialogs(Peer(VIEW), "darwin")

    def test_a_dialog_left_in_the_full_screen_space_moves_onto_the_new_document(self):
        kit = self.appkit()
        self.assertEqual(self.adopt(kit), 1)
        self.assertEqual(kit.calls, [(OLD, "removeChildWindow:", DIALOG),
                                     (TARGET, "addChildWindow:ordered:", DIALOG, mnw.ABOVE),
                                     (DIALOG, "makeKeyAndOrderFront:", None)])

    def test_nothing_moves_when_the_parent_is_on_screen_or_the_dialog_hidden(self):
        for kit in (self.appkit(old_active=True), self.appkit(dialog_visible=False), self.appkit(target_active=False)):
            self.assertEqual(self.adopt(kit), 0)
            self.assertEqual(kit.calls, [])

    def test_a_parent_not_in_full_screen_keeps_its_dialog(self):
        kit = self.appkit()
        kit.windows[OLD]["mask"] = TITLED
        self.assertEqual(self.adopt(kit), 0)

    def test_never_on_other_platforms_and_appkit_errors_reach_the_caller(self):
        self.assertEqual(mnw.adopt_dialogs(Peer(VIEW), "win32"), 0)
        with mock.patch.object(mnw, "send", side_effect=OSError("no libobjc")):
            with self.assertRaises(OSError):  # mac_full_screen_dialogs.adopt logs it
                mnw.adopt_dialogs(Peer(VIEW), "darwin")


if __name__ == "__main__":
    unittest.main()
