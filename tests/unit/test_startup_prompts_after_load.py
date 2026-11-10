# SPDX-License-Identifier: AGPL-3.0-only
"""Start-up questions wait for a document opened at start: a file opened from the file manager shows its frame before
the import, so a modal question run then would hold the import under it (blank window, "Load document")."""
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

from hst_office import welcome_job as wj  # noqa: E402


class _Window:
    def __init__(self, visible):
        self.visible = visible

    def isVisible(self):
        return self.visible


class _Frame:
    def __init__(self, controller, visible=True):
        self.controller, self.window = controller, _Window(visible)

    def getController(self):
        return self.controller

    def getContainerWindow(self):
        return self.window


class _Frames:
    def __init__(self, frames):
        self.frames = frames

    def getCount(self):
        return len(self.frames)

    def getByIndex(self, index):
        return self.frames[index]


def _ctx(frames):
    desktop = mock.Mock()
    desktop.getFrames.return_value = _Frames(frames)
    ctx = mock.Mock()
    ctx.ServiceManager.createInstanceWithContext.return_value = desktop
    return ctx


class Loading(unittest.TestCase):
    def test_a_shown_frame_without_controller_is_loading(self):
        self.assertTrue(wj.loading(_ctx([_Frame(object()), _Frame(None)])))

    def test_loaded_frames_and_hidden_loads_do_not_hold_the_prompts(self):
        self.assertFalse(wj.loading(_ctx([_Frame(object()), _Frame(None, visible=False)])))
        self.assertFalse(wj.loading(_ctx([])))


class Later(unittest.TestCase):
    def make(self, frames, now=None):
        ran, timers, posts = [], [], []
        clock = now or (lambda: 0.0)
        later = wj._Later(_ctx(frames), lambda: ran.append(True), 0, clock=clock,
                          timer=lambda delay, action: timers.append((delay, action)))
        return later, ran, timers, posts

    def test_runs_at_once_when_nothing_loads(self):
        later, ran, timers, _ = self.make([_Frame(object())])
        later.notify(None)
        self.assertEqual((ran, timers), ([True], []))

    def test_waits_for_the_import_then_runs(self):
        frame = _Frame(None)
        later, ran, timers, _ = self.make([frame])
        with mock.patch.object(wj, "_post") as post:
            later.notify(None)
            self.assertEqual(ran, [])
            self.assertEqual(timers[0][0], wj.LOAD_POLL)
            timers[0][1]()  # the timer posts the callback again to the main loop
            post.assert_called_once_with(later.ctx, later)
        frame.controller = object()  # the import ended
        later.notify(None)
        self.assertEqual(ran, [True])

    def test_a_load_that_never_ends_does_not_hold_the_prompts_forever(self):
        now = [0.0]
        later, ran, timers, _ = self.make([_Frame(None)], now=lambda: now[0])
        later.notify(None)
        self.assertEqual(ran, [])
        now[0] = wj.LOAD_WAIT + 1
        later.notify(None)
        self.assertEqual(ran, [True])

    def test_a_broken_check_runs_the_prompts(self):
        ctx = mock.Mock()
        ctx.ServiceManager.createInstanceWithContext.side_effect = RuntimeError("no desktop")
        ran = []
        later = wj._Later(ctx, lambda: ran.append(True), 0, clock=lambda: 0.0, timer=lambda *a: None)
        with mock.patch.object(wj.diag_log, "exception") as logged:
            later.notify(None)
        self.assertEqual(ran, [True])
        logged.assert_called_once_with("welcome_job.loading")


if __name__ == "__main__":
    unittest.main()
