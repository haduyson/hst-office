# SPDX-License-Identifier: AGPL-3.0-only
"""A shut down, restart or log off is not a crash (patch hst-session-end-note, session_end.py).

Measured on 1.0.1 and rc/1.0.2-batch5: the next start after systemd's SIGTERM (Linux) or after Windows ended the office
during WM_QUERYENDSESSION / after WM_ENDSESSION asked "Lần trước HST Office bị đóng đột ngột. Gửi thông tin…", exactly as
after a kill. The office now leaves a note; the next start reads it and asks nothing (recovery is unchanged)."""
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
from hst_office import diag_crash, diag_log, session_end  # noqa: E402
from hst_office import error_report_crash as crash  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
PATCH = os.path.join(ROOT, "patches", "libreoffice", "hst-session-end-note.patch")
SEGV = "\n\nFatal exception: Signal 11\nStack:\n#0 /opt/hst/program/libuno_sal.so.3(+0x4a1b2) [0x7f]\n"


class NoteTests(unittest.TestCase):
    def test_linux_sigterm_is_a_session_end(self):
        self.assertIn("SIGTERM", session_end.from_linux_stderr("gtk warning\n\n\nTerminated: Signal 15\n"))
        self.assertEqual(session_end.from_linux_stderr(SEGV), "")
        self.assertEqual(session_end.from_linux_stderr(""), "")
        self.assertEqual(session_end.from_linux_stderr(None), "")

    def test_windows_query_end_and_cancel(self):
        self.assertIn("WM_ENDSESSION", session_end.from_windows_note("session-end=query\nsession-end=end\n"))
        self.assertIn("WM_QUERYENDSESSION", session_end.from_windows_note("session-end=query\n"))
        self.assertEqual(session_end.from_windows_note("session-end=query\nsession-end=cancel\n"), "")
        again = "session-end=query\nsession-end=cancel\nsession-end=query\n"
        self.assertIn("WM_QUERYENDSESSION", session_end.from_windows_note(again))
        self.assertEqual(session_end.from_windows_note("code=0xC0000005 module=a.dll offset=0x1 thread=1\n"), "")


class PreviousSessionTests(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        diag_log.configure(self.folder.name, ())
        self.saved = sig.from_windows_events, sig.windows_hang
        sig.from_windows_events = lambda since, run=None: ""
        sig.windows_hang = lambda since, run=None: None

    def tearDown(self):
        sig.from_windows_events, sig.windows_hang = self.saved
        diag_log.configure(None)
        self.folder.cleanup()

    def test_session_end_versus_kill_versus_crash(self):
        marker = {"started": 1, "version": "1.0.2"}
        linux = diag_crash.previous_session("Linux", marker=marker, stderr_text="\n\nTerminated: Signal 15\n")
        self.assertEqual(linux["ended"], "session end")
        self.assertIn("the system ended the session", "\n".join(diag_crash.facts(linux)))
        self.assertEqual(diag_crash.previous_session("Linux", marker=marker, stderr_text="")["ended"], "not closed")
        self.assertEqual(diag_crash.previous_session("Linux", marker=marker, stderr_text=SEGV + "Terminated: Signal 15\n")
                         ["ended"], "crash")
        windows = diag_crash.previous_session("Windows", marker=marker, note_text="session-end=query\n")
        self.assertEqual(windows["ended"], "session end")
        fault = "session-end=query\ncode=0xC0000005 module=vcllo.dll offset=0x10 thread=1\nend=exit255\n"
        self.assertEqual(diag_crash.previous_session("Windows", marker=marker, note_text=fault)["ended"], "crash")
        self.assertEqual(diag_crash.previous_session("Windows", marker=marker, note_text="")["ended"], "not closed")


class QuestionTests(unittest.TestCase):
    def setUp(self):
        self.saved = crash.diag_crash.start, crash.environment, crash.recovery_state, crash.ask_enabled
        crash.environment = lambda ctx, frame: None
        crash.ask_enabled = lambda ctx: True
        crash.STATE["pending"] = None

    def tearDown(self):
        crash.diag_crash.start, crash.environment, crash.recovery_state, crash.ask_enabled = self.saved
        crash.STATE["pending"] = None

    def captured(self, ended, modules=("com.sun.star.text.TextDocument",), crashed=False):
        crash.diag_crash.start = lambda ctx, env: {"ended": ended, "started": 1}
        crash.recovery_state = lambda ctx: {"crashed": crashed, "session": False, "modules": list(modules)}
        crash.capture(None)
        return crash.STATE["pending"]

    def test_no_question_after_the_system_ended_the_session(self):
        self.assertIsNone(self.captured("session end"))
        self.assertIsNone(self.captured("session end", modules=()))

    def test_kills_crashes_and_emergency_saves_are_still_asked(self):
        self.assertIsNotNone(self.captured("not closed"))
        self.assertIsNotNone(self.captured("crash"))
        self.assertIsNotNone(self.captured("session end", crashed=True))


class PatchTests(unittest.TestCase):
    def test_patch_is_in_the_series_and_writes_both_notes(self):
        with open(os.path.join(ROOT, "patches", "libreoffice", "series"), encoding="utf-8") as handle:
            self.assertIn("hst-session-end-note.patch", handle.read().split())
        with open(PATCH, encoding="utf-8") as handle:
            text = handle.read()
        self.assertIn('+                    static const char aNote[] = "\\n\\nTerminated: Signal 15\\n";', text)
        self.assertIn('+                ImplHstNoteSessionEnd( "session-end=query\\n" );', text)
        self.assertIn('+            ImplHstNoteSessionEnd( wParam ? "session-end=end\\n" : "session-end=cancel\\n" );', text)
        self.assertIn('GetEnvironmentVariableW( L"HST_FAULT_NOTE"', text)


if __name__ == "__main__":
    unittest.main()
