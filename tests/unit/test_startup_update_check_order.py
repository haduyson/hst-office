# SPDX-License-Identifier: LicenseRef-HST-Proprietary
"""The start-up update check does not wait for an unanswered start-up question (e.g. "Mở tài liệu văn phòng bằng HST
Office?"): it starts before the questions on its worker thread, and prompting() tells its pop-up to wait while they
run, so the two never cover each other."""
import unittest
from unittest import mock

import _paths  # noqa: F401
import test_startup_prompts  # noqa: F401 - installs the UNO module stubs
from hst_office import startup_prompts as sp  # noqa: E402


class UpdateCheckOrder(unittest.TestCase):
    def setUp(self):
        patcher = mock.patch.object(sp, "_update_resume")
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_update_check_starts_before_an_unanswered_question(self):
        """The default-apps question waits for the user: the check is already on its way (not held by the answer)."""
        calls = []

        def default_apps():
            calls.append("default_apps:check-started=%s" % ("update_check" in calls))
            return True
        shown = sp.run(None, [("welcome", lambda: False), ("default_apps", default_apps)],
                       after=lambda ctx: calls.append("update_check"))
        self.assertEqual(shown, "default_apps")
        self.assertEqual(calls, ["update_check", "default_apps:check-started=True"])

    def test_prompting_while_the_questions_run_so_the_update_popup_waits(self):
        seen = []
        sp.run(None, [("welcome", lambda: seen.append(("welcome", sp.prompting())) or True)],
               after=lambda ctx: seen.append(("update_check", sp.prompting())))
        self.assertEqual(seen, [("update_check", True), ("welcome", True)])
        self.assertFalse(sp.prompting())

    def test_prompting_ends_even_when_the_chain_raises(self):
        with mock.patch.object(sp, "run_chain", side_effect=RuntimeError("toolkit gone")):
            with self.assertRaises(RuntimeError):
                sp.run(None, [], after=lambda ctx: None)
        self.assertFalse(sp.prompting())


if __name__ == "__main__":
    unittest.main()
