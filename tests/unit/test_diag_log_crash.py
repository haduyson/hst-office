# SPDX-License-Identifier: AGPL-3.0-only
"""Local diagnostics: log redaction, rotation and tail, session marker, crash signatures, payload size caps."""
import json
import os
import tempfile
import unittest

import _paths  # noqa: F401
from hst_office import crash_signature as sig
from hst_office import diag_crash, diag_log
from hst_office import error_report_filter as flt
from hst_office import error_report_payload as p

SECRETS = flt.personal_strings({"HOME": "/home/nguyenvana", "USER": "nguyenvana"})
LINUX_STDERR = """(soffice:4242): Gtk-WARNING **: 15:48:40: something harmless
Fatal Python error: Segmentation fault
Fatal Python error: Aborted
Fatal exception: Signal 6
Stack:
#0 /opt/hst-office1.0/program/libuno_sal.so.3(_ZN3sal13backtrace_getEj+0x30) [0x7f1c2b238880]
#1 /opt/hst-office1.0/program/libuno_sal.so.3(+0x462c5) [0x7f1c2b2442c5]
#2 /lib/x86_64-linux-gnu/libc.so.6(+0x45330) [0x7f1c2a845330]
#3 /lib/x86_64-linux-gnu/libc.so.6(pthread_kill+0x11c) [0x7f1c2a89ec0c]
#4 /lib/x86_64-linux-gnu/libc.so.6(abort+0xdf) [0x7f1c2a8288ff]
#5 /opt/hst-office1.0/program/libmergedlo.so(+0x16a268f) [0x7f1c2c2a268f]
#6 /opt/hst-office1.0/program/libuno_sal.so.3(+0x46456) [0x7f1c2b244456]
#7 /lib/x86_64-linux-gnu/libc.so.6(+0x45330) [0x7f1c2a845330]
#8 /lib/x86_64-linux-gnu/libc.so.6(gsignal+0x1e) [0x7f1c2a84527e]
#9 /lib/x86_64-linux-gnu/libc.so.6(+0x45330) [0x7f1c2a845330]
#10 /opt/hst-office1.0/program/libswlo.so(_ZN7SwFrame5PaintEv+0x1f) [0x7f1c2e1f001f]
#11 /opt/hst-office1.0/program/libmergedlo.so(+0x2a1b3c4) [0x7f1c2d61b3c4]
"""


