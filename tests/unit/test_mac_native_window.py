# SPDX-License-Identifier: LicenseRef-HST-Proprietary
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


if __name__ == "__main__":
    unittest.main()
