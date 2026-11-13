# SPDX-License-Identifier: AGPL-3.0-only
"""Windows: a crash the office's own handler ends with exit(255) leaves no Windows event; the handler's fault note
(patch hst-windows-silent-crash-note) makes the next start report it as a crash instead of "not closed"."""
import os
import tempfile
import unittest

import _paths  # noqa: F401
from hst_office import crash_signature as sig
from hst_office import diag_crash, diag_log

NOTE = "code=0xC0000005 module=vclplug_winlo.dll offset=0x4A10 thread=7\nend=exit255\n"


class FaultNoteTests(unittest.TestCase):
    def test_note_of_a_crash_the_office_ended_silently(self):
        self.assertEqual(sig.from_fault_note(NOTE),
                         "Exception c0000005 (access violation) in vclplug_winlo.dll at offset 0x4a10; the office's "
                         "crash handler ended the process (exit code 255), so Windows recorded nothing")
        handled = sig.from_fault_note("code=0xE06D7363 module=C:\\Users\\x\\mergedlo.dll offset=0x10 thread=1\n")
        self.assertEqual(handled, "Exception e06d7363 (C++ exception) in mergedlo.dll at offset 0x10")
        self.assertEqual(sig.from_fault_note(""), "")
        self.assertEqual(sig.from_fault_note("end=exit255\n"), "")


class PreviousSessionTests(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        diag_log.configure(self.folder.name, ())
        self.reader = sig.from_windows_events
        sig.from_windows_events = lambda since, run=None: ""  # Windows recorded nothing

    def tearDown(self):
        sig.from_windows_events = self.reader
        diag_log.configure(None)
        self.folder.cleanup()

    def test_silent_crash_is_a_crash_not_a_session_left_open(self):
        found = diag_crash.previous_session("Windows", marker={"started": 1, "version": "1.0.2"}, note_text=NOTE)
        self.assertEqual(found["ended"], "crash")
        self.assertIn("vclplug_winlo.dll at offset 0x4a10", "\n".join(diag_crash.facts(found)))
        killed = diag_crash.previous_session("Windows", marker={"started": 1}, note_text="")
        self.assertEqual(killed["ended"], "not closed")

    def test_only_a_note_written_after_the_session_started_counts(self):
        path = os.path.join(self.folder.name, diag_crash.FAULT_NOTE)
        with open(path, "w", encoding="utf-8") as handle:
            handle.write(NOTE)
        os.utime(path, (1000, 1000))
        self.assertEqual(diag_crash.previous_session("Windows", marker={"started": 5000})["ended"], "not closed")
        self.assertEqual(diag_crash.previous_session("Windows", marker={"started": 1000})["ended"], "crash")


if __name__ == "__main__":
    unittest.main()