class LogTests(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        diag_log.configure(self.folder.name, SECRETS)

    def tearDown(self):
        diag_log.configure(None)
        self.folder.cleanup()

    def read(self, name=diag_log.LOG_NAME):
        with open(os.path.join(self.folder.name, name), encoding="utf-8") as handle:
            return handle.read()

    def test_entries_are_filtered_before_they_reach_the_disk(self):
        diag_log.warning("command", "Không mở được /home/nguyenvana/Tài liệu/Báo cáo.docx (file:///tmp/x.odt)")
        try:
            raise OSError("cannot write C:\\Users\\nguyenvana\\Desktop\\so lieu.xlsx")
        except OSError:
            diag_log.exception("save_format_check", print_too=False)
        text = self.read()
        for personal in ("nguyenvana", "Báo cáo", "so lieu", "Tài liệu", "file:"):
            self.assertNotIn(personal, text)
        self.assertRegex(text, r"^\d{4}-\d\d-\d\dT\d\d:\d\d:\d\dZ WARNING command: ")
        self.assertIn("ERROR save_format_check: OSError: cannot write <PATH>", text)
        self.assertIn("\n  Traceback (most recent call last):", text)  # indented under its entry
        self.assertIn("<PATH>/test_diag_log_crash.py", text)  # module names stay, paths go

    def test_rotation_keeps_two_files_of_at_most_one_megabyte(self):
        old = diag_log.MAX_BYTES
        diag_log.MAX_BYTES = 2000
        try:
            for number in range(200):
                diag_log.info("test", "entry %03d %s" % (number, "x" * 40))
        finally:
            diag_log.MAX_BYTES = old
        current, previous = self.read(), self.read(diag_log.LOG_NAME + ".1")
        self.assertLessEqual(len(current.encode()), 2000)
        self.assertLessEqual(len(previous.encode()), 2000)
        self.assertIn("entry 199", current)
        self.assertNotIn("entry 000", current + previous)  # older megabytes are gone
        self.assertEqual(sorted(os.listdir(self.folder.name)), [diag_log.LOG_NAME, diag_log.LOG_NAME + ".1"])

    def test_recent_reads_across_the_rotated_file_within_the_limits(self):
        old = diag_log.MAX_BYTES
        diag_log.MAX_BYTES = 3000
        try:
            for number in range(100):
                diag_log.info("test", "entry %03d" % number)
        finally:
            diag_log.MAX_BYTES = old
        text = diag_log.recent(60, 10 * 1024)
        lines = text.splitlines()
        self.assertEqual(len(lines), 60)
        self.assertTrue(lines[-1].endswith("entry 099"))
        self.assertLessEqual(len(diag_log.recent(500, 1000).encode()), 1000)

    def test_logging_never_raises(self):
        diag_log.configure(os.path.join(self.folder.name, "file"), SECRETS)
        with open(os.path.join(self.folder.name, "file"), "w"):
            pass  # the log directory is a file: nothing can be written
        diag_log.error("test", "lost")
        self.assertEqual(diag_log.recent(10, 1000), "")


class SignatureTests(unittest.TestCase):
    def test_linux_fatal_signal_block_becomes_module_offsets(self):
        text = sig.from_linux_stderr(LINUX_STDERR)
        self.assertEqual(text.splitlines(), ["Fatal signal: Segmentation fault", "Office handler: Signal 6 (SIGABRT)",
                                             "  libswlo.so _ZN7SwFrame5PaintEv+0x1f", "  libmergedlo.so +0x2a1b3c4"])
        self.assertNotIn("0x7f1c", text)  # absolute addresses differ at every start
        self.assertNotIn("/opt/", text)
        self.assertEqual(sig.crash_frames(["a.so +0x1", "b.so +0x2"]), ["a.so +0x1", "b.so +0x2"])  # no trampoline
        self.assertEqual(sig.from_linux_stderr("Gtk-WARNING only\n"), "")

    def test_macos_ips_faulting_thread(self):
        body = {"exception": {"type": "EXC_BAD_ACCESS", "signal": "SIGSEGV"}, "faultingThread": 1,
                "usedImages": [{"name": "libmergedlo.dylib"}, {"path": "/usr/lib/system/libsystem_c.dylib"}],
                "threads": [{"frames": []}, {"frames": [{"imageIndex": 0, "imageOffset": 4096, "symbol": "Foo::bar"},
                                                        {"imageIndex": 1, "imageOffset": 16}]}]}
        text = sig.from_ips('{"app_name":"soffice"}\n' + json.dumps(body))
        self.assertEqual(text.splitlines(), ["EXC_BAD_ACCESS (SIGSEGV)", "  libmergedlo.dylib +0x1000 Foo::bar",
                                             "  libsystem_c.dylib +0x10"])
        self.assertEqual(sig.from_ips("not a report"), "")

    def test_windows_application_error_event(self):
        event = ("<Event xmlns='http://schemas.microsoft.com/win/2004/08/events/event'><System>"
                 "<TimeCreated SystemTime='2026-11-10T08:00:00.000Z'/></System><EventData>"
                 "<Data Name='AppName'>soffice.bin</Data><Data Name='AppVersion'>26.8.1.1</Data>"
                 "<Data Name='AppTimeStamp'>0</Data><Data Name='ModuleName'>mergedlo.dll</Data>"
                 "<Data Name='ModuleVersion'>26.8.1.1</Data><Data Name='ModuleTimeStamp'>0</Data>"
                 "<Data Name='ExceptionCode'>c0000005</Data><Data Name='FaultingOffset'>00000000012a3b4c</Data>"
                 "</EventData></Event>")
        self.assertEqual(sig.from_event_xml(event),
                         "Exception c0000005 in mergedlo.dll 26.8.1.1 at offset 00000000012a3b4c (soffice 26.8.1.1)")
        self.assertEqual(sig.from_event_xml(event.replace("soffice.bin", "explorer.exe")), "")

        Done = type("Done", (), {"stdout": event})
        since = sig.event_time(event)
        self.assertEqual(sig.from_windows_events(since, run=lambda *a, **k: Done()).split(" in ")[1][:12], "mergedlo.dll")
        self.assertEqual(sig.from_windows_events(since + 3600, run=lambda *a, **k: Done()), "")  # an older crash


class SessionTests(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        diag_log.configure(self.folder.name, SECRETS)

    def tearDown(self):
        diag_log.configure(None)
        self.folder.cleanup()

    def test_marker_left_means_the_session_did_not_close(self):
        self.assertIsNone(diag_crash.previous_session("Linux", marker={}))
        found = diag_crash.previous_session("Linux", marker={"started": 1, "version": "1.0.1"},
                                            stderr_text=LINUX_STDERR)
        self.assertEqual(found["ended"], "crash")
        facts = "\n".join(diag_crash.facts(found))
        self.assertIn("Session marker: previous session crash (version 1.0.1)", facts)
        self.assertIn("libmergedlo.so +0x2a1b3c4", facts)
        killed = diag_crash.previous_session("Linux", marker={"started": 1}, stderr_text="")
        self.assertEqual(killed["ended"], "not closed")
        self.assertIn("Crash signature: none recorded", "\n".join(diag_crash.facts(killed)))

    def test_stderr_is_kept_for_terminals_pipes_and_headless_runs(self):
        read, write = os.pipe()
        cmdline = os.path.join(self.folder.name, "cmdline")
        with open(cmdline, "wb") as handle:
            handle.write(b"soffice.bin\0--headless\0--convert-to\0pdf\0")
        with open(os.path.join(self.folder.name, "err"), "w") as plain:
            self.assertTrue(diag_crash.keep_stderr(write, cmdline))  # a script reads the pipe
            self.assertTrue(diag_crash.keep_stderr(plain.fileno(), cmdline))  # a conversion run
            self.assertFalse(diag_crash.keep_stderr(plain.fileno(), cmdline + ".missing"))  # desktop start
        os.close(read), os.close(write)

    def test_stop_removes_the_marker_and_logs_the_exit(self):
        path = os.path.join(self.folder.name, diag_crash.MARKER)
        with open(path, "w", encoding="utf-8") as handle:
            json.dump({"started": 1}, handle)
        diag_crash.stop()
        self.assertFalse(os.path.exists(path))
        self.assertIsNone(diag_crash.previous_session("Linux"))
        self.assertIn("INFO session: exit", diag_log.recent(5, 1000))


class PayloadTests(unittest.TestCase):
    def test_crash_report_carries_system_info_log_and_signature_within_the_limits(self):
        found = diag_crash.previous_session("Linux", marker={"started": 1}, stderr_text=LINUX_STDERR)
        crash = "\n".join(["Previous session: ended abnormally"] + diag_crash.facts(found))
        log = "\n".join("2026-11-10T08:00:00Z ERROR dispatch: line %d %s" % (n, "é" * 300) for n in range(2000))
        payload = p.build_payload(p.new_report_id(), "crash", p.utc_now(),
                                  {"version": "1.0.1", "build": "680", "engine": "26.8.1.1"},
                                  {"family": "linux", "version": "Linux Mint 22.3, kernel 7.0.0-42", "arch": "x86_64"},
                                  "vi-VN", "writer", diagnostics={"systemInfo": "Version: 1.0.1 (x86_64)\nVCL: gtk3",
                                                                  "crash": crash, "log": log})
        self.assertEqual(p.schema_errors(payload), [])
        diagnostics = payload["diagnostics"]
        self.assertEqual(set(diagnostics), {"systemInfo", "crash", "log"})
        self.assertIn("Fatal signal: Segmentation fault", diagnostics["crash"])
        self.assertLessEqual(p.utf8_len(diagnostics["log"]), p.LIMITS["log"])
        self.assertTrue(diagnostics["log"].endswith("line 1999 " + "é" * 300))  # the log keeps its end
        self.assertLessEqual(len(p.encode(payload)), p.MAX_BODY)


if __name__ == "__main__":
    unittest.main()
