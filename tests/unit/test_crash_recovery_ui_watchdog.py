# SPDX-License-Identifier: LicenseRef-HST-Proprietary
# Copyright (C) 2026 HASON TECH
"""The crash handler ends even when the recovery UI cannot run (hst-crash-recovery-ui-watchdog.patch).

Owner report (macOS 1.0.2 -> 1.0.3): an office opened while the updater replaced the app bundle loaded a second
libmergedlo, aborted, and its recovery UI faulted on its first instruction inside the signal handler, where every
signal is blocked: 100 % CPU until Force Quit. Checks the lines the patch adds (no LibreOffice tree needed); the build
queue compiles them on Linux and Windows, the Desktop macOS workflow on macOS.
"""
import pathlib
import re
import unittest

from test_crash_handler_bounded_flush import code, series

ROOT = pathlib.Path(__file__).resolve().parents[2]
PATCHES = ROOT / "patches" / "libreoffice"
PATCH = "hst-crash-recovery-ui-watchdog.patch"


def added():
    lines, current = [], None
    for line in (PATCHES / PATCH).read_text(encoding="utf-8").splitlines():
        if line.startswith("+++ "):
            current = line[4:].split("\t")[0].removeprefix("b/")
        elif current == "desktop/source/app/app.cxx" and line.startswith("+") and not line.startswith("+++"):
            lines.append(line[1:])
    return lines


def after_patch():
    """The patched part of app.cxx as the hunks show it (context and added lines, markers removed)."""
    text = (PATCHES / PATCH).read_text(encoding="utf-8").split("+++ b/desktop/source/app/app.cxx", 1)[1]
    return "\n".join(line[1:] for line in text.splitlines() if line[:1] in (" ", "+"))


class Watchdog(unittest.TestCase):
    def setUp(self):
        self.body = code(added())
        self.patched = after_patch()

    def test_last_app_cxx_patch_in_series_and_only_app_cxx(self):
        # Its hunks are written against app.cxx as every earlier patch leaves it, so no later patch may touch
        # app.cxx; patches of other files may follow it.
        names = series()
        later = [name for name in names[names.index(PATCH) + 1:]
                 if "+++ b/desktop/source/app/app.cxx" in (PATCHES / name).read_text(encoding="utf-8")]
        self.assertEqual(later, [])
        files = re.findall(r"^\+\+\+ b/(\S+)", (PATCHES / PATCH).read_text(encoding="utf-8"), re.M)
        self.assertEqual(files, ["desktop/source/app/app.cxx"])

    def test_nested_faults_get_their_default_action_and_are_unblocked_on_posix_only(self):
        self.assertIn("for (int nSignal : { SIGSEGV, SIGBUS, SIGILL, SIGFPE })", self.body)
        self.assertIn("aDefault.sa_handler = SIG_DFL;", self.body)
        self.assertIn("pthread_sigmask(SIG_UNBLOCK, &aFaults, nullptr);", self.body)
        self.assertEqual(self.body.count("#if !defined _WIN32 && !defined EMSCRIPTEN"), 3)  # includes, helper, call

    def test_watchdog_starts_before_the_recovery_ui_and_ends_the_process(self):
        start = self.patched.index("        lcl_startRecoveryWatchdog();")
        self.assertLess(self.patched.index("        lcl_makeNestedFaultsFatal();"), start)
        self.assertTrue(self.patched[start:].split("\n", 2)[1].strip().startswith("bRestart = impl_callRecoveryUI("))
        self.assertIn("nBusySeconds >= 60", self.body)
        self.assertIn("std::chrono::minutes(10)", self.body)
        self.assertIn("_exit(EXITHELPER_FATAL_ERROR);", self.body)
        self.assertIn("}).detach();", self.body)
        self.assertIn("GetProcessTimes(", self.body)  # Windows
        self.assertIn("CLOCK_PROCESS_CPUTIME_ID", self.body)  # POSIX

    def test_macos_skips_the_recovery_ui_in_a_replaced_bundle(self):
        self.assertIn("&& !lcl_bundleReplaced()", self.body)
        self.assertIn("_NSGetExecutablePath(aPath, &nSize)", self.body)
        self.assertIn("<key>CFBundleShortVersionString</key>", self.body)
        self.assertIn("HST_VERSION) != 0", self.body)
        self.assertRegex(self.patched, r"\( !Application::IsQuit\(\) +\)\n#if defined MACOSX\n.*\n +&& !lcl_bundleReplaced\(\)\n#endif")


if __name__ == "__main__":
    unittest.main()
