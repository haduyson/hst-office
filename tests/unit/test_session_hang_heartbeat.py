# SPDX-License-Identifier: AGPL-3.0-only
"""A session closed while "not responding" reads as a hang, and the heartbeat names what was open.

Report 9 (Windows 10, several .xlsx open): three sessions ended with "previous session not closed", no crash signature,
no emergency save, 0 documents in the recovery list and app "unknown". A frozen office closed by the user or Windows
leaves exactly that: Windows logs "Application Hang" (1002) and a WER AppHangB1 report (1001), never the "Application
Error" (1000) the reader looked for, and the recovery list names modified documents only. The events below are real
ones from HST4 (Windows 11, HST Office 1.0.1, frozen with NtSuspendProcess, reported with WerReportHang), trimmed.
"""
import json
import os
import sys
import tempfile
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
from hst_office import diag_crash, diag_log, session_facts  # noqa: E402
from hst_office import error_report_crash as crash  # noqa: E402
from hst_office import session_heartbeat as heartbeat  # noqa: E402

HANG_1002 = (
    "<Event xmlns='http://schemas.microsoft.com/win/2004/08/events/event'><System><Provider Name='Application Hang'/>"
    "<EventID>1002</EventID><TimeCreated SystemTime='2026-11-13T10:49:40.2614227Z'/></System><EventData>"
    "<Data Name='AppName'>soffice.bin</Data><Data Name='AppVersion'>1.0.1.10000</Data>"
    "<Data Name='ProcessId'>0x3398</Data><Data Name='StartTime'>0x1dd735c78520608</Data>"
    "<Data Name='TerminationTime'>19</Data><Data Name='ExeFileName'>C:\\Users\\nguyenvana\\HST\\soffice.bin</Data>"
    "<Data Name='ReportId'>5450a76b-0399-4fd7-b56e-8e8da736ce55</Data><Data Name='PackageFullName'></Data>"
    "<Data Name='PackageRelativeAppId'></Data><Data Name='HangType'>Top level window is idle</Data>"
    "</EventData></Event>")
HANG_1001 = (
    "<Event xmlns='http://schemas.microsoft.com/win/2004/08/events/event'><System>"
    "<Provider Name='Windows Error Reporting'/><EventID>1001</EventID>"
    "<TimeCreated SystemTime='2026-11-13T10:49:40.2099521Z'/></System><EventData>"
    "<Data Name='Bucket'>1508007756091515583</Data><Data Name='BucketType'>5</Data>"
    "<Data Name='EventName'>AppHangB1</Data><Data Name='Response'>Not available</Data><Data Name='CabId'>0</Data>"
    "<Data Name='P1'>soffice.bin</Data><Data Name='P2'>1.0.1.10000</Data><Data Name='P3'>6af4c3b3</Data>"
    "</EventData></Event>")
CRASH_1001 = HANG_1001.replace("AppHangB1", "APPCRASH")
HANG_TIME = 1794566980  # 2026-11-13T10:49:40Z


def run_with(*events):
    done = type("Done", (), {"stdout": "".join(events)})
    return lambda *a, **k: done()


class HangEventTests(unittest.TestCase):
    def test_real_application_hang_and_wer_hang_report_are_read(self):
        self.assertEqual(sig.from_hang_xml(HANG_1002),
                         "Application Hang (soffice 1.0.1.10000); hang type: Top level window is idle")
        self.assertEqual(sig.from_hang_xml(HANG_1001), "AppHangB1 report for soffice 1.0.1.10000")
        self.assertNotIn("nguyenvana", sig.from_hang_xml(HANG_1002))  # the program path is never copied

    def test_unnamed_data_of_older_systems_follow_the_message_order(self):
        unnamed = HANG_1002
        for name in sig.HANG_FIELDS:
            unnamed = unnamed.replace("<Data Name='%s'>" % name, "<Data>")
        unnamed = unnamed.replace("<Data Name='ExeFileName'>", "<Data>")
        self.assertIn("hang type: Top level window is idle", sig.from_hang_xml(unnamed))

    def test_other_programs_crash_reports_and_older_hangs_are_ignored(self):
        self.assertEqual(sig.from_hang_xml(HANG_1002.replace("soffice.bin", "EXCEL.EXE")), "")
        self.assertEqual(sig.from_hang_xml(CRASH_1001), "")
        self.assertIsNone(sig.windows_hang(HANG_TIME + 3600, run=run_with(HANG_1002)))
        self.assertIsNone(sig.windows_hang(0, run=run_with(CRASH_1001)))
        found = sig.windows_hang(HANG_TIME - 600, run=run_with(HANG_1002, HANG_1001))
        self.assertEqual(found["time"], HANG_TIME)

    def test_no_wevtutil_is_no_hang(self):
        def broken(*a, **k):
            raise OSError("wevtutil")
        self.assertIsNone(sig.windows_hang(0, run=broken))


