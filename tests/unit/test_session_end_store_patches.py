# SPDX-License-Identifier: LicenseRef-HST-Proprietary
# Copyright (C) 2026 HASON TECH
"""When the system ends the session the documents are stored for the next start (hst-gnome-end-session-save,
hst-session-end-answer-now, hst-session-end-store).

GNOME/Cinnamon EndSession used to drop every change silently, Windows held the log off with the save question (and the
quit stalled 98-115 s inside WM_QUERYENDSESSION even with nothing unsaved), Linux SIGTERM exited at once. The runtime
checks are tests/runtime/check-session-end-{gnome,linux,windows,windows-answer}.py; these tests pin the order of the
patches and the invariants a later rebase must keep."""
import os
import re
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
PATCHES = os.path.join(ROOT, "patches", "libreoffice")
ORDER = ["hst-session-end-note.patch", "hst-gnome-end-session-save.patch", "hst-session-end-answer-now.patch",
         "hst-session-end-store.patch"]


def read(name):
    with open(os.path.join(PATCHES, name), encoding="utf-8") as handle:
        return handle.read()


def added(text):
    """The code after the patch, as far as its hunks show it (added and context lines)."""
    body = text.split("\n---\n", 1)[1]
    return "\n".join(line[1:] for line in body.splitlines()
                     if line[:1] in ("+", " ") and not line.startswith("+++"))


class SeriesTests(unittest.TestCase):
    def test_patches_are_in_the_series_in_order(self):
        series = read("series").split()
        positions = [series.index(name) for name in ORDER]
        self.assertEqual(positions, sorted(positions))


class GnomeTests(unittest.TestCase):
    def test_end_session_stores_before_answering_and_before_dropping_changes(self):
        code = added(read("hst-gnome-end-session-save.patch"))
        self.assertRegex(code, r"store_session\(\);\s*session_client_response\(client_proxy\);\s*"
                               r"clear_modify_and_terminate\(\);")
        self.assertRegex(code, r"store_session\(\);\s*clear_modify_and_terminate\(\);")  # Stop
        self.assertIn('"doSessionSave"', code)
        self.assertIn('"doSessionQuietQuit"', code)
        self.assertIn("DispatchAsynchron", code)


class WindowsAnswerTests(unittest.TestCase):
    def test_answers_yes_first_only_when_nothing_is_unsaved(self):
        code = added(read("hst-session-end-answer-now.patch"))
        self.assertIn("if ( InSendMessage() && !ImplHstAnyDocumentModified() )\n            ReplyMessage( TRUE );", code)
        # an error while checking counts as unsaved: the path that can ask is kept
        self.assertRegex(code, r"catch \( const css::uno::Exception& \)\s*\{[^}]*return true;")


class StoreTests(unittest.TestCase):
    def setUp(self):
        self.text = read("hst-session-end-store.patch")
        self.code = added(self.text)

    def test_session_end_job_is_the_session_restart_without_the_restart(self):
        self.assertIn("SessionEnd                = 8192", self.code)
        self.assertIn("is_typed_flags<Job, 0x3FFF>", self.code)
        self.assertIn('CMD_DO_SESSION_END = u"/doSessionEnd"_ustr', self.code)
        branch = re.search(r"if \(\(eJob & Job::SessionEnd\) == Job::SessionEnd\)\s*\{(.*?)\n        \}", self.code, re.S)
        self.assertIsNotNone(branch)
        self.assertIn("implts_doSessionRestart(aParams)", branch.group(1))
        self.assertNotIn("requestRestart", branch.group(1))
        self.assertIn("DisableAutorecovery", branch.group(1))

    def test_all_three_system_ends_run_it(self):
        self.assertEqual(self.code.count('vnd.sun.star.autorecovery:/doSessionEnd"_ustr'), 2)  # Windows, SIGTERM
        self.assertIn('dispatch_recovery_job(xContext, u"doSessionEnd"_ustr);', self.code)  # GNOME
        self.assertRegex(self.code, r"ImplHstStoreSession\( hWnd \);\s*bStored = true;\s*\}\s*"
                                    r"if \( !ImplHstAnyDocumentModified\(\) \)\s*ReplyMessage\( TRUE \);")
        # the store disposes the windows of the documents: the application quits directly
        self.assertRegex(self.code, r"if \( !bStored \)\s*nRet = pFrame->CallCallback\( SalEvent::Shutdown, nullptr \);\s*"
                                    r"else if \( GetpApp\(\) && GetpApp\(\)->QueryExit\(\) \)\s*Application::Quit\(\);")
        self.assertIn("ShutdownBlockReasonCreate", self.code)
        self.assertIn("ShutdownBlockReasonDestroy( hWnd );", self.code)

    def test_sigterm_handler_only_signals_and_keeps_the_old_exit_as_fallback(self):
        handler = re.search(r"oslSignalAction onSignal\(.*?\n\}", self.code, re.S).group(0)
        self.assertIn("write(g_aPipe[1], &c, 1)", handler)
        self.assertIn("return osl_Signal_ActIgnore;", handler)
        # systemd and oosplash both send SIGTERM: a repeated one changes nothing, the deadline holds
        self.assertRegex(handler, r"g_bPending\.exchange\(true\)\)[^\n]*\n\s*return osl_Signal_ActIgnore;")
        self.assertIn("TimeValue delay = { 25, 0 };", self.code)  # oosplash outwaits the 20 s deadline
        self.assertNotRegex(handler, r"SAL_|OUString|Reference|PostUserEvent")  # nothing unsafe in a signal handler
        self.assertIn("constexpr auto DEADLINE = std::chrono::seconds(20);", self.code)
        self.assertIn('static const char aNote[] = "\\n\\nTerminated: Signal 15\\n";', self.code)
        self.assertIn("if (!rArgs.IsHeadless() && !rArgs.IsInvisible())", self.code)
        self.assertNotIn("+++ b/desktop/source/app/app.cxx", self.text)  # the crash handler patch owns app.cxx
        self.assertIn("desktop/source/app/hstsessionend \\", self.code)


if __name__ == "__main__":
    unittest.main()
