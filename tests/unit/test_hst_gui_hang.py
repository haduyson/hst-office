# SPDX-License-Identifier: AGPL-3.0-only
"""GUI check hang watchdog: the gtk3 clipboard deadlock is recognised from all-thread gdb stacks (trimmed from a real
stalled check-nd30-insertion-point run under CPU load), other waits are not, and a hang leaves stacks and a FAIL line
instead of a silent stall."""
import io
import os
import sys
import tempfile
import unittest
from contextlib import redirect_stdout

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "runtime"))
import hst_gui_hang  # noqa: E402

REQUEST_THREAD = """Thread 3 (Thread 0x7397173436c0 (LWP 3889533) "cppu_threadpool"):
#1  0x000073978fc5fb4e in ??? () at /lib/x86_64-linux-gnu/libglib-2.0.so.0
#2  0x000073978fc00ff7 in g_main_loop_run () at /lib/x86_64-linux-gnu/libglib-2.0.so.0
#3  0x000073978b196d2e in gtk_clipboard_wait_for_contents () at /lib/x86_64-linux-gnu/libgtk-3.so.0
#4  0x000073978b19a7e1 in gtk_clipboard_wait_for_targets () at /lib/x86_64-linux-gnu/libgtk-3.so.0
#12 0x000073972e15a547 in SwView::IsPasteAllowed() () at program/libswlo.so
#13 0x000073972e09c0db in SwBaseShell::StateClpbrd(SfxItemSet&) () at program/libswlo.so
#22 0x0000739794a12c3d in VclBuilder::makeObject(...) () at program/libmergedlo.so
"""
MAIN_WAITING = """Thread 1 (Thread 0x73978b83de00 (LWP 3859121) "soffice.bin"):
#0  0x00007397913274ed in syscall () at /lib/x86_64-linux-gnu/libc.so.6
#1  0x000073978fc597ad in g_cond_wait () at /lib/x86_64-linux-gnu/libglib-2.0.so.0
#4  0x000073978fbffad3 in g_main_context_iteration () at /lib/x86_64-linux-gnu/libglib-2.0.so.0
#6  0x0000739794d51682 in Application::Yield() () at program/libmergedlo.so
"""
MAIN_POLLING = """Thread 1 (Thread 0x73978b83de00 (LWP 3859121) "soffice.bin"):
#0  0x00007397913274ed in poll () at /lib/x86_64-linux-gnu/libc.so.6
#4  0x000073978fbffad3 in g_main_context_iteration () at /lib/x86_64-linux-gnu/libglib-2.0.so.0
"""


class _Office:
    def __init__(self, workdir):
        self.workdir, self.pid, self.proc = workdir, None, None


class ClassifyTest(unittest.TestCase):
    def test_off_main_clipboard_query_with_main_thread_waiting_is_the_deadlock(self):
        self.assertEqual(hst_gui_hang.classify(REQUEST_THREAD + "\n" + MAIN_WAITING), hst_gui_hang.GTK_CLIPBOARD)

    def test_main_thread_still_polling_is_not_the_deadlock(self):
        self.assertIsNone(hst_gui_hang.classify(REQUEST_THREAD + "\n" + MAIN_POLLING))

    def test_clipboard_query_on_the_main_thread_is_not_the_deadlock(self):
        main_query = MAIN_WAITING + "#7  gtk_clipboard_wait_for_targets ()\n"
        self.assertIsNone(hst_gui_hang.classify(main_query))

    def test_no_stacks(self):
        self.assertIsNone(hst_gui_hang.classify("no gdb dump: FileNotFoundError()\n"))


class ReportTest(unittest.TestCase):
    def test_hang_leaves_stacks_and_a_fail_line(self):
        with tempfile.TemporaryDirectory() as out:
            watch = hst_gui_hang.HangWatch(_Office(os.path.join(out, "office")), out, idle=7)
            watch.beat("table_cell: opening its document")
            printed = io.StringIO()
            with redirect_stdout(printed):
                watch._report()
            self.assertIn("FAIL  no progress for 7 s after: table_cell: opening its document", printed.getvalue())
            self.assertTrue(printed.getvalue().rstrip().endswith("FAIL"))
            with open(os.path.join(out, "hang-python.txt"), encoding="utf-8") as log:
                self.assertIn("test_hang_leaves_stacks_and_a_fail_line", log.read())
            self.assertTrue(os.path.exists(os.path.join(out, "hang-gdb.txt")))

    def test_progress_keeps_the_watchdog_quiet(self):
        watch = hst_gui_hang.HangWatch(_Office("/nonexistent"), "/nonexistent", idle=60)
        watch.last = 0
        watch.beat()
        self.assertLess(hst_gui_hang.time.time() - watch.last, 5)
        self.assertEqual(watch.what, "start")


if __name__ == "__main__":
    unittest.main()
