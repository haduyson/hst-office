# SPDX-License-Identifier: AGPL-3.0-only
"""Start-up answers survive the loss of the extension's configuration values (startup_choices).

configmgr drops the user values of a bundled extension's schema when a start reads registrymodifications.xcu before the
extension's registration cache is complete, so the welcome dialog came back after "Không hiển thị lại". The answers are
now kept in <profile>/user/hst-office/startup-choices.json as well. Without an office: the configuration is a fake node
whose values can be "lost" (reset to the schema defaults)."""
import json
import os
import sys
import tempfile
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
              "com.sun.star.task", "com.sun.star.frame", "com.sun.star.style",
              "com.sun.star.style.VerticalAlignment"):
    sys.modules.setdefault(_name, _StubModule(_name))

from hst_office import default_apps as da  # noqa: E402
from hst_office import error_report_crash as crash  # noqa: E402
from hst_office import startup_choices as sc  # noqa: E402
from hst_office import welcome_job as wj  # noqa: E402

DEFAULTS = {wj.CONFIG_PATH: {"Shown": False},
            da.CONFIG_PATH: dict(da.DEFAULT_STATE),
            crash.SETTINGS: {"AskAfterCrash": True}}


class _Config:
    """The extension's configuration of one profile: nodes of property values, `lose()` drops every user value."""

    def __init__(self, locked=()):
        self.values = {path: dict(props) for path, props in DEFAULTS.items()}
        self.locked = set(locked)

    def lose(self):
        self.values = {path: dict(props) for path, props in DEFAULTS.items()}

    def node(self, path):
        config = self

        class Node:
            def getPropertyValue(self, name):
                return config.values[path][name]

            def setPropertyValue(self, name, value):
                config.values[path][name] = value

            def commitChanges(self):
                pass

            def getPropertySetInfo(self):
                return types.SimpleNamespace(getPropertyByName=lambda name: types.SimpleNamespace(
                    Attributes=sc.READONLY if name in config.locked else 0))
        return Node()


