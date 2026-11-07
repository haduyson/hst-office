# SPDX-License-Identifier: AGPL-3.0-only
"""Start-up dispatcher without an office: one modal question per start, in the fixed order, and the default-apps
show-once / snooze rule (ask, "Để sau" again after 14 days, at most 3 times; never once answered or registered)."""
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

from hst_office import default_apps as da  # noqa: E402
from hst_office import startup_prompts as sp  # noqa: E402

DAY = 86400
NOW = 2_000_000_000


class Order(unittest.TestCase):
    def test_order_is_mac_move_crash_welcome_default_apps_update(self):
        self.assertEqual(sp.ORDER, ("mac_move", "crash", "welcome", "default_apps", "update_outcome"))

    def chain(self, due):
        calls = []

        def step(name):
            def run():
                calls.append(name)
                return name in due
            return run
        shown = sp.run(None, [(n, step(n)) for n in sp.ORDER], after=lambda ctx: calls.append("update_check"))
        return shown, calls

    def test_only_the_first_due_prompt_is_shown(self):
        for due in ({"crash", "welcome", "default_apps"}, {"welcome", "default_apps"}, {"default_apps", "update_outcome"}):
            shown, calls = self.chain(due)
            first = next(n for n in sp.ORDER if n in due)
            self.assertEqual(shown, first)
            self.assertEqual(calls, list(sp.ORDER[:sp.ORDER.index(first) + 1]) + ["update_check"], due)

    def test_nothing_due_runs_every_check_and_the_infobar_check(self):
        shown, calls = self.chain(set())
        self.assertIsNone(shown)
        self.assertEqual(calls, list(sp.ORDER) + ["update_check"])

    def test_failing_step_does_not_block_later_ones(self):
        def boom():
            raise RuntimeError("broken prompt")
        with mock.patch("traceback.print_exc"):
            shown = sp.run(None, [("crash", boom), ("welcome", lambda: True)], after=lambda ctx: None)
        self.assertEqual(shown, "welcome")

    def test_failing_update_check_is_swallowed(self):
        def boom(ctx):
            raise RuntimeError("offline")
        with mock.patch("traceback.print_exc"):
            self.assertIsNone(sp.run(None, [], after=boom))

    def test_mac_move_uses_the_stub_until_the_updater_ships_it(self):
        with mock.patch.object(sp.platform, "system", return_value="Darwin"), \
                mock.patch.dict(sys.modules, {"hst_office.mac_app_location": None}):
            self.assertFalse(sp._mac_move(None))
        with mock.patch.object(sp.platform, "system", return_value="Linux"):
            self.assertFalse(sp._mac_move(None))

    def test_mac_move_calls_offer_move_once(self):
        fake = types.ModuleType("hst_office.mac_app_location")
        fake.offer_move_once = mock.Mock(return_value=True)
        with mock.patch.object(sp.platform, "system", return_value="Darwin"), \
                mock.patch.dict(sys.modules, {"hst_office.mac_app_location": fake}):
            self.assertTrue(sp._mac_move("ctx"))
        fake.offer_move_once.assert_called_once_with("ctx")


class Snooze(unittest.TestCase):
    def test_first_time_is_due(self):
        self.assertTrue(da.should_ask(dict(da.DEFAULT_STATE), NOW, False))

    def test_later_waits_fourteen_days(self):
        state = da.after_answer(dict(da.DEFAULT_STATE), False, NOW)
        self.assertEqual((state["Asked"], state["LastAsked"], state["Done"]), (1, NOW, False))
        self.assertFalse(da.should_ask(state, NOW + 14 * DAY - 1, False))
        self.assertTrue(da.should_ask(state, NOW + 14 * DAY, False))

    def test_at_most_three_times(self):
        state, now = dict(da.DEFAULT_STATE), NOW
        asked = 0
        for _ in range(10):
            if da.should_ask(state, now, False):
                asked += 1
                state = da.after_answer(state, False, now)
            now += 15 * DAY
        self.assertEqual(asked, da.MAX_ASKS)

    def test_accepted_registered_or_locked_never_asks(self):
        accepted = da.after_answer(dict(da.DEFAULT_STATE), True, NOW)
        self.assertFalse(da.should_ask(accepted, NOW + 365 * DAY, False))
        self.assertFalse(da.should_ask(dict(da.DEFAULT_STATE), NOW, True))
        self.assertFalse(da.should_ask(dict(da.DEFAULT_STATE, Ask=False), NOW, False))


class StartupStep(unittest.TestCase):
    def setUp(self):
        self.state = dict(da.DEFAULT_STATE)
        self.saved = []
        for target, value in (("load_state", lambda ctx: dict(self.state)),
                              ("save_state", lambda ctx, s: (self.saved.append(s), self.state.update(s))),
                              ("_report", lambda *a, **k: None)):
            patcher = mock.patch.object(da, target, value)
            patcher.start()
            self.addCleanup(patcher.stop)
        self.registered = mock.patch.object(da.osx, "is_registered", return_value=False)
        self.registered.start()
        self.addCleanup(self.registered.stop)

    def test_question_text_is_exact(self):
        self.assertEqual(da.QUESTION, "Mở tài liệu văn phòng bằng HST Office?")
        self.assertEqual((da.ACCEPT, da.LATER), ("Đồng ý", "Để sau"))

    def test_no_vendor_names_in_user_text(self):
        text = " ".join([da.QUESTION, da.TYPES_NOTE, da.DONE_TEXT, da.WINDOWS_TEXT, da.FAILED_TEXT]).lower()
        for name in ("microsoft", "word", "excel", "powerpoint", "libreoffice", "openoffice", "office 365", "apple"):
            self.assertNotIn(name, text)

    def test_later_snoozes_and_shows_one_modal(self):
        act = mock.Mock()
        self.assertTrue(da.offer_at_startup(None, now=NOW, ask=lambda ctx, peer: False, act=act))
        act.assert_not_called()
        self.assertEqual(self.state["Asked"], 1)
        self.assertFalse(da.offer_at_startup(None, now=NOW + DAY, ask=lambda ctx, peer: self.fail("asked twice")))

    def test_agree_runs_the_action_once_and_ends_the_question(self):
        act = mock.Mock(return_value=(True, ""))
        self.assertTrue(da.offer_at_startup(None, now=NOW, ask=lambda ctx, peer: True, act=act))
        act.assert_called_once()
        self.assertTrue(self.state["Done"])
        self.assertFalse(da.offer_at_startup(None, now=NOW + 99 * DAY, ask=lambda ctx, peer: self.fail("asked again")))

    def test_mac_outside_applications_is_not_asked_and_not_counted(self):
        with mock.patch.object(da.osx, "system", return_value="Darwin"), \
                mock.patch.object(da.osx, "mac_in_applications", return_value=False):
            self.assertFalse(da.offer_at_startup(None, now=NOW, ask=lambda ctx, peer: self.fail("asked")))
        self.assertEqual(self.saved, [])
        with mock.patch.object(da.osx, "system", return_value="Darwin"), \
                mock.patch.object(da.osx, "mac_in_applications", return_value=True):
            self.assertTrue(da.offer_at_startup(None, now=NOW, ask=lambda ctx, peer: False))

    def test_already_registered_is_never_asked(self):
        self.registered.stop()
        with mock.patch.object(da.osx, "is_registered", return_value=True):
            self.assertFalse(da.offer_at_startup(None, now=NOW, ask=lambda ctx, peer: self.fail("asked")))
        self.registered.start()
        self.assertTrue(self.state["Done"])


if __name__ == "__main__":
    unittest.main()
