# SPDX-License-Identifier: LicenseRef-HST-Proprietary
# Copyright (C) 2026 HASON TECH
"""A start by other software (headless, invisible, --accept, conversion, COM automation) skips the welcome dialog and the
default-apps question; a person's start keeps every question. The command line is read from sal (osl_getCommandArg)."""
import ctypes
import glob
import sys
import types
import unittest
from unittest import mock

import _paths  # noqa: F401


class _StubModule(types.ModuleType):
    def __getattr__(self, name):
        if name.startswith("__"):
            raise AttributeError(name)
        value = type(name, (), {})
        setattr(self, name, value)
        return value


for _name in ("uno", "unohelper", "com", "com.sun", "com.sun.star", "com.sun.star.awt", "com.sun.star.lang",
              "com.sun.star.task", "com.sun.star.frame"):
    sys.modules.setdefault(_name, _StubModule(_name))

from hst_office import automation_start as auto  # noqa: E402
from hst_office import startup_prompts as sp  # noqa: E402


class Switches(unittest.TestCase):
    def test_automation_starts(self):
        for args in (["--headless"], ["-headless"], ["--invisible"], ["--norestore", "--accept=pipe,name=x;urp;"],
                     ["--accept=socket,host=127.0.0.1,port=2002;urp;"], ["--convert-to", "pdf", "a.docx"],
                     ["--nodefault", "--nologo"], ["--terminate_after_init"], ["--print-to-file", "a.docx"],
                     ["-p", "a.docx"], ["--pt", "Printer", "a.docx"], ["--cat", "a.docx"], ["--script-cat", "a.docm"]):
            self.assertTrue(auto.automated(args), args)

    def test_person_starts(self):
        for args in ([], ["--writer"], ["--calc", "/home/u/bảng tính.xlsx"], ["--norestore"], ["--nologo"],
                     ["-env:UserInstallation=file:///tmp/p"], ["C:\\docs\\-p.docx"], ["-"], ["--show", "a.odp"]):
            self.assertFalse(auto.automated(args), args)

    def test_opt_in_for_the_runtime_checks(self):
        args = lambda: ["--accept=pipe,name=x;urp;"]  # noqa: E731
        self.assertTrue(auto.started_by_automation({}, args))
        self.assertFalse(auto.started_by_automation({auto.INTERACTIVE_ENV: "1"}, args))
        self.assertTrue(auto.started_by_automation({auto.INTERACTIVE_ENV: "0"}, args))

    def test_unreadable_arguments_count_as_a_persons_start(self):
        def boom():
            raise OSError("no sal")
        with mock.patch("traceback.print_exc"):
            self.assertFalse(auto.started_by_automation({}, boom))


def _system_sal():
    for path in glob.glob("/usr/lib/libreoffice/program/libuno_sal.so.3") + glob.glob("/opt/*/program/libuno_sal.so.3"):
        return ctypes.CDLL(path)
    return None


class CommandArgs(unittest.TestCase):
    def test_reads_the_arguments_sal_holds(self):
        sal = _system_sal()
        if sal is None:
            self.skipTest("no LibreOffice sal library on this machine")
        argv = [b"soffice.bin", b"--invisible", "--accept=pipe,name=x;urp;".encode(), "tệp mới.docx".encode()]
        sal.osl_setCommandArgs(len(argv), (ctypes.c_char_p * len(argv))(*argv))
        self.assertEqual(auto.command_args(sal), ["--invisible", "--accept=pipe,name=x;urp;", "tệp mới.docx"])


class StartupPrompts(unittest.TestCase):
    def test_automation_drops_only_the_questions_for_a_person(self):
        steps = [(name, None) for name in sp.ORDER]
        self.assertEqual([name for name, _step in sp.for_automation(steps)],
                         ["mac_move", "profile_repaired", "crash", "update_outcome"])

    def run_job(self, automated):
        ran = []
        welcome_job = types.ModuleType("hst_office.welcome_job")
        welcome_job.run_later = lambda ctx, fn: fn()
        with mock.patch.dict(sys.modules, {"hst_office.welcome_job": welcome_job}), \
                mock.patch.object(sp, "_safe_snapshot", return_value=None), \
                mock.patch.object(sp, "_safe_automated", return_value=automated), \
                mock.patch.object(sp, "steps_for", return_value=[(n, (lambda n=n: ran.append(n))) for n in sp.ORDER]), \
                mock.patch.object(sp, "_update_check", lambda ctx: ran.append("update_check")):
            sp.StartupPromptsJob("ctx").execute(())
        return ran

    def test_launchers_notice_waits_for_a_person(self):
        self.assertIn("mac_launchers", sp.FOR_PERSON)
        steps = [(name, None) for name in ("crash", "mac_launchers", "update_outcome")]
        self.assertEqual([name for name, _step in sp.for_automation(steps)], ["crash", "update_outcome"])

    def test_job_skips_welcome_and_default_apps_for_automation(self):
        self.assertEqual(self.run_job(True), ["mac_move", "profile_repaired", "crash", "update_outcome", "update_check"])

    def test_job_keeps_every_question_for_a_person(self):
        self.assertEqual(self.run_job(False), list(sp.ORDER) + ["update_check"])


if __name__ == "__main__":
    unittest.main()