class _Profile(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.mkdtemp(prefix="hst-choices-")
        self.config = _Config()
        access = lambda ctx, writable=False, path=None: self.config.node(path)  # noqa: E731
        patches = [mock.patch.object(sc, "profile_dir", lambda ctx: self.folder),
                   mock.patch.object(wj, "_access", lambda ctx, writable: access(ctx, writable, wj.CONFIG_PATH)),
                   mock.patch.object(da, "_access", lambda ctx, writable: access(ctx, writable, da.CONFIG_PATH)),
                   mock.patch.object(crash, "_node", lambda ctx, path, writable=False: access(ctx, writable, path)),
                   mock.patch.object(crash, "_write", lambda ctx, path, name, value:
                                     access(ctx, True, path).setPropertyValue(name, value))]
        for patch in patches:
            patch.start()
            self.addCleanup(patch.stop)

    def tearDown(self):
        for name in os.listdir(self.folder):
            os.remove(os.path.join(self.folder, name))
        os.rmdir(self.folder)

    def stored(self):
        return sc.read(self.folder)


class StoreFile(_Profile):
    def test_write_merges_and_leaves_no_temporary_file(self):
        self.assertTrue(sc.write(self.folder, welcome_shown=True))
        self.assertTrue(sc.write(self.folder, crash_never_ask=True))
        self.assertEqual(self.stored(), {"welcome_shown": True, "crash_never_ask": True})
        self.assertEqual(os.listdir(self.folder), [sc.FILE_NAME])

    def test_missing_broken_or_oversized_file_reads_as_nothing_stored(self):
        self.assertEqual(sc.read(self.folder), {})
        path = os.path.join(self.folder, sc.FILE_NAME)
        for content in (b"", b"{not json", b"[1, 2]", b'"text"', b" " * (sc.MAX_BYTES + 1)):
            with open(path, "wb") as handle:
                handle.write(content)
            self.assertEqual(sc.read(self.folder), {}, content[:20])
        self.assertTrue(sc.write(self.folder, welcome_shown=True), "a broken file is replaced")
        self.assertEqual(self.stored(), {"welcome_shown": True})

    def test_an_unwritable_profile_loses_the_answer_without_raising(self):
        with mock.patch.object(sc, "atomic_write", side_effect=PermissionError("read-only")), \
                mock.patch.object(sc.diag_log, "exception"):
            self.assertFalse(sc.write(self.folder, welcome_shown=True))
        with mock.patch.object(sc, "profile_dir", side_effect=RuntimeError("no office")), \
                mock.patch.object(sc.diag_log, "exception"):
            self.assertFalse(sc.put(None, "welcome_shown", True))
            self.assertEqual(sc.get(None, "welcome_shown", "default"), "default")


class Welcome(_Profile):
    def test_shown_welcome_stays_hidden_after_the_configuration_value_is_lost(self):
        self.assertFalse(wj.is_shown(None))
        wj.set_shown(None, True)  # the dialog was displayed with "Không hiển thị lại" ticked
        self.assertEqual(self.stored(), {"welcome_shown": True})
        self.config.lose()  # a start without the extension's registration cache dropped Welcome/Shown
        self.assertTrue(wj.is_shown(None))

    def test_answer_of_a_version_without_the_file_is_migrated(self):
        self.config.values[wj.CONFIG_PATH]["Shown"] = True
        self.assertTrue(wj.is_shown(None))
        self.assertEqual(self.stored(), {"welcome_shown": True})
        self.config.lose()
        self.assertTrue(wj.is_shown(None))

    def test_cleared_tick_shows_the_dialog_again(self):
        wj.set_shown(None, True)
        wj.set_shown(None, False)  # closed with "Không hiển thị lại" cleared
        self.assertEqual(self.config.values[wj.CONFIG_PATH]["Shown"], False)
        self.assertFalse(wj.is_shown(None))

    def test_show_welcome_marks_on_display_and_clears_on_untick(self):
        class Dialog:
            def __init__(self, ctx, strings, medium, on_shown=None):
                self.on_shown = on_shown

            def run(self, parent_peer=None):
                self.on_shown()
                return Dialog.keep
        for keep, expected in ((True, True), (False, False)):
            Dialog.keep = keep
            with mock.patch.object(wj, "Welcome", Dialog):
                wj.show_welcome(None, "welcome", strings={"welcome": {}})
            self.config.lose()
            self.assertEqual(wj.is_shown(None), expected, keep)


class DefaultApps(_Profile):
    def test_snooze_survives_the_lost_configuration(self):
        state = da.after_answer(da.for_release(da.load_state(None), "1.0.3"), False, 1_000)
        da.save_state(None, state)
        self.config.lose()
        got = da.load_state(None)
        self.assertEqual((got["Asked"], got["LastAsked"], got["Release"], got["Done"]), (1, 1_000, "1.0.3", False))
        self.assertFalse(da.should_ask(da.for_release(got, "1.0.3"), 1_000 + da.DAY, False))

    def test_agreement_survives_and_ask_stays_with_the_administrator(self):
        da.save_state(None, dict(da.DEFAULT_STATE, Asked=1, LastAsked=5, Done=True, Release="1.0.3"))
        self.config.lose()
        self.config.values[da.CONFIG_PATH]["Ask"] = False
        got = da.load_state(None)
        self.assertTrue(got["Done"])
        self.assertFalse(got["Ask"])

    def test_answer_of_a_version_without_the_file_is_migrated(self):
        self.config.values[da.CONFIG_PATH].update(Asked=2, LastAsked=7, Release="1.0.2")
        da.load_state(None)
        self.assertEqual(self.stored()["default_apps"], {"Asked": 2, "LastAsked": 7, "Done": False,
                                                         "Release": "1.0.2"})

    def test_merge_takes_the_latest_question_and_any_agreement(self):
        configured = dict(da.DEFAULT_STATE, Asked=1, LastAsked=10, Release="1.0.2", Done=True)
        stored = {"Asked": 2, "LastAsked": 20, "Done": False, "Release": "1.0.3"}
        got = da.merge_answers(configured, stored)
        self.assertEqual((got["Asked"], got["LastAsked"], got["Release"], got["Done"]), (2, 20, "1.0.3", True))
        older = dict(stored, LastAsked=5)
        got = da.merge_answers(configured, older)
        self.assertEqual((got["Asked"], got["LastAsked"], got["Release"]), (1, 10, "1.0.2"))
        self.assertEqual(da.merge_answers(configured, None), configured)
        self.assertEqual(da.merge_answers(configured, {"LastAsked": "x"}), configured)


class CrashQuestion(_Profile):
    def test_never_ask_survives_the_lost_configuration(self):
        self.assertTrue(crash.ask_enabled(None))
        crash.never_ask(None)
        self.assertFalse(self.config.values[crash.SETTINGS]["AskAfterCrash"])
        self.config.lose()
        self.assertFalse(crash.ask_enabled(None))

    def test_answer_of_a_version_without_the_file_is_migrated(self):
        self.config.values[crash.SETTINGS]["AskAfterCrash"] = False
        self.assertFalse(crash.ask_enabled(None))
        self.assertEqual(self.stored(), {"crash_never_ask": True})

    def test_administrator_lock_is_not_copied_as_the_users_answer(self):
        self.config.locked.add("AskAfterCrash")
        self.config.values[crash.SETTINGS]["AskAfterCrash"] = False
        self.assertFalse(crash.ask_enabled(None))
        self.assertEqual(self.stored(), {})


class Migration(_Profile):
    def test_every_start_copies_the_answers_of_an_earlier_version(self):
        self.config.values[wj.CONFIG_PATH]["Shown"] = True
        self.config.values[da.CONFIG_PATH].update(Asked=1, LastAsked=9, Release="1.0.2")
        self.config.values[crash.SETTINGS]["AskAfterCrash"] = False
        sc.migrate(None)
        self.config.lose()
        self.assertTrue(wj.is_shown(None))
        self.assertEqual(da.load_state(None)["Asked"], 1)
        self.assertFalse(crash.ask_enabled(None))

    def test_one_failing_reader_does_not_stop_the_others(self):
        self.config.values[crash.SETTINGS]["AskAfterCrash"] = False
        with mock.patch.object(wj, "is_shown", side_effect=RuntimeError("no schema")), \
                mock.patch.object(sc.diag_log, "exception"):
            sc.migrate(None)
        self.assertEqual(self.stored(), {"crash_never_ask": True})

    def test_the_start_up_job_migrates_before_scheduling_the_questions(self):
        from hst_office import startup_prompts as sp
        calls = []
        with mock.patch.object(sc, "migrate", lambda ctx: calls.append("migrate")), \
                mock.patch.object(wj, "run_later", lambda ctx, fn: calls.append("scheduled")), \
                mock.patch.object(sp, "_safe_snapshot", lambda ctx: None):
            sp.StartupPromptsJob(None).execute(())
        self.assertEqual(calls, ["migrate", "scheduled"])


class FileFormat(_Profile):
    def test_file_is_plain_json_in_the_hst_profile_folder(self):
        wj.set_shown(None, True)
        with open(os.path.join(self.folder, "startup-choices.json"), encoding="utf-8") as handle:
            self.assertEqual(json.load(handle), {"welcome_shown": True})


if __name__ == "__main__":
    unittest.main()
