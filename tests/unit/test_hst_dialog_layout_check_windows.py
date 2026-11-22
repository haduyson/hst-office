# SPDX-License-Identifier: LicenseRef-HST-Proprietary
# Copyright (C) 2026 HASON TECH
"""The dialog layout check's window handling: which cases run, which windows count as the dialog, and what is closed.

A close request sent to a tooltip crashes the office (VCL's close handling of a help window), a progress window that
goes away by itself is not the dialog, and a checker error is not an ended office."""
import os
import sys
import types
import unittest
from unittest import mock

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(ROOT, "tests", "runtime"))
import hst_dialog_layout_cases as cases  # noqa: E402
import hst_dialog_layout_check as check  # noqa: E402


class SelectCasesTest(unittest.TestCase):
    def test_all_includes_every_batch_case(self):
        extra = cases.load_extra()
        self.assertIn("toc-entry-structure", extra)
        every = check.select_cases(every=True)
        for ident in list(cases.CANDIDATES) + list(extra):
            self.assertIn(ident, every)

    def test_default_is_the_ranked_list_with_batch_cases(self):
        self.assertEqual(set(check.select_cases()), set(cases.listed()))

    def test_ids_pick_batch_cases_too(self):
        self.assertEqual(list(check.select_cases(ids=["toc-entry-structure"])), ["toc-entry-structure"])
        with self.assertRaises(SystemExit):
            check.select_cases(ids=["no-such-dialog"])


def gtk3_platform(windows, types_by_key):
    """A gtk3 Platform whose X top-levels are `windows` (a list of key lists, one per look) with the window types
    `types_by_key` ('gone' for a window xprop no longer finds)."""
    args = types.SimpleNamespace(plugin="gtk3", display=":0")
    platform = check.Platform(args, office=None)
    looks = iter(windows)
    last = []

    def top_windows():
        nonlocal last
        last = next(looks, last)
        return {key: (key, "") for key in last}

    def xprop(cmd, **_kwargs):
        key = cmd[cmd.index("-id") + 1]
        kind = types_by_key.get(key, "_NET_WM_WINDOW_TYPE_DIALOG")
        out = (f"{key}: BadWindow" if kind == "gone"
               else f"_NET_WM_WINDOW_TYPE(ATOM) = {kind}")
        return types.SimpleNamespace(stdout=out, returncode=0)

    platform.top_windows = top_windows
    return platform, xprop


class WindowsTest(unittest.TestCase):
    def test_tooltip_is_never_closed(self):
        platform, xprop = gtk3_platform([["0x1", "0x2"], []],
                                        {"0x2": "_NET_WM_WINDOW_TYPE_TOOLTIP"})
        sent = []
        fake_gui = types.SimpleNamespace(send_close_request=lambda key, _display: sent.append(key))
        with mock.patch.object(check.subprocess, "run", side_effect=xprop), \
                mock.patch.dict(sys.modules, {"hst_gui": fake_gui}), mock.patch.object(check.time, "sleep"):
            self.assertTrue(platform.close(["0x1"], before={}))
        self.assertEqual(sent, ["0x1"])

    def test_open_tooltip_alone_does_not_keep_the_dialog_open(self):
        platform, xprop = gtk3_platform([["0x2"]], {"0x2": "_NET_WM_WINDOW_TYPE_TOOLTIP"})
        with mock.patch.object(check.subprocess, "run", side_effect=xprop), mock.patch.object(check.time, "sleep"):
            self.assertTrue(platform.close([], before={}))

    def test_wait_new_takes_the_dialog_shown_after_the_paint(self):
        # the first-use progress window (0x5) is gone after the wait; the real dialog (0x6) then shows
        platform, xprop = gtk3_platform([["0x5"], [], ["0x6"], ["0x6"]], {})
        with mock.patch.object(check.subprocess, "run", side_effect=xprop), mock.patch.object(check.time, "sleep"):
            self.assertEqual(platform.wait_new(before={}, timeout=60), ["0x6"])

    def test_wait_new_ignores_a_tooltip(self):
        platform, xprop = gtk3_platform([["0x7"]] * 3, {"0x7": "_NET_WM_WINDOW_TYPE_TOOLTIP"})
        clock = iter(range(0, 1000, 10))
        with mock.patch.object(check.subprocess, "run", side_effect=xprop), \
                mock.patch.object(check.time, "sleep"), mock.patch.object(check.time, "time", lambda: next(clock)):
            self.assertEqual(platform.wait_new(before={}, timeout=25), [])


class FakeUno(types.ModuleType):
    def __init__(self):
        super().__init__("uno")

    @staticmethod
    def getTypeByName(name):
        return name


class EndExecuteTest(unittest.TestCase):
    def test_only_on_a_dialog(self):
        dialog = mock.Mock()
        window = mock.Mock()
        window.queryInterface.return_value = dialog
        not_dialog = mock.Mock()
        not_dialog.queryInterface.return_value = None
        with mock.patch.dict(sys.modules, {"uno": FakeUno()}):
            self.assertTrue(check.end_execute(window))
            self.assertFalse(check.end_execute(not_dialog))
        dialog.endExecute.assert_called_once_with()
        not_dialog.endExecute.assert_not_called()


class OfficeAliveTest(unittest.TestCase):
    def test_alive_and_dead(self):
        office = mock.Mock()
        self.assertTrue(check.office_alive(office))
        office.desktop.side_effect = RuntimeError("binary URP bridge disposed")
        self.assertFalse(check.office_alive(office))


if __name__ == "__main__":
    unittest.main()
