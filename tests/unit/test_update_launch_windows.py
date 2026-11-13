# SPDX-License-Identifier: AGPL-3.0-only
"""Windows "Cập nhật ngay": the helper starts elevated from the office window before the office quits.

The helper used to ask for administrator rights itself after the office had closed: Windows treats that as a background
request (a blinking taskbar button only), so nothing seemed to happen and the old build reopened."""
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest import mock

import _paths  # noqa: F401
from hst_office import update_elevate_windows as elevate
from hst_office import update_launch as launch
from test_update_launch import FakeDesktop, office


class FakeWin32:
    """user32/shell32/kernel32 stand-ins: ShellExecuteExW records what it was given and answers like Windows."""

    def __init__(self, ok=True, error=0, foreground=0x1234, owner=None):
        self.ok, self.error, self.foreground, self.owner, self.info, self.closed = ok, error, foreground, owner, None, []

    def GetForegroundWindow(self):
        return self.foreground

    def GetWindowThreadProcessId(self, hwnd, pid):
        pid._obj.value = os.getpid() if self.owner is None else self.owner
        return 1

    def ShellExecuteExW(self, info):
        self.info = info._obj
        if self.ok:
            self.info.hProcess = 0x99
        return self.ok

    def GetLastError(self):
        return self.error

    def GetProcessId(self, handle):
        return 4321

    def CloseHandle(self, handle):
        self.closed.append(handle)


class RunElevated(unittest.TestCase):
    ARGV = ["powershell.exe", "-File", r"C:\Users\Người dùng\AppData\Local\HSTOffice\update\hst-update.ps1", "-ProcessId", "7"]

    def test_runas_with_the_office_window_as_owner(self):
        api = FakeWin32()
        self.assertEqual(elevate.run_elevated(self.ARGV[0], subprocess.list2cmdline(self.ARGV[1:]), api=(api, api, api)), 4321)
        info = api.info
        self.assertEqual((info.lpVerb, info.lpFile, info.nShow), ("runas", "powershell.exe", 0))
        self.assertEqual(info.lpParameters, subprocess.list2cmdline(self.ARGV[1:]))
        self.assertEqual(info.hwnd, 0x1234)
        self.assertEqual(info.fMask, 0x40 | 0x100 | 0x400)
        self.assertEqual(api.closed, [0x99])

    def test_foreground_window_of_another_process_is_not_used_as_owner(self):
        api = FakeWin32(owner=os.getpid() + 1)
        elevate.run_elevated(self.ARGV[0], subprocess.list2cmdline(self.ARGV[1:]), api=(api, api, api))
        self.assertFalse(api.info.hwnd)

    def test_no_at_the_administrator_question_and_other_errors(self):
        api = FakeWin32(ok=False, error=elevate.ERROR_CANCELLED)
        with self.assertRaises(elevate.ElevationDeclined):
            elevate.run_elevated(self.ARGV[0], subprocess.list2cmdline(self.ARGV[1:]), api=(api, api, api))
        api = FakeWin32(ok=False, error=2)
        with self.assertRaises(OSError):
            elevate.run_elevated(self.ARGV[0], subprocess.list2cmdline(self.ARGV[1:]), api=(api, api, api))


class LaunchRunElevated(unittest.TestCase):
    def test_argv_is_joined_with_windows_quoting(self):
        argv = ["powershell.exe", "-File", r"C:\Users\A B\hst-update.ps1", "-Installer", r"C:\x\a b.msi"]
        with mock.patch.object(elevate, "run_elevated", return_value=7) as run:
            self.assertEqual(launch.run_elevated(argv), 7)
        run.assert_called_once_with("powershell.exe", subprocess.list2cmdline(argv[1:]))


class ElevateAndQuit(unittest.TestCase):
    def run_case(self, run=None, **desktop_options):
        calls = []
        desktop = FakeDesktop(calls, **desktop_options)
        with tempfile.TemporaryDirectory() as cache:
            marker = Path(launch.cancel_marker(cache))
            marker.write_text("stale")
            run = run or (lambda argv: calls.append(("elevated", argv, marker.exists())) or 4321)
            try:
                result = launch.elevate_and_quit(office(desktop), ["powershell.exe", "x"], cache, run=run)
            except (RuntimeError, launch.ElevationDeclined) as exc:
                result = type(exc).__name__
            return result, calls, marker.exists()

    def test_elevated_before_the_quit_and_no_marker_when_quitting(self):
        result, calls, marker = self.run_case()
        self.assertTrue(result)
        self.assertEqual(calls, [("elevated", ["powershell.exe", "x"], False), ("set", "SuspendQuickstartVeto", True),
                                 ("terminate",)])
        self.assertFalse(marker)

    def test_cancelled_or_failed_quit_leaves_the_marker_for_the_helper(self):
        for options, expected in (({"saved": False}, False), ({"error": RuntimeError("disposed")}, "RuntimeError")):
            with self.subTest(options=options):
                result, calls, marker = self.run_case(**options)
                self.assertEqual(result, expected)
                self.assertTrue(marker)

    def test_declined_elevation_keeps_the_office_open(self):
        def declined(argv):
            raise launch.ElevationDeclined()
        result, calls, marker = self.run_case(run=declined)
        self.assertEqual(result, "ElevationDeclined")
        self.assertNotIn(("terminate",), calls)



if __name__ == "__main__":
    unittest.main()
