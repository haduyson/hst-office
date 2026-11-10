# SPDX-License-Identifier: AGPL-3.0-only
"""Writing, detaching and cancelling the external updater (update_launch)."""
import os
from pathlib import Path
import signal
import subprocess
import tempfile
import unittest
from unittest import mock

import _paths  # noqa: F401
from hst_office import update_launch as launch
from update_helper_harness import HAS_SHELL, build


class LaunchContract(unittest.TestCase):
    def test_write_modes_and_encoding(self):
        with tempfile.TemporaryDirectory() as root:
            for system in ("Linux", "Darwin", "Windows"):
                directory = Path(root) / system
                helper = build(system)
                path = Path(launch.write_helper(helper, directory))
                self.assertEqual(path.read_text(encoding=helper["encoding"]), helper["text"])
                self.assertEqual(path.read_bytes().startswith(b"\xef\xbb\xbf"), system == "Windows")
                if os.name == "posix":
                    self.assertEqual(directory.stat().st_mode & 0o777, 0o700)
                    self.assertEqual(path.stat().st_mode & 0o777, 0o600 if system == "Windows" else 0o700)
            self.assertEqual(launch.log_path(root), os.path.join(root, "update.log"))

    def test_spawn_detaches_without_shell(self):
        for system in ("Linux", "Darwin", "Windows"):
            with mock.patch.object(launch.subprocess, "Popen") as popen:
                self.assertIs(launch.spawn(["helper", "some argument"], system), popen.return_value)
                args, options = popen.call_args
                self.assertEqual(args[0], ["helper", "some argument"])
                self.assertIs(options["shell"], False)
                self.assertIs(options["close_fds"], True)
                for stream in ("stdin", "stdout", "stderr"):
                    self.assertEqual(options[stream], subprocess.DEVNULL)
                if system == "Windows":
                    self.assertEqual(options["creationflags"], 0x08000208)
                    self.assertNotIn("start_new_session", options)
                else:
                    self.assertIs(options["start_new_session"], True)

    def test_cancel_exited_running_and_stubborn(self):
        proc = mock.Mock(pid=123)
        proc.poll.return_value = 0
        self.assertFalse(launch.cancel(proc))
        proc.terminate.assert_not_called()
        proc.poll.return_value = None
        for operating_system in ("posix", "nt"):
            proc.reset_mock()
            proc.wait.side_effect = [subprocess.TimeoutExpired("helper", 5), 0]
            with mock.patch.object(launch.os, "name", operating_system), mock.patch.object(launch.os, "killpg", create=True) as killpg:
                self.assertTrue(launch.cancel(proc))
                self.assertEqual(proc.wait.call_args_list, [mock.call(timeout=5), mock.call()])
                if operating_system == "posix":
                    self.assertEqual(killpg.call_args_list, [mock.call(123, signal.SIGTERM), mock.call(123, signal.SIGKILL)])
                else:
                    proc.terminate.assert_called_once_with()
                    proc.kill.assert_called_once_with()

    @unittest.skipUnless(HAS_SHELL, "POSIX process groups required")
    def test_real_spawn_and_cancel(self):
        proc = launch.spawn(["/bin/sh", "-c", "sleep 30"], "Linux")
        try:
            self.assertEqual(os.getpgid(proc.pid), proc.pid)
            self.assertTrue(launch.cancel(proc))
            self.assertIsNotNone(proc.returncode)
            self.assertFalse(launch.cancel(proc))
        finally:
            if proc.poll() is None:
                launch.cancel(proc)


class FakeDesktop:
    """Desktop.terminate() as the office does it on macOS: windows are closed first (a save prompt may be cancelled),
    then the Dock quick starter vetoes unless SuspendQuickstartVeto is set."""

    def __init__(self, calls, saved=True, error=None):
        self.calls, self.saved, self.error, self.suspended = calls, saved, error, False

    def setPropertyValue(self, name, value):
        self.calls.append(("set", name, value))
        if name == "SuspendQuickstartVeto":
            self.suspended = value

    def terminate(self):
        self.calls.append(("terminate",))
        if self.error:
            raise self.error
        return self.saved and self.suspended


def office(desktop):
    ctx = mock.Mock()
    ctx.ServiceManager.createInstanceWithContext.return_value = desktop
    return ctx


class QuitOffice(unittest.TestCase):
    def test_quick_starter_veto_is_lifted_for_the_quit(self):
        calls = []
        desktop = FakeDesktop(calls)
        self.assertTrue(launch.quit_office(office(desktop)))
        self.assertEqual(calls, [("set", "SuspendQuickstartVeto", True), ("terminate",)])

    def test_cancelled_save_prompt_keeps_the_office_and_restores_the_veto(self):
        calls = []
        desktop = FakeDesktop(calls, saved=False)
        self.assertFalse(launch.quit_office(office(desktop)))
        self.assertFalse(desktop.suspended)
        self.assertEqual(calls[-1], ("set", "SuspendQuickstartVeto", False))

    def test_failed_quit_restores_the_veto_and_raises(self):
        desktop = FakeDesktop([], error=RuntimeError("disposed"))
        with self.assertRaises(RuntimeError):
            launch.quit_office(office(desktop))
        self.assertFalse(desktop.suspended)


class SpawnAndQuit(unittest.TestCase):
    def run_case(self, **desktop_options):
        calls = []
        desktop = FakeDesktop(calls, **desktop_options)
        with mock.patch.object(launch, "spawn", side_effect=lambda argv, system: calls.append(("spawn", argv, system)) or "proc"), \
                mock.patch.object(launch, "cancel", side_effect=lambda proc: calls.append(("cancel", proc))):
            try:
                result = launch.spawn_and_quit(office(desktop), ["/bin/sh", "helper"], "Darwin")
            except RuntimeError:
                result = "raised"
        return result, calls

    def test_helper_starts_before_the_quit_and_keeps_running_when_quitting(self):
        result, calls = self.run_case()
        self.assertTrue(result)
        self.assertEqual(calls, [("spawn", ["/bin/sh", "helper"], "Darwin"), ("set", "SuspendQuickstartVeto", True),
                                 ("terminate",)])

    def test_helper_is_stopped_when_the_quit_is_cancelled_or_fails(self):
        for options, expected in (({"saved": False}, False), ({"error": RuntimeError("disposed")}, "raised")):
            with self.subTest(options=options):
                result, calls = self.run_case(**options)
                self.assertEqual(result, expected)
                self.assertEqual(calls[-1], ("cancel", "proc"))


if __name__ == "__main__":
    unittest.main()
