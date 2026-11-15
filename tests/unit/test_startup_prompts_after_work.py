# SPDX-License-Identifier: AGPL-3.0-only
"""Start-up questions never land on the user's work: they wait for every document load, and on a busy machine the user
has often opened, typed or closed something by then. A modal question opening then would hold closing a tab or
quitting; it waits for a calmer start instead (the crash question, read once per start, still runs)."""
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
              "com.sun.star.task", "com.sun.star.frame", "com.sun.star.style",
              "com.sun.star.style.VerticalAlignment"):
    sys.modules.setdefault(_name, _StubModule(_name))

from hst_office import startup_activity as activity  # noqa: E402
from hst_office import startup_prompts as sp  # noqa: E402


class _Arg:
    def __init__(self, name, value):
        self.Name, self.Value = name, value


class _Model:
    def __init__(self, modified=False, hidden=False):
        self.modified, self.hidden = modified, hidden

    def isModified(self):
        return self.modified

    def getArgs(self):
        return (_Arg("Hidden", True),) if self.hidden else ()


class _Controller:
    def __init__(self, model=None):
        self.model = model

    def getModel(self):
        return self.model


class _Window:
    def __init__(self, visible=True):
        self.visible = visible

    def isVisible(self):
        return self.visible


class _Frame:
    def __init__(self, controller=None, visible=True):
        self.controller, self.window = controller, _Window(visible)

    def getController(self):
        return self.controller

    def getContainerWindow(self):
        return self.window


class _Desktop:
    def __init__(self, frames):
        self.frames = frames

    def getFrames(self):
        desk = self

        class _Access:
            def getCount(self):
                return len(desk.frames)

            def getByIndex(self, index):
                return desk.frames[index]
        return _Access()


def _ctx(desktop):
    ctx = mock.Mock()
    ctx.ServiceManager.createInstanceWithContext.return_value = desktop
    return ctx


class StartedWorking(unittest.TestCase):
    def setUp(self):
        self.start_center = _Frame(_Controller())  # StartModule: no model
        self.desktop = _Desktop([self.start_center])
        self.ctx = _ctx(self.desktop)
        self.before = activity.snapshot(self.ctx)

    def test_nothing_happened(self):
        self.assertFalse(activity.started_working(self.ctx, self.before))

    def test_a_document_opened_meanwhile(self):
        self.desktop.frames.append(_Frame(_Controller(_Model())))
        self.assertTrue(activity.started_working(self.ctx, self.before))

    def test_a_document_still_loading_in_a_shown_window(self):
        self.desktop.frames.append(_Frame(None))
        self.assertTrue(activity.started_working(self.ctx, self.before))

    def test_hidden_loads_are_not_the_users_work(self):
        self.desktop.frames += [_Frame(_Controller(_Model(hidden=True)), visible=False), _Frame(None, visible=False)]
        self.assertFalse(activity.started_working(self.ctx, self.before))

    def test_a_document_tab_parked_in_a_hidden_window_counts(self):
        self.desktop.frames.append(_Frame(_Controller(_Model()), visible=False))
        self.assertTrue(activity.started_working(self.ctx, self.before))

    def test_a_window_closed_meanwhile(self):
        self.desktop.frames.remove(self.start_center)
        self.assertTrue(activity.started_working(self.ctx, self.before))

    def test_the_start_center_replaced_by_a_new_document(self):
        self.start_center.controller = _Controller(_Model())
        self.assertTrue(activity.started_working(self.ctx, self.before))

    def test_a_document_modified(self):
        doc = _Frame(_Controller(_Model()))
        self.desktop.frames = [doc]
        before = activity.snapshot(self.ctx)
        doc.controller.model.modified = True
        self.assertTrue(activity.started_working(self.ctx, before))

    def test_the_document_opened_at_start_finishing_its_load_is_no_work(self):
        doc = _Frame(None)  # onFirstVisibleTask fires while the file from the file manager is imported
        self.desktop.frames = [doc]
        before = activity.snapshot(self.ctx)
        doc.controller = _Controller(_Model())
        self.assertFalse(activity.started_working(self.ctx, before))


class RunAfterWork(unittest.TestCase):
    def steps(self, ran):
        return [(name, (lambda n=name: ran.append(n) or False)) for name in sp.ORDER]

    def test_calm_start_asks_every_question_in_order(self):
        ran = []
        with mock.patch.object(sp, "_started_working", return_value=False):
            sp.run(object(), self.steps(ran), after=lambda _ctx: None, before=[])
        self.assertEqual(ran, list(sp.ORDER))

    def test_after_the_user_started_working_only_the_crash_question_runs(self):
        ran, checked = [], []
        with mock.patch.object(sp, "_started_working", return_value=True):
            sp.run(object(), self.steps(ran), after=lambda _ctx: checked.append(True), before=[])
        self.assertEqual(ran, ["crash"])
        self.assertEqual(checked, [True])  # the non-modal update check still runs

    def test_without_a_snapshot_the_questions_run_as_before(self):
        ran = []
        sp.run(object(), self.steps(ran), after=lambda _ctx: None, before=None)
        self.assertEqual(ran, list(sp.ORDER))

    def test_the_job_schedules_the_questions_with_a_snapshot_taken_now(self):
        scheduled = []
        with mock.patch.object(sp, "_safe_snapshot", return_value=["snap"]), \
                mock.patch("hst_office.welcome_job.run_later", lambda ctx, fn: scheduled.append(fn)), \
                mock.patch.object(sp, "run") as run:
            sp.StartupPromptsJob("ctx").execute(())
            scheduled[0]()
        run.assert_called_once_with("ctx", before=["snap"])


if __name__ == "__main__":
    unittest.main()