class SessionTests(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        diag_log.configure(self.folder.name, ())
        diag_crash.STATE["closed"] = False
        self.saved = sig.from_windows_events, sig.windows_hang

    def tearDown(self):
        sig.from_windows_events, sig.windows_hang = self.saved
        diag_crash.STATE["closed"] = False
        diag_log.configure(None)
        self.folder.cleanup()

    def marker(self, **fields):
        path = os.path.join(self.folder.name, diag_crash.MARKER)
        with open(path, "w", encoding="utf-8") as handle:
            json.dump(dict({"started": HANG_TIME - 1200, "pid": 1, "version": "1.0.2"}, **fields), handle)
        return path

    def test_report_9_shape_reads_as_a_hang_with_what_was_open(self):
        self.marker()
        snap = {"apps": ["calc", "calc", "calc"], "active": "calc", "modified": 0, "loading": 1}
        self.assertTrue(diag_crash.update_marker(dict(snap, beat=HANG_TIME - 300)))
        sig.from_windows_events = lambda since, pid=None: ""
        sig.windows_hang = lambda since, pid=None: {"time": HANG_TIME, "text": sig.from_hang_xml(HANG_1002)}
        found = diag_crash.previous_session("Windows")
        self.assertEqual(found["ended"], "hang")
        facts = "\n".join(diag_crash.facts(found))
        self.assertIn("Session marker: previous session hang (version 1.0.2)", facts)
        self.assertIn("Hang: Application Hang (soffice 1.0.1.10000)", facts)
        self.assertIn("Last heartbeat: 2026-11-13T10:44:40Z (900 s after the start)", facts)
        self.assertIn("Not responding for at least 300 s before it was closed (2026-11-13T10:49:40Z)", facts)
        self.assertRegex(facts, r"Documents open at the last heartbeat: 3 \(\S.* 3\); modified: 0; still loading: 1")
        self.assertEqual(session_facts.last_app(found), "calc")

    def test_a_crash_signature_wins_over_a_hang(self):
        self.marker()
        sig.from_windows_events = lambda since, pid=None: "Exception c0000005 in mergedlo.dll"
        sig.windows_hang = lambda since, pid=None: self.fail("hang events are read only without a crash")
        self.assertEqual(diag_crash.previous_session("Windows")["ended"], "crash")

    def test_markers_of_older_versions_have_no_heartbeat(self):
        found = diag_crash.previous_session("Linux", marker={"started": 1, "version": "1.0.1"}, stderr_text="")
        self.assertEqual(found["ended"], "not closed")
        self.assertIn("Last heartbeat: none recorded", "\n".join(diag_crash.facts(found)))
        self.assertEqual(session_facts.last_app(found), "")

    def test_no_beat_rewrites_the_marker_after_a_normal_close(self):
        path = self.marker()
        diag_crash.stop()
        self.assertFalse(os.path.exists(path))
        self.assertFalse(diag_crash.update_marker({"beat": 1}))
        self.assertFalse(os.path.exists(path))

    def test_heartbeat_writes_on_change_and_refreshes_its_time(self):
        heartbeat.STATE.update(seen=None, written=0.0)
        stored = []
        snaps = iter([{"apps": ["calc"], "active": "calc"}] * 2 + [{"apps": ["calc", "writer"], "active": "writer"}])

        def store(fields):
            stored.append(fields)
            return True
        take = lambda ctx: next(snaps)  # noqa: E731
        heartbeat.beat(None, now=100.0, take=take, store=store)
        heartbeat.beat(None, now=110.0, take=take, store=store)  # same documents, within REFRESH: no write
        heartbeat.beat(None, now=115.0, take=take, store=store)  # another document became active: written at once
        self.assertEqual([entry["beat"] for entry in stored], [100.0, 115.0])
        self.assertEqual(stored[-1]["active"], "writer")

    def test_last_app_prefers_the_active_document_then_a_shared_app(self):
        self.assertEqual(session_facts.last_app({"active": "writer", "apps": ["calc"]}), "writer")
        self.assertEqual(session_facts.last_app({"active": "start", "apps": ["calc", "calc"]}), "calc")
        self.assertEqual(session_facts.last_app({"active": "", "apps": ["calc", "writer"]}), "")


class CrashPromptAppTests(unittest.TestCase):
    def test_unchanged_documents_still_name_the_app(self):
        opened = []
        marker = {"ended": "hang", "started": HANG_TIME - 600, "beat": HANG_TIME - 60, "active": "calc",
                  "apps": ["calc"], "modified": 0, "loading": 0, "version": "1.0.2",
                  "hang": {"time": HANG_TIME, "text": sig.from_hang_xml(HANG_1002)}}
        crash.STATE["pending"] = {"crashed": False, "session": False, "modules": [], "session_marker": marker}
        crash.ask(None, frame=type("F", (), {"getContainerWindow": lambda self: None})(),
                  show=lambda ctx, parent: "send", open_report=lambda ctx, frame, kind, text, app: opened.append(
                      (kind, app, text)))
        kind, app, text = opened[0]
        self.assertEqual((kind, app), ("crash", "calc"))
        self.assertIn("Documents in the recovery list (modified) at exit: 0", text)
        self.assertIn("Not responding for at least 60 s", text)
        self.assertIn("Active app: ", text)


if __name__ == "__main__":
    unittest.main()
