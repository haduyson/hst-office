# SPDX-License-Identifier: AGPL-3.0-only
"""Windows: a crash the office's own handler ends with exit(255) leaves no Windows event; the handler's fault note
(patch hst-windows-silent-crash-note) makes the next start report it as a crash instead of "not closed"."""
import os
import tempfile
import unittest

import _paths  # noqa: F401
from hst_office import crash_signature as sig
from hst_office import windows_fault_note
from hst_office import diag_crash, diag_log
from hst_office.error_report_info import skia_in_use

NOTE = "code=0xC0000005 module=vclplug_winlo.dll offset=0x4A10 thread=7\nend=exit255\n"


class FaultNoteTests(unittest.TestCase):
    def test_note_of_a_crash_the_office_ended_silently(self):
        self.assertEqual(windows_fault_note.signature(NOTE),
                         "Exception c0000005 (access violation) in vclplug_winlo.dll at offset 0x4a10; the office's "
                         "crash handler ended the process (exit code 255), so Windows recorded nothing")
        handled = windows_fault_note.signature("code=0xE06D7363 module=C:\\Users\\x\\mergedlo.dll offset=0x10 thread=1\n")
        self.assertEqual(handled, "Exception e06d7363 (C++ exception) in mergedlo.dll at offset 0x10")
        self.assertEqual(windows_fault_note.signature(""), "")
        self.assertEqual(windows_fault_note.signature("end=exit255\n"), "")

    def test_frames_of_the_faulting_thread_follow_the_fault(self):
        note = ("code=0xC0000005 module=mergedlo.dll offset=0x7E8F7F thread=16800\n"
                "frame module=mergedlo.dll offset=0x7E8F7F\nframe module=sclo.dll offset=0x1A2B3C\n"
                "frame module=mergedlo.dll offset=0x10\nframes=cut\n")
        self.assertEqual(windows_fault_note.signature(note).splitlines(),
                         ["Exception c0000005 (access violation) in mergedlo.dll at offset 0x7e8f7f",
                          "mergedlo.dll +0x7e8f7f", "sclo.dll +0x1a2b3c", "mergedlo.dll +0x10"])

    def test_the_note_adds_the_real_fault_to_the_office_raised_event(self):
        event = "Exception 00000000 in KERNELBASE.dll 10.0.26100.9974 at offset 00000000000c569a (soffice 1.0.2)"
        note = windows_fault_note.signature("code=0xC0000005 module=python313.dll offset=0x1D2F4A thread=1\n")
        self.assertEqual(windows_fault_note.combined(event, note), event + "; first fault: " + note)
        self.assertEqual(windows_fault_note.combined(event, ""), event)
        self.assertEqual(windows_fault_note.combined("", note), note)


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
        path = os.path.join(self.folder.name, windows_fault_note.NAME)
        with open(path, "w", encoding="utf-8") as handle:
            handle.write(NOTE)
        os.utime(path, (1000, 1000))
        self.assertEqual(diag_crash.previous_session("Windows", marker={"started": 5000})["ended"], "not closed")
        self.assertEqual(diag_crash.previous_session("Windows", marker={"started": 1000})["ended"], "crash")


class SkiaInUseTests(unittest.TestCase):
    """A Skia crash at start-up makes the office fall back to raster by itself: the report shows what really draws."""

    def test_vulkan_and_raster_logs(self):
        vulkan = ("RenderMethod: vulkan\nVendor: 0x10de\nDevice: 0x1f99\nAPI: 1.3.280\nDriver: 566.36\n"
                  "DeviceType: discrete\nDeviceName: NVIDIA GeForce GTX 1650\nDenylisted: no\n")
        self.assertEqual(skia_in_use(vulkan), "; in use: vulkan (NVIDIA GeForce GTX 1650, driver 566.36, denylisted no)")
        self.assertEqual(skia_in_use("RenderMethod: raster\nCompiler: clang\n"), "; in use: raster")
        self.assertEqual(skia_in_use(""), "")


if __name__ == "__main__":
    unittest.main()
