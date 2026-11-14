# SPDX-License-Identifier: AGPL-3.0-only
"""Windows crash and hang events count only for the session's own soffice.bin.

Every LibreOffice-based suite runs a process named soffice.bin. The reader matched events by that name and time only,
so a crash of another office on the same PC (LibreOffice, a second HST Office) while an HST Office session was open
was reported as that session's crash. Seen on a shared test PC (report 12 probes): a hung HST Office force-ended
without any event of its own was reported as "crash" with another install's Application Error. The session marker
holds the soffice.bin process id; Application Error (1000) and Application Hang (1002) carry it.
"""
import sys
import types
import unittest

import _paths  # noqa: F401

class _StubModule(types.ModuleType):
    def __getattr__(self, name):
        if name.startswith("__"):
            raise AttributeError(name)
        value = type(name, (), {})
        setattr(self, name, value)
        return value


for _name in ("uno", "unohelper", "com", "com.sun", "com.sun.star", "com.sun.star.lang", "com.sun.star.task",
              "com.sun.star.awt"):
    sys.modules.setdefault(_name, _StubModule(_name))

from hst_office import crash_signature as sig  # noqa: E402
from hst_office import diag_crash  # noqa: E402

HEAD = "<Event xmlns='http://schemas.microsoft.com/win/2004/08/events/event'><System>"
CRASH_NAMED = (HEAD + "<Provider Name='Application Error'/><EventID>1000</EventID>"
               "<TimeCreated SystemTime='2026-11-14T10:00:46.000Z'/></System><EventData>"
               "<Data Name='AppName'>soffice.bin</Data><Data Name='AppVersion'>26.8.1.1</Data>"
               "<Data Name='AppTimeStamp'>0</Data><Data Name='ModuleName'>unknown</Data>"
               "<Data Name='ModuleVersion'>0.0.0.0</Data><Data Name='ModuleTimeStamp'>0</Data>"
               "<Data Name='ExceptionCode'>c0000005</Data><Data Name='FaultingOffset'>0000000000000000</Data>"
               "<Data Name='ProcessId'>0x3618</Data><Data Name='ProcessCreationTime'>0x1dd741ed512e0a9</Data>"
               "</EventData></Event>")
# the same event as older Windows builds log it: unnamed data in the fixed order
CRASH_UNNAMED = (HEAD + "<EventID>1000</EventID><TimeCreated SystemTime='2026-11-14T10:00:46.000Z'/></System><EventData>"
                 "<Data>soffice.bin</Data><Data>26.8.1.1</Data><Data>0</Data><Data>unknown</Data><Data>0.0.0.0</Data>"
                 "<Data>0</Data><Data>c0000005</Data><Data>0000000000000000</Data><Data>3618</Data></EventData></Event>")
HANG = (HEAD + "<Provider Name='Application Hang'/><EventID>1002</EventID>"
        "<TimeCreated SystemTime='2026-11-14T10:00:46.000Z'/></System><EventData>"
        "<Data>soffice.bin</Data><Data>1.0.1.10000</Data><Data>3618</Data><Data>01dd741ed512e0a9</Data><Data>19</Data>"
        "<Data>C:\\Program Files\\Other\\soffice.bin</Data><Data>id</Data><Data></Data><Data></Data>"
        "<Data>Top level window is idle</Data></EventData></Event>")
HANG_REPORT = (HEAD + "<Provider Name='Windows Error Reporting'/><EventID>1001</EventID>"
               "<TimeCreated SystemTime='2026-11-14T10:00:46.000Z'/></System><EventData>"
               "<Data Name='EventName'>AppHangB1</Data><Data Name='P1'>soffice.bin</Data>"
               "<Data Name='P2'>26.8.1.1</Data></EventData></Event>")
OURS, OTHER = 0x3618, 0x1d54
SINCE = sig.event_time(CRASH_NAMED) - 30


def run_with(*events):
    done = type("Done", (), {"stdout": "".join(events)})
    return lambda *args, **kwargs: done


class OwnProcessTests(unittest.TestCase):
    def test_application_error_of_another_process_is_not_ours(self):
        for event in (CRASH_NAMED, CRASH_UNNAMED):
            self.assertIn("c0000005", sig.from_event_xml(event, OURS))
            self.assertEqual(sig.from_event_xml(event, OTHER), "")
            self.assertEqual(sig.from_windows_events(SINCE, run=run_with(event), pid=OTHER), "")
            self.assertIn("c0000005", sig.from_windows_events(SINCE, run=run_with(event), pid=OURS))

    def test_newest_foreign_crash_does_not_hide_our_own(self):
        foreign = CRASH_NAMED.replace("0x3618", "0x1d54").replace("c0000005", "c0000409")
        found = sig.from_windows_events(SINCE, run=run_with(foreign, CRASH_NAMED), pid=OURS)
        self.assertIn("c0000005", found)

    def test_hang_events_of_another_process_are_not_ours(self):
        self.assertIsNotNone(sig.windows_hang(SINCE, run=run_with(HANG), pid=OURS))
        self.assertIsNone(sig.windows_hang(SINCE, run=run_with(HANG), pid=OTHER))
        self.assertIsNone(sig.windows_hang(SINCE, run=run_with(HANG_REPORT), pid=OURS))  # names no process

    def test_without_a_pid_nothing_is_filtered(self):
        self.assertIn("c0000005", sig.from_event_xml(CRASH_NAMED))
        self.assertIsNotNone(sig.windows_hang(SINCE, run=run_with(HANG_REPORT)))
        self.assertFalse(sig.same_process({"ProcessId": "not hex"}, OURS))

    def test_previous_session_passes_the_marker_pid(self):
        seen = []
        saved = sig.from_windows_events, sig.windows_hang
        sig.from_windows_events = lambda since, pid=None: seen.append(("crash", pid)) or ""
        sig.windows_hang = lambda since, pid=None: seen.append(("hang", pid))
        try:
            ended = diag_crash.previous_session("Windows", {"started": SINCE, "pid": OTHER}, note_text="")
        finally:
            sig.from_windows_events, sig.windows_hang = saved
        self.assertEqual(seen, [("crash", OTHER), ("hang", OTHER)])
        self.assertEqual(ended["ended"], "not closed")


if __name__ == "__main__":
    unittest.main()
