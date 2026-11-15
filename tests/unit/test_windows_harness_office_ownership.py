# SPDX-License-Identifier: AGPL-3.0-only
"""A Windows harness office owns exactly the soffice.bin processes started with its private profile: keys and clicks
reach only their windows, and WinOffice.stop ends only them (also the soffice.bin left by a first-start restart),
never another agent's or the owner's office."""
import os
import tempfile
import types
import unittest
from unittest import mock

import windows_input_fakes as fakes
from windows_input_fakes import DIALOG, DOC, OFFICE_PID, OTHER_OFFICE, OTHER_OFFICE_PID, FakeApi

MINE = "file:///C:/hst-test/run/profile"


def row(pid, profile, name="soffice.bin"):
    return {"ProcessId": pid, "Name": name, "CommandLine": '"D:\\inst\\program\\soffice.exe" "--norestore" '
            '"-env:UserInstallation=%s" "--accept=socket,host=127.0.0.1,port=2170;urp;"' % profile}


class ProfileMatchTests(unittest.TestCase):
    def setUp(self):
        fakes.install(FakeApi())
        import windows_gui_processes as processes
        self.processes = processes

    def test_only_the_whole_profile_url_matches(self):
        rows = [row(1, MINE), row(2, MINE + "2"), row(3, "file:///C:/hst-test/run"), row(4, MINE.upper()),
                row(5, MINE, name="soffice.exe"), row(6, "file:///C:/Users/owner/AppData/Roaming/HST Office/4"),
                {"ProcessId": 7, "Name": "soffice.bin", "CommandLine": None}]
        self.assertEqual(self.processes.owned_pids(rows, MINE), [1, 4])

    def test_terminate_ends_only_our_processes_politely_then_by_force(self):
        rows = [row(11, MINE), row(12, MINE), row(21, "file:///C:/hst-test/other/profile"), row(31, MINE + "-b")]
        killed = []

        def kill(pid, force):
            killed.append((pid, force))
            if pid == 11:  # 11 quits when asked; 12 hangs until forced
                rows[:] = [r for r in rows if r["ProcessId"] != 11]
            if force:
                rows[:] = [r for r in rows if r["ProcessId"] != pid]
        found = self.processes.terminate(MINE, timeout=0, list_pids=lambda url: self.processes.owned_pids(rows, url),
                                         kill=kill, sleep=lambda s: None)
        self.assertEqual(found, [11, 12])
        self.assertEqual(killed, [(11, False), (12, False), (12, True)])
        self.assertEqual([r["ProcessId"] for r in rows], [21, 31])

    def test_owner_follows_a_restart_of_the_office(self):
        pids = [[100], [100], [200]]
        owner = self.processes.ProfileOwner(MINE, list_pids=lambda url: pids.pop(0) if pids else [200])
        self.assertTrue(owner.owns(100))
        self.assertTrue(owner.owns(100))  # cached: no new lookup
        self.assertFalse(owner.owns(300))  # unknown: looked up again ([100])
        self.assertTrue(owner.owns(200))  # restarted under a new PID: looked up again ([200])

    def test_a_failing_process_query_owns_nothing(self):
        with mock.patch.object(self.processes.subprocess, "run", side_effect=OSError("no powershell")):
            self.assertEqual(self.processes.soffice_rows(), [])


class OwnedInputTests(unittest.TestCase):
    def setUp(self):
        self.api = FakeApi()
        self.guard, self.input, _dialogs, self.user32 = fakes.install(self.api)
        self.owner = types.SimpleNamespace(owns=lambda pid: pid == OFFICE_PID)
        self.guard.register_owner(self.owner)

    def test_keys_reach_our_office_but_not_another_office_on_the_same_desktop(self):
        self.input.keys("escape")
        self.api.foreground_window = OTHER_OFFICE  # another agent's soffice.bin
        with self.assertRaises(self.input.BlockedInput):
            self.input.keys("enter")
        self.assertEqual([front for front, _events in self.user32.sent], [DOC])

    def test_clicks_and_wm_close_spare_another_office(self):
        self.api.under_pointer = OTHER_OFFICE
        with self.assertRaises(self.guard.BlockedInput):
            self.guard.check_point(1, 1)
        self.assertFalse(self.guard.close_window(OTHER_OFFICE))
        self.assertTrue(self.guard.close_window(DIALOG))
        self.assertEqual(self.api.posted, [(DIALOG, 0x0010)])

    def test_without_owners_any_hst_office_is_accepted(self):
        self.guard.unregister_owner(self.owner)
        self.assertIsNone(self.guard.refusal(OTHER_OFFICE, self.api))
        self.assertEqual(self.api.pid(OTHER_OFFICE), OTHER_OFFICE_PID)


class WinOfficeStopTests(unittest.TestCase):
    def setUp(self):
        fakes.install(FakeApi())
        import windows_gui_guard as guard
        import windows_gui_office as office_module
        import windows_gui_processes as processes
        self.guard, self.processes = guard, processes
        self.tmp = tempfile.mkdtemp()
        self.office = office_module.WinOffice("C:/inst", os.path.join(self.tmp, "profile"), 2170, self.tmp)
        self.rows = [row(51, self.office.url), row(52, "file:///C:/hst-test/closecrash/profile"),
                     row(53, "file:///C:/Users/owner/AppData/Roaming/HST Office/4")]
        self.office.owner = processes.ProfileOwner(self.office.url, list_pids=lambda url: [51])
        guard.register_owner(self.office.owner)
        desktop = mock.Mock()
        self.office.ctx = types.SimpleNamespace(ServiceManager=types.SimpleNamespace(
            createInstanceWithContext=lambda name, ctx: desktop))
        self.office.proc = mock.Mock(returncode=0)

    def test_stop_ends_the_restarted_soffice_bin_of_our_profile_only(self):
        killed = []

        def kill(pid, force):
            killed.append(pid)
            self.rows[:] = [r for r in self.rows if r["ProcessId"] != pid]
        with mock.patch.object(self.processes, "soffice_rows", lambda: list(self.rows)), \
                mock.patch.object(self.processes, "_taskkill", kill):
            self.assertEqual(self.office.stop(), 0)
        self.assertEqual(killed, [51])
        self.assertEqual(self.office.leftover, [51])
        self.assertEqual([r["ProcessId"] for r in self.rows], [52, 53])
        self.assertEqual(self.guard._OWNERS, [])


if __name__ == "__main__":
    unittest.main()
