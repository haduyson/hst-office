# SPDX-License-Identifier: AGPL-3.0-only
"""The crash handler never waits forever on the configuration (hst-crash-handler-bounded-flush.patch).

Owner report (Windows 1.0.1): a crash while a Writer document closed left the emergency save dialog with an empty
list on screen, and only the Task Manager ended the office. A dump showed Desktop::Exception -> FlushConfiguration
joining configmgr's writer thread, which waited for the configuration lock held by the faulted main thread. Checks
the lines the series leaves in each file (no LibreOffice tree needed); tests/runtime/check-close-crash-handler-windows.py
checks the built office.
"""
import json
import pathlib
import re
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[2]
PATCHES = ROOT / "patches" / "libreoffice"
PATCH = "hst-crash-handler-bounded-flush.patch"


def series():
    return [line.strip() for line in (PATCHES / "series").read_text(encoding="utf-8").splitlines()
            if line.strip() and not line.lstrip().startswith("#")]


def hunks(path):
    """(added, removed) lines of `path` in the new patch."""
    added, removed, current = [], [], None
    for line in (PATCHES / PATCH).read_text(encoding="utf-8").splitlines():
        if line.startswith("+++ "):
            current = line[4:].split("\t")[0].removeprefix("b/")
        elif line.startswith("--- ") or line.startswith("@@"):
            continue
        elif current == path and line.startswith("+"):
            added.append(line[1:])
        elif current == path and line.startswith("-"):
            removed.append(line[1:])
    return added, removed


def code(lines):
    return "\n".join(re.sub(r"//.*$", "", line) for line in lines)


class Series(unittest.TestCase):
    def test_appended_last_and_later_patches_leave_the_files_alone(self):
        names = series()
        self.assertIn(PATCH, names)
        later = names[names.index(PATCH) + 1:]
        files = ("desktop/source/app/app.cxx", "framework/source/services/hstrecoverylist.cxx", "sal/osl/w32/signal.cxx")
        for name in later:
            text = (PATCHES / name).read_text(encoding="utf-8")
            for path in files:
                self.assertNotIn("+++ b/" + path, text, "%s changes %s again" % (name, path))


class DesktopException(unittest.TestCase):
    def setUp(self):
        self.added, self.removed = hunks("desktop/source/app/app.cxx")
        self.body = code(self.added)

    def test_no_recovery_ui_after_quit(self):
        self.assertIn("( !Application::IsQuit()                   )", self.body)

    def test_flush_is_bounded(self):
        self.assertIn("    FlushConfiguration();", self.removed)
        self.assertIn("lcl_flushConfigurationWithin(std::chrono::seconds(5));", self.body)
        self.assertRegex(self.body, r"aDone\.wait_for\(aGuard, aLimit,")
        self.assertIn(").detach();", self.body)
        self.assertIn("->flush();", self.body)


class EmergencySaveFlush(unittest.TestCase):
    def test_hst_recovery_flush_is_bounded_and_skipped_once_stuck(self):
        added, removed = hunks("framework/source/services/hstrecoverylist.cxx")
        body = code(added)
        self.assertIn("static std::atomic<bool> s_bStuck(false);", body)
        self.assertIn("if (s_bStuck)", body)
        self.assertIn("std::chrono::seconds(5)", body)
        self.assertIn("s_bStuck = true;", body)
        self.assertIn(").detach();", body)
        self.assertIn("        uno::Reference<util::XFlushable>(configuration::theDefaultProvider::get(xContext),",
                      removed)


class WindowsSignalHandler(unittest.TestCase):
    def test_kill_path_terminates_without_exit_teardown(self):
        added, removed = hunks("sal/osl/w32/signal.cxx")
        self.assertIn("            exit(255);", removed)
        body = code(added)
        self.assertIn("TerminateProcess(GetCurrentProcess(), 255);", body)
        self.assertNotRegex(body, r"(?<![_\w])exit\(255\)")


class RecoveryDialogTitles(unittest.TestCase):
    def test_titles_show_the_product_name_only(self):
        rows = [json.loads(line) for line in (ROOT / "l10n" / "vi-overrides.jsonl").read_text(encoding="utf-8")
                .splitlines() if line.strip()]
        wanted = {"docrecoverysavedialog|DocRecoverySaveDialog", "docrecoveryrecoverdialog|DocRecoveryRecoverDialog",
                  "docrecoverybrokendialog|DocRecoveryBrokenDialog"}
        titles = {row["msgctxt"]: row["msgstr"] for row in rows if row.get("msgctxt") in wanted}
        self.assertEqual(set(titles), wanted)
        for context, text in titles.items():
            self.assertEqual(text, "Khôi phục tài liệu %PRODUCTNAME", context)


if __name__ == "__main__":
    unittest.main()
